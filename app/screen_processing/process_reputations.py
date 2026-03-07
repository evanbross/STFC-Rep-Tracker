import logging
import os
import time

import cv2
import numpy as np

from app.screen_processing.screen_capture import (
    ScreenCapture,
    _SNIPPETS_DIR,
    click_button_if_visible,
    get_reader,
)

logger = logging.getLogger(__name__)


class ProcessReputationsOrchestrator:
    def __init__(self, db):
        from app.database.status_entries_dao import StatusEntriesDAO

        self.sc = ScreenCapture()
        self.stat_dao = StatusEntriesDAO(db)
        self.factions_dao = db.factions

    def capture_and_analyze(self):
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(f"capture_and_analyze: {e}")
            return {"error": str(e)}

        try:
            filepath = self.sc.capture_window(window)
            logger.info(f"capture_and_analyze: Captured screenshot: {filepath}")
        except Exception as e:
            logger.error(f"capture_and_analyze: Failed to capture screen: {e}")
            return {"error": "Failed to capture screen"}

        results = analyze_screenshot(window, filepath, self.factions_dao)

        saved = []
        for item in results or []:
            points = item.get("points")
            if points is None:
                continue
            try:
                self.stat_dao.add_status_entry(item["faction"], points)
                saved.append({"faction": item["faction"], "points": points})
                logger.info(f"capture_and_analyze: saved {item['faction']}: {points:,}")
            except Exception as e:
                logger.error(
                    f"capture_and_analyze: failed to save {item['faction']}: {e}"
                )

        return {"saved": saved, "results": results}


def _find_highlighted_faction(image_path, factions):
    """Identify which faction is currently highlighted in the faction store sidebar.

    Args:
        image_path: Path to a screenshot of the faction store.
        factions:   List of faction dicts (must have 'name' and 'code' keys),
                    ordered by display_order to match the on-screen row order.

    Returns the name of the highlighted faction.

    Strategy:
        1. Template matching — for each faction that has a SelectedRow{Code}.jpg
           snippet, run matchTemplate against the screenshot.  The faction with
           the highest match score wins (provided it exceeds the threshold).
        2. Brightness fallback — if no snippets are available (or no match
           exceeds the threshold), falls back to the original brightness-based
           row detection.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    best_name = None
    best_score = -1

    for faction in factions:
        code = (faction.get("code") or "").strip().capitalize()
        name = faction.get("name", "<unknown>")
        if not code:
            continue
        snippet_path = os.path.normpath(
            os.path.join(_SNIPPETS_DIR, f"SelectedRow{code}.jpg")
        )
        if not os.path.isfile(snippet_path):
            logger.debug(
                f"_find_highlighted_faction: no snippet for '{name}' ({snippet_path})"
            )
            continue
        template = cv2.imread(snippet_path)
        if template is None:
            continue
        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        logger.debug(
            f"_find_highlighted_faction: '{name}' template score={max_val:.3f}"
        )
        if max_val > best_score:
            best_score = max_val
            best_name = name

    _SNIPPET_THRESHOLD = 0.70
    if best_name is not None and best_score >= _SNIPPET_THRESHOLD:
        logger.info(
            f"_find_highlighted_faction: highlighted faction is '{best_name}' "
            f"(template score={best_score:.3f})"
        )
        return best_name

    # ── Brightness fallback ────────────────────────────────────────────────
    logger.debug(
        "_find_highlighted_faction: template matching inconclusive "
        f"(best={best_score:.3f}), falling back to brightness analysis"
    )
    height, width = img.shape[:2]
    faction_panel = img[:, : int(width * 0.45)]
    gray = cv2.cvtColor(faction_panel, cv2.COLOR_BGR2GRAY)
    num_factions = len(factions)
    row_height = height // num_factions
    best_brightness = -1
    best_name = None
    for i, faction in enumerate(factions):
        name = faction.get("name", "<unknown>")
        y1 = i * row_height
        y2 = y1 + row_height
        avg_brightness = np.mean(gray[y1:y2, :])
        logger.debug(
            f"_find_highlighted_faction: brightness row {i} '{name}'={avg_brightness:.1f}"
        )
        if avg_brightness > best_brightness:
            best_brightness = avg_brightness
            best_name = name

    logger.info(
        f"_find_highlighted_faction: highlighted faction is '{best_name}' "
        f"(brightness fallback, score={best_brightness:.1f})"
    )
    return best_name


def capture_and_identify_faction(db):
    """Capture the current STFC window and identify which faction is highlighted.

    Returns a dict with {"faction": name} or {"error": message}.
    """
    sc = ScreenCapture()
    try:
        window = sc.get_and_activate_window()
    except RuntimeError as e:
        logger.error(f"capture_and_identify_faction: {e}")
        return {"error": str(e)}

    image_path = sc.capture_window(window)
    factions = sorted(
        db.factions.get_all_factions(), key=lambda f: f.get("display_order") or 999
    )

    try:
        faction = _find_highlighted_faction(image_path, factions)
        return {"faction": faction}
    except Exception as e:
        logger.error(f"capture_and_identify_faction: {e}")
        return {"error": str(e)}


def _preprocess_for_ocr(region_bgr):
    """Scale up and threshold a BGR region to improve OCR accuracy on small UI text.

    Uses Otsu's global threshold instead of adaptive thresholding — more reliable
    for game UI text (light text on a dark, mostly-uniform background).
    """
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    scaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
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
        logger.warning("_extract_points: no image path provided")
        return None

    img = cv2.imread(image_path)
    if img is None:
        logger.warning(f"_extract_points: could not load image: {image_path}")
        return None

    height, width = img.shape[:2]

    # "Points: X,XXX" is in the top-left faction panel, not the right panel.
    # Extend the height crop slightly to capture the points row even when the
    # "FACTION STORE" header pushes it down a little.
    points_region = img[0 : int(height * 0.13), 0 : int(width * 0.22)]
    preprocessed = _preprocess_for_ocr(points_region)

    if logger.isEnabledFor(logging.DEBUG):
        _save_debug_crop(points_region, preprocessed, label="points")

    results = get_reader().readtext(preprocessed, detail=0)
    text = " ".join(results)
    logger.debug(f"Raw OCR results from points region: {results!r}")
    logger.debug(f"Joined OCR text: {text!r}")

    # Parse out the number after "Points" — support negative values (e.g. "-1,234")
    # and allow common OCR substitutions in the label (e.g. "Polnts", "P0ints").
    match = re.search(r"[Pp][o0O][il1][Nn][Tt][Ss][:\s]*(-?[\d,]+)", text)
    if match:
        return int(match.group(1).replace(",", ""))

    # Second-pass: re-run OCR with a digits/minus/comma allowlist to reduce misreads
    digit_results = get_reader().readtext(
        preprocessed, detail=0, allowlist="0123456789,-"
    )
    digit_text = " ".join(digit_results)
    logger.info(f"Digit-only OCR results: {digit_results!r}")

    # Try the Points pattern again with a fuzzier label match, then pull the
    # number from the digit-only pass which is more reliable.
    if re.search(r"[Pp].{0,3}[Nn][Tt][Ss]", text):
        numbers = re.findall(r"-?[\d,]{3,}", digit_text)
        if numbers:
            return int(max(numbers, key=_digit_count).replace(",", ""))

    # No "Points:" label detected — faction has no reputation value on screen.
    # Return None so callers can distinguish "no points" from a read failure.
    logger.info(
        "_extract_points: 'Points' label not found — faction likely has no reputation"
    )
    return None


def analyze_screenshot(window, image_path, factions_dao):
    from app.screen_processing.screen_capture import ScreenCapture

    sc = ScreenCapture()

    sc.navigate_to_home_screen(
        window,
        target_templates=["Faction Store Header.jpg"],
        nav_buttons=[
            "TopLeftBackArrow.jpg",
            "collect.jpg",
            "Done.jpg",
            "Factions Button.jpg",
            "Factions Button2.jpg",
        ],
        busy_templates=["STFC busy screen.jpg"],
    )

    return click_all_faction_buttons(factions_dao, window, sc)


def _snippet_filename_for_faction(faction):
    """Return the expected RepButton snippet filename for a faction dict.

    Convention: RepButton{code.capitalize()}.jpg
    e.g. faction code 'fed' -> 'RepButtonFed.jpg'
    """
    code = (faction.get("code") or "").strip()
    if not code:
        return None
    return f"RepButton{code.capitalize()}.jpg"


def click_faction_button(faction, img, screen_offset=(0, 0)):
    """Find and click a single faction's sidebar button using template matching.

    Uses a RepButton snippet named after the faction's code field
    (e.g. code='fed' -> RepButtonFed.jpg).  If no snippet exists for
    this faction a warning is logged and False is returned so callers
    know they need to supply the image.

    Returns True if the button was found and clicked, False otherwise.
    """
    filename = _snippet_filename_for_faction(faction)
    if filename is None:
        logger.warning(
            f"click_faction_button: faction '{faction.get('name')}' has no code — cannot determine snippet filename"
        )
        return False

    # snippet_path = os.path.normpath(os.path.join(_SNIPPETS_DIR, filename))
    # if not os.path.isfile(snippet_path):
    #     logger.warning(
    #         f"click_faction_button: no snippet found for '{faction.get('name')}' "
    #         f"(expected {filename} in {_SNIPPETS_DIR})"
    #     )
    #     return False

    clicked = click_button_if_visible(filename, img, screen_offset)
    if clicked:
        logger.debug(
            f"click_faction_button: clicked '{faction.get('name')}' using {filename}"
        )
    else:
        logger.warning(
            f"click_faction_button: snippet {filename} exists but was not matched on screen for '{faction.get('name')}'"
        )
    return clicked


def _wait_for_faction_active(
    sc, window, faction, factions, max_retries=8, retry_delay=0.10
):
    """Poll until the expected faction is the highlighted one, then return the screenshot path.

    After clicking a faction button the UI may take a moment to update.  This
    function captures a fresh screenshot on each attempt and calls
    _find_highlighted_faction to check whether the desired faction is now active.
    Returns the path of the first screenshot where the faction is confirmed, or
    the last screenshot taken if the retries are exhausted.
    """
    name = faction.get("name", "<unknown>")
    for attempt in range(1, max_retries + 1):
        image_path = sc.capture_window(window)
        highlighted = _find_highlighted_faction(image_path, factions)
        if highlighted == name:
            logger.debug(
                f"_wait_for_faction_active: '{name}' confirmed active after {attempt} attempt(s)"
            )
            return image_path
        logger.debug(
            f"_wait_for_faction_active: attempt {attempt}/{max_retries} — "
            f"highlighted='{highlighted}', waiting {retry_delay}s"
        )
        time.sleep(retry_delay)

    logger.warning(
        f"_wait_for_faction_active: '{name}' not confirmed after {max_retries} attempts — proceeding anyway"
    )
    return None  # sc.capture_window(window)


def click_all_faction_buttons(factions_dao, window, sc):
    """Iterate through factions, capture the screen, and click each faction's sidebar button.

    Starts by clicking the Rogue button to establish a known scroll position, then
    iterates all factions in display_order.

    Args:
        factions_dao: FactionsDAO instance used to query all factions from the DB
        window:       STFC window object (from ScreenCapture.get_stfc_window())
        sc:           ScreenCapture instance (used to take fresh screenshots)

    Returns:
        list of dicts: [{"faction": name, "clicked": bool, "points": int|None, "error": str|None}, ...]

    Factions whose RepButton snippet is missing are skipped with a warning — crop a
    snippet from Faction Buttons.jpg and save it as RepButton{code}.jpg to add support.
    Factions with no reputation value will have points=None in their result.
    """
    screen_offset = (window.left, window.top)
    results = []
    factions = factions_dao.get_all_factions()

    # # Click Rogue button first to establish a known scroll position in the sidebar.
    # start_path = sc.capture_window(window)
    # start_img = cv2.imread(start_path)
    # if start_img is not None:
    #     if click_button_if_visible("RepButtonRog.jpg", start_img, screen_offset):
    #         logger.debug(
    #             "click_all_faction_buttons: clicked Rogue to establish start position"
    #         )
    #         time.sleep(1.0)
    #     else:
    #         logger.warning(
    #             "click_all_faction_buttons: Rogue button not visible, proceeding from current position"
    #         )
    # else:
    #     logger.warning(
    #         "click_all_faction_buttons: could not capture initial screenshot for Rogue click"
    #     )

    for faction in factions:
        name = faction.get("name", "<unknown>")
        logger.info(f"click_all_faction_buttons: selecting '{name}'")

        image_path = sc.capture_window(window)
        img = cv2.imread(image_path)
        if img is None:
            logger.error(
                f"click_all_faction_buttons: could not read screenshot for '{name}'"
            )
            results.append(
                {
                    "faction": name,
                    "clicked": False,
                    "points": None,
                    "error": "screenshot failed",
                }
            )
            continue

        clicked = click_faction_button(faction, img, screen_offset)

        points = None
        if clicked:
            points_path = _wait_for_faction_active(
                sc, window, faction, factions, max_retries=8, retry_delay=0.25
            )
            points = _extract_points(points_path)
            if points is None:
                logger.info(
                    f"click_all_faction_buttons: '{name}' has no reputation — skipping"
                )
            else:
                logger.info(f"click_all_faction_buttons: '{name}' points = {points:,}")

        results.append(
            {"faction": name, "clicked": clicked, "points": points, "error": None}
        )

    return results


# if __name__ == "__main__":
#     import sys
#
#     path = sys.argv[1] if len(sys.argv) > 1 else "screenshot.png"
#     analyze_screenshot(path)
