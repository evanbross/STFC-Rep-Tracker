# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# LICENSE: Personal Use Only
# This source code is made available for personal, non-commercial use only.
# You may read, study, and run this code for personal purposes.
# You may NOT:
#   - Use this code, in whole or in part, in any commercial product or service
#   - Sell, sublicense, or otherwise monetize this code or derivatives of it
#   - Redistribute this code without explicit written permission from ZombieTech LLC
#
# No warranty is provided, express or implied. Use at your own risk.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
import os
import re
import time
from datetime import datetime, UTC
from typing import Any

import cv2
import numpy as np

from app.app_config import capture_cfg
from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    get_reader,
    match_template,
    wait_for_any_template,
    wait_and_click,
    wait_and_click_any,
)

logger = logging.getLogger(__name__)

# Faction dicts as returned by FactionsDAO — typed loosely since the DAO
# is not yet annotated.
_FactionDict = dict[str, Any]

# Return type for _navigate_to_factions: success gives (window, None),
# failure gives (None, error dict).
_NavResult = tuple[Any, None] | tuple[None, dict[str, str]]


class ProcessReputationsOrchestrator:
    def __init__(self, db: Any) -> None:
        from app.database.status_entries_dao import StatusEntriesDAO

        self.sc: ScreenCapture = ScreenCapture()
        self.stat_dao: StatusEntriesDAO = StatusEntriesDAO(db)
        self.factions_dao: Any = db.factions

    def _navigate_to_factions(self) -> _NavResult:
        """Activate window, then navigate to the faction store if not already there.

        Checks for the faction store header snippet first — if it's already visible,
        skips the home-screen navigation and Factions button click entirely.

        Returns (window, None) on success or (None, error_dict) on failure.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(e)
            return None, {"error": str(e)}

        img = self.sc.capture(window)
        header_threshold: float = capture_cfg("factions", "header_threshold", default=0.70)
        header_match = match_template("Faction Store Header.jpg", img)
        if header_match is not None and header_match[1] >= header_threshold:
            logger.info(
                f"Already on faction store (header score={header_match[1]:.3f}) — skipping navigation"
            )
            return window, None

        logger.info("Faction store header not detected — navigating from home screen")
        try:
            self.sc.navigate_to_home_screen(window)
        except RuntimeError as e:
            logger.error(f"Could not reach home screen: {e}")
            return None, {"error": str(e)}

        if not wait_and_click_any(
            ["Factions Button.jpg", "Factions Button2.jpg", "Factions Button 3.jpg"],
            self.sc,
            window,
            (window.left, window.top),
        ):
            logger.error("Factions Button not found")
            return None, {"error": "Factions Button not found"}

        return window, None

    def _save_results(self, results: list[_FactionDict]) -> list[_FactionDict]:
        """Persist captured reputation points to the database.

        Iterates results from _process_faction_list, writes each entry that has a
        non-None points value to the status_entries table, and returns a list of
        successfully saved {"faction": name, "points": value} dicts.
        """
        saved: list[_FactionDict] = []
        for item in results or []:
            points: int | None = item.get("points")
            if points is None:
                continue
            try:
                self.stat_dao.add_status_entry(item["faction"], points)
                saved.append({"faction": item["faction"], "points": points})
                logger.info(f"Saved {item['faction']}: {points:,}")
            except Exception as e:
                logger.error(f"Failed to save {item['faction']}: {e}")
        return saved

    def process_single_faction(self, faction_code: str) -> dict[str, Any]:
        window, err = self._navigate_to_factions()
        if err:
            return err

        faction = self.factions_dao.get_faction_by_code(faction_code)
        if not faction:
            return {"error": f"Faction '{faction_code}' not found"}

        results = _process_faction_list([faction], window, self.sc)
        saved = self._save_results(results)
        return {"saved": saved, "results": results}

    def process_reputations(self) -> dict[str, Any]:
        window, err = self._navigate_to_factions()
        if err:
            return err

        results = _process_faction_list(self.factions_dao.get_all_factions(), window, self.sc)
        saved = self._save_results(results)
        return {"saved": saved, "results": results}


def _find_highlighted_faction(
    img: np.ndarray, factions: list[_FactionDict]
) -> str | None:
    """Identify which faction is currently highlighted in the faction store.

    Args:
        img:      BGR numpy array of a screenshot of the faction store.
        factions: List of faction dicts with a 'selected_snippets' list.

    Returns the name of the best-matching faction, or None if no snippet exceeds
    the threshold.
    """
    if img is None:
        raise ValueError("_find_highlighted_faction: img is None")

    threshold: float = capture_cfg("factions", "snippet_threshold", default=0.70)
    best_name: str | None = None
    best_score: float = -1.0

    for faction in factions:
        fname: str = faction.get("name", "<unknown>")
        snippets: list[dict[str, Any]] = faction.get("selected_snippets", [])

        faction_best: float = -1.0
        faction_best_file: str | None = None
        for s in snippets:
            filename: str | None = s.get("filename")
            if not filename:
                continue
            try:
                m = match_template(filename, img)
                score: float | None = m[1] if m is not None else None
                if score is not None:
                    logger.debug(f"'{fname}' {filename} score={score:.3f}")
                    if score > faction_best:
                        faction_best = score
                        faction_best_file = filename
            except FileNotFoundError:
                logger.debug(f"'{fname}' file missing ({filename})")

        if faction_best > best_score:
            best_score = faction_best
            best_name = fname
            logger.debug(
                f"'{fname}' new best via {faction_best_file} (score={faction_best:.3f})"
            )

    if best_name is not None and best_score >= threshold:
        logger.info(f"'{best_name}' (score={best_score:.3f})")
        return best_name

    logger.info(
        f"No faction exceeded threshold {threshold} "
        f"(best='{best_name}' at {best_score:.3f})"
    )
    return None


def capture_and_identify_faction(db: Any) -> dict[str, Any]:
    """Capture the current STFC window and identify which faction is highlighted.

    Returns a dict with {"faction": name} or {"error": message}.
    """
    sc = ScreenCapture()
    try:
        window = sc.get_and_activate_window()
    except RuntimeError as e:
        logger.error(e)
        return {"error": str(e)}

    img = sc.capture(window)
    factions: list[_FactionDict] = sorted(
        db.factions.get_all_factions(), key=lambda f: f.get("display_order") or 999
    )

    try:
        faction = _find_highlighted_faction(img, factions)
        return {"faction": faction}
    except Exception as e:
        logger.error(e)
        return {"error": str(e)}


def _preprocess_for_ocr(region_bgr: np.ndarray) -> np.ndarray:
    """Scale up and threshold a BGR region to improve OCR accuracy on small UI text.

    Uses Otsu's global threshold instead of adaptive thresholding — more reliable
    for game UI text (light text on a dark, mostly-uniform background).
    """
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    scale: int = capture_cfg("ocr", "scale_factor", default=3)
    scaled = cv2.resize(
        gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4
    )
    # Invert so text becomes dark-on-white, then apply Otsu's global threshold
    inverted = cv2.bitwise_not(scaled)
    _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _save_debug_crop(
    region_bgr: np.ndarray, preprocessed: np.ndarray, label: str = "crop"
) -> None:
    """Save raw and preprocessed crops to Screenshots/debug/ for OCR tuning."""
    debug_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "Screenshots", "debug"
    )
    os.makedirs(debug_dir, exist_ok=True)
    ts = datetime.now(UTC).strftime("%H-%M-%S")
    cv2.imwrite(os.path.join(debug_dir, f"{ts}_{label}_raw.png"), region_bgr)
    cv2.imwrite(os.path.join(debug_dir, f"{ts}_{label}_preprocessed.png"), preprocessed)


def _digit_count(s: str) -> int:
    """Return the number of digits in s (ignoring sign and commas)."""
    return len(s.replace("-", "").replace(",", ""))


# ai: claude-sonnet-5 | 2026-07-10
def _extract_points(img: np.ndarray | None, faction_name: str = "") -> int | None:
    if img is None:
        logger.warning("No image provided to _extract_points")
        return None

    height, width = img.shape[:2]

    # "Points: X,XXX" is in the top-left faction panel, not the right panel.
    # Extend the height crop slightly to capture the points row even when the
    # "FACTION STORE" header pushes it down a little.
    h_frac: float = capture_cfg("ocr", "points_height_frac", default=0.13)
    w_frac: float = capture_cfg("ocr", "points_width_frac", default=0.22)
    points_region = img[0 : int(height * h_frac), 0 : int(width * w_frac)]
    preprocessed = _preprocess_for_ocr(points_region)

    results: list[str] = get_reader().readtext(preprocessed, detail=0)
    text = " ".join(results)
    logger.debug(f"Raw OCR results from points region: {results!r}")
    logger.info(f"'{faction_name}' reputation OCR text: {text!r}")

    # Parse out the number after "Points" — support negative values (e.g. "-1,234")
    # and allow common OCR substitutions in the label (e.g. "Polnts", "P0ints").
    match = re.search(r"[Pp][o0O][il1][Nn][Tt][Ss][:\s]*(-?[\d,]+)", text)
    if match:
        if logger.isEnabledFor(logging.DEBUG):
            _save_debug_crop(points_region, preprocessed, label="points")
        return int(match.group(1).replace(",", ""))

    # Second-pass: re-run OCR with a digits/minus/comma allowlist to reduce misreads
    digit_results: list[str] = get_reader().readtext(
        preprocessed, detail=0, allowlist="0123456789,-"
    )
    digit_text = " ".join(digit_results)
    logger.debug(f"Digit-only OCR results: {digit_results!r}")

    # Try the Points pattern again with a fuzzier label match, then pull the
    # number from the digit-only pass which is more reliable.
    if re.search(r"[Pp].{0,3}[Nn][Tt][Ss]", text):
        numbers: list[str] = re.findall(r"-?[\d,]{3,}", digit_text)
        if numbers:
            if logger.isEnabledFor(logging.DEBUG):
                _save_debug_crop(points_region, preprocessed, label="points")
            return int(max(numbers, key=_digit_count).replace(",", ""))

    # No "Points:" label detected — save crops to aid diagnosis regardless of log level.
    _save_debug_crop(points_region, preprocessed, label="points_FAIL")
    logger.info("'Points' label not found — saved debug crop to Screenshots/debug/")
    return None


def click_faction_button(
    faction: _FactionDict,
    img: np.ndarray,
    screen_offset: tuple[int, int] = (0, 0),
) -> bool:
    """Locate and click a faction's name button on the left side of the screen.

    Uses the RepButton snippet (faction icon + name) to find the correct button
    via template matching.  The snippet filename comes from snippet_unselected; if
    that is not set, falls back to RepButton{code}.jpg derived from the faction code.
    Returns True if the button was found and clicked, False otherwise.
    """
    name: str = faction.get("name", "<unknown>")
    raw_filename: str | None = faction.get("snippet_unselected")
    if raw_filename:
        filename: str = raw_filename
    else:
        code: str | None = faction.get("code")
        if not code:
            logger.warning(f"'{name}' has no snippet_unselected or code")
            return False
        filename = f"RepButton{code.capitalize()}.jpg"
        logger.debug(f"'{name}' no snippet_unselected, derived {filename} from code")

    crop_h_frac: float = capture_cfg("factions", "snippet_name_height_frac", default=1.0)
    clicked: bool = click_button_if_visible(
        filename, img, screen_offset, crop_h_frac=crop_h_frac
    )
    if clicked:
        logger.debug(f"Clicked '{name}' using {filename}")
        return True

    # Button not found at normal threshold — it may already be selected (brighter
    # appearance). Retry with a lower threshold to handle the selected state.
    fallback_threshold: float = capture_cfg(
        "factions", "button_selected_threshold", default=0.60
    )
    clicked = click_button_if_visible(
        filename,
        img,
        screen_offset,
        crop_h_frac=crop_h_frac,
        threshold=fallback_threshold,
    )
    if clicked:
        logger.debug(f"Clicked '{name}' at fallback threshold (already selected)")
    else:
        logger.warning(f"'{name}' button not matched on screen ({filename})")
    return clicked


def _process_faction_list(
    factions: list[_FactionDict], window: Any, sc: ScreenCapture
) -> list[_FactionDict]:
    """Iterate through a list of faction dicts and capture reputation points.

    For each faction:
      1. Wait for and click the faction's unselected sidebar button (snippet_unselected).
      2. Wait for snippet_selected_desc to confirm the faction panel is active.
      3. Extract reputation points if the Points region is visible.

    Args:
        factions: list of faction dicts (as returned by FactionsDAO.get_all_factions())
        window:   STFC window object (from ScreenCapture.get_stfc_window())
        sc:       ScreenCapture instance (used to take fresh screenshots)

    Returns:
        list of dicts: [{"faction": name, "clicked": bool, "points": int|None, "error": str|None}, ...]
    """
    screen_offset: tuple[int, int] = (window.left, window.top)
    results: list[_FactionDict] = []

    for faction in factions:
        name: str = faction.get("name", "<unknown>")

        unselected: str | None = faction.get("snippet_unselected")
        selected_snippets: list[dict[str, Any]] = faction.get("selected_snippets", [])
        selected_filenames: list[str] = [
            s["filename"] for s in selected_snippets if s.get("filename")
        ]
        desc_filenames: list[str] = [
            s["filename"]
            for s in selected_snippets
            if s.get("snippet_type") == "desc" and s.get("filename")
        ]
        confirm_filenames: list[str] = desc_filenames if desc_filenames else selected_filenames

        logger.info(
            f"Selecting '{name}' — unselected={unselected} "
            f"selected={selected_filenames} confirm={confirm_filenames}"
        )

        if not unselected:
            logger.warning(f"'{name}' has no snippet_unselected — skipping")
            results.append(
                {
                    "faction": name,
                    "clicked": False,
                    "points": None,
                    "error": "no snippet_unselected",
                }
            )
            continue

        wait_templates: list[str] = [unselected] + selected_filenames
        filename, img = wait_for_any_template(wait_templates, sc, window)
        if filename is None:
            logger.warning(f"'{name}' — no indicator visible — skipping")
            results.append(
                {
                    "faction": name,
                    "clicked": False,
                    "points": None,
                    "error": "button not found",
                }
            )
            continue

        # ai: claude-sonnet-5 | 2026-07-10
        if filename == unselected:
            logger.info(f"'{name}' unselected button located (template='{filename}')")
        else:
            logger.info(f"'{name}' already selected — selected button located (template='{filename}')")

        clicked = False
        if filename == unselected:
            clicked = wait_and_click(unselected, sc, window, screen_offset)
            if not clicked:
                logger.warning(
                    f"'{name}' unselected button disappeared before click — skipping"
                )
                results.append(
                    {
                        "faction": name,
                        "clicked": False,
                        "points": None,
                        "error": "button not found",
                    }
                )
                continue

        points: int | None = None
        if confirm_filenames:
            confirm_first_delay: float = capture_cfg("factions", "confirm_first_delay", default=0.5)
            confirm_retries: int = capture_cfg("factions", "confirm_retries", default=8)
            confirm_delay: float = capture_cfg("factions", "confirm_delay", default=0.2)
            time.sleep(confirm_first_delay)
            confirm_file, _ = wait_for_any_template(
                confirm_filenames, sc, window,
                max_retries=confirm_retries, delay=confirm_delay,
            )
            if confirm_file is not None:
                logger.info(f"'{name}' selected button found (template='{confirm_file}')")  # ai: claude-sonnet-5 | 2026-07-10
                fresh_img = sc.capture(window)
                points = _extract_points(fresh_img, faction_name=name)
                if points is None:
                    logger.info(f"'{name}' has no reputation — skipping")
                else:
                    logger.info(f"'{name}' points = {points:,}")
            else:
                logger.warning(
                    f"'{name}' no confirm snippet visible after click — skipping"
                )
        else:
            logger.warning(f"'{name}' has no selected snippets — skipping points")

        results.append(
            {"faction": name, "clicked": clicked, "points": points, "error": None}
        )

    return results


def click_all_faction_buttons(
    factions_dao: Any, window: Any, sc: ScreenCapture
) -> list[_FactionDict]:
    """Legacy wrapper — calls _process_faction_list with all factions from the DAO."""
    return _process_faction_list(factions_dao.get_all_factions(), window, sc)


# if __name__ == "__main__":
#     import sys
#
#     path = sys.argv[1] if len(sys.argv) > 1 else "screenshot.png"
#     analyze_screenshot(path)