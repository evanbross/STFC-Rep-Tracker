import logging
import os

import cv2

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


class ProcessReputationsOrchestrator:
    def __init__(self, db):
        from app.database.status_entries_dao import StatusEntriesDAO

        self.sc = ScreenCapture()
        self.stat_dao = StatusEntriesDAO(db)
        self.factions_dao = db.factions

    def process_reputations(self):
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(e)
            return {"error": str(e)}

        try:
            self.sc.navigate_to_home_screen(window)
        except RuntimeError as e:
            logger.error(f"Could not reach home screen: {e}")
            return {"error": str(e)}

        if not wait_and_click_any(
            ["Factions Button.jpg", "Factions Button2.jpg"],
            self.sc,
            window,
            (window.left, window.top),
        ):
            logger.error("Factions Button not found")
            return {"error": "Factions Button not found"}

        # self.sc.press_key(window, "T")

        results = click_all_faction_buttons(self.factions_dao, window, self.sc)

        # results = analyze_screenshot(window, self.factions_dao)

        saved = []
        for item in results or []:
            points = item.get("points")
            if points is None:
                continue
            try:
                self.stat_dao.add_status_entry(item["faction"], points)
                saved.append({"faction": item["faction"], "points": points})
                logger.info(f"Saved {item['faction']}: {points:,}")
            except Exception as e:
                logger.error(f"Failed to save {item['faction']}: {e}")

        return {"saved": saved, "results": results}


def _find_highlighted_faction(image_path, factions):
    """Identify which faction is currently highlighted in the faction store.

    Args:
        image_path: Path to a screenshot of the faction store.
        factions:   List of faction dicts with a 'selected_snippets' list.

    Returns the name of the best-matching faction, or None if no snippet exceeds
    the threshold.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    threshold = capture_cfg("factions", "snippet_threshold", default=0.70)
    best_name = None
    best_score = -1

    for faction in factions:
        fname = faction.get("name", "<unknown>")
        snippets = faction.get("selected_snippets", [])

        faction_best = -1
        faction_best_file = None
        for s in snippets:
            filename = s.get("filename")
            if not filename:
                continue
            try:
                m = match_template(filename, img)
                score = m[1] if m is not None else None
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


def capture_and_identify_faction(db):
    """Capture the current STFC window and identify which faction is highlighted.

    Returns a dict with {"faction": name} or {"error": message}.
    """
    sc = ScreenCapture()
    try:
        window = sc.get_and_activate_window()
    except RuntimeError as e:
        logger.error(e)
        return {"error": str(e)}

    image_path = sc.capture_window(window)
    factions = sorted(
        db.factions.get_all_factions(), key=lambda f: f.get("display_order") or 999
    )

    try:
        faction = _find_highlighted_faction(image_path, factions)
        return {"faction": faction}
    except Exception as e:
        logger.error(e)
        return {"error": str(e)}


def _preprocess_for_ocr(region_bgr):
    """Scale up and threshold a BGR region to improve OCR accuracy on small UI text.

    Uses Otsu's global threshold instead of adaptive thresholding — more reliable
    for game UI text (light text on a dark, mostly-uniform background).
    """
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    scale = capture_cfg("ocr", "scale_factor", default=3)
    scaled = cv2.resize(
        gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4
    )
    # Invert so text becomes dark-on-white, then apply Otsu's global threshold
    inverted = cv2.bitwise_not(scaled)
    _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _save_debug_crop(region_bgr, preprocessed, label="crop"):
    """Save raw and preprocessed crops to Screenshots/debug/ for OCR tuning."""
    debug_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "Screenshots", "debug"
    )
    os.makedirs(debug_dir, exist_ok=True)
    from datetime import datetime

    ts = datetime.now().strftime("%H-%M-%S")
    cv2.imwrite(os.path.join(debug_dir, f"{ts}_{label}_raw.png"), region_bgr)
    cv2.imwrite(os.path.join(debug_dir, f"{ts}_{label}_preprocessed.png"), preprocessed)


def _digit_count(s):
    """Return the number of digits in s (ignoring sign and commas)."""
    return len(s.replace("-", "").replace(",", ""))


def _extract_points(image_path):
    import re

    if not image_path:
        logger.warning("No image path provided")
        return None

    img = cv2.imread(image_path)
    if img is None:
        logger.warning(f"Could not load image: {image_path}")
        return None

    height, width = img.shape[:2]

    # "Points: X,XXX" is in the top-left faction panel, not the right panel.
    # Extend the height crop slightly to capture the points row even when the
    # "FACTION STORE" header pushes it down a little.
    h_frac = capture_cfg("ocr", "points_height_frac", default=0.13)
    w_frac = capture_cfg("ocr", "points_width_frac", default=0.22)
    points_region = img[0 : int(height * h_frac), 0 : int(width * w_frac)]
    preprocessed = _preprocess_for_ocr(points_region)

    results = get_reader().readtext(preprocessed, detail=0)
    text = " ".join(results)
    logger.debug(f"Raw OCR results from points region: {results!r}")
    logger.debug(f"Joined OCR text: {text!r}")

    # Parse out the number after "Points" — support negative values (e.g. "-1,234")
    # and allow common OCR substitutions in the label (e.g. "Polnts", "P0ints").
    match = re.search(r"[Pp][o0O][il1][Nn][Tt][Ss][:\s]*(-?[\d,]+)", text)
    if match:
        if logger.isEnabledFor(logging.DEBUG):
            _save_debug_crop(points_region, preprocessed, label="points")
        return int(match.group(1).replace(",", ""))

    # Second-pass: re-run OCR with a digits/minus/comma allowlist to reduce misreads
    digit_results = get_reader().readtext(
        preprocessed, detail=0, allowlist="0123456789,-"
    )
    digit_text = " ".join(digit_results)
    logger.debug(f"Digit-only OCR results: {digit_results!r}")

    # Try the Points pattern again with a fuzzier label match, then pull the
    # number from the digit-only pass which is more reliable.
    if re.search(r"[Pp].{0,3}[Nn][Tt][Ss]", text):
        numbers = re.findall(r"-?[\d,]{3,}", digit_text)
        if numbers:
            if logger.isEnabledFor(logging.DEBUG):
                _save_debug_crop(points_region, preprocessed, label="points")
            return int(max(numbers, key=_digit_count).replace(",", ""))

    # No "Points:" label detected — save crops to aid diagnosis regardless of log level.
    _save_debug_crop(points_region, preprocessed, label="points_FAIL")
    logger.info("'Points' label not found — saved debug crop to Screenshots/debug/")
    return None


def click_faction_button(faction, img, screen_offset=(0, 0)):
    """Locate and click a faction's name button on the left side of the screen.

    Uses the RepButton snippet (faction icon + name) to find the correct button
    via template matching.  The snippet filename comes from snippet_unselected; if
    that is not set, falls back to RepButton{code}.jpg derived from the faction code.
    Returns True if the button was found and clicked, False otherwise.
    """
    name = faction.get("name", "<unknown>")
    filename = faction.get("snippet_unselected")
    if not filename:
        code = faction.get("code")
        if not code:
            logger.warning(f"'{name}' has no snippet_unselected or code")
            return False
        filename = f"RepButton{code.capitalize()}.jpg"
        logger.debug(f"'{name}' no snippet_unselected, derived {filename} from code")

    crop_h_frac = capture_cfg("factions", "snippet_name_height_frac", default=1.0)
    clicked = click_button_if_visible(
        filename, img, screen_offset, crop_h_frac=crop_h_frac
    )
    if clicked:
        logger.debug(f"Clicked '{name}' using {filename}")
        return True

    # Button not found at normal threshold — it may already be selected (brighter
    # appearance). Retry with a lower threshold to handle the selected state.
    fallback_threshold = capture_cfg(
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


def click_all_faction_buttons(factions_dao, window, sc):
    """Iterate through factions and capture reputation points from the faction store.

    For each faction:
      1. Wait for and click the faction's unselected sidebar button (snippet_unselected).
      2. Wait for snippet_selected_desc to confirm the faction panel is active.
      3. Extract reputation points if the Points region is visible.

    Args:
        factions_dao: FactionsDAO instance used to query all factions from the DB
        window:       STFC window object (from ScreenCapture.get_stfc_window())
        sc:           ScreenCapture instance (used to take fresh screenshots)

    Returns:
        list of dicts: [{"faction": name, "clicked": bool, "points": int|None, "error": str|None}, ...]
    """
    screen_offset = (window.left, window.top)
    results = []
    factions = factions_dao.get_all_factions()

    for faction in factions:
        name = faction.get("name", "<unknown>")

        unselected = faction.get("snippet_unselected")
        selected_snippets = faction.get("selected_snippets", [])
        selected_filenames = [
            s["filename"] for s in selected_snippets if s.get("filename")
        ]
        desc_filenames = [
            s["filename"]
            for s in selected_snippets
            if s.get("snippet_type") == "desc" and s.get("filename")
        ]
        confirm_filenames = desc_filenames if desc_filenames else selected_filenames

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

        wait_templates = [unselected] + selected_filenames
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
        logger.info(f"'{name}' found via {filename}")

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

        points = None
        if confirm_filenames:
            confirm_file, _ = wait_for_any_template(confirm_filenames, sc, window)
            if confirm_file is not None:
                img_path = sc.capture_window(window)
                points = _extract_points(img_path)
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


# if __name__ == "__main__":
#     import sys
#
#     path = sys.argv[1] if len(sys.argv) > 1 else "screenshot.png"
#     analyze_screenshot(path)
