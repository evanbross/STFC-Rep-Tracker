import logging
import os
import time

import cv2
import numpy as np

from app.screen_processing.screen_capture import (
    click_button_if_visible,
    get_reader,
    is_button_visible,
    is_template_visible,
)

logger = logging.getLogger(__name__)


def _is_faction_store_screen(img):
    """Return True if the top-left back-arrow is visible in img (numpy BGR array)."""
    return is_button_visible("Faction Store Header.jpg", img) is not None


def _find_highlighted_faction(image_path, faction_names):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    height, width = img.shape[:2]

    # The faction list is on the left portion of the screen
    # Crop to just the faction list area (roughly left 45% of image)
    faction_panel = img[:, : int(width * 0.45)]

    # Convert to grayscale for brightness analysis
    gray = cv2.cvtColor(faction_panel, cv2.COLOR_BGR2GRAY)

    # Divide into rows (one per faction)
    num_factions = len(faction_names)
    row_height = height // num_factions

    best_faction = None
    best_brightness = -1

    for i, faction in enumerate(faction_names):
        y1 = i * row_height
        y2 = y1 + row_height
        row = gray[y1:y2, :]
        avg_brightness = np.mean(row)

        if avg_brightness > best_brightness:
            best_brightness = avg_brightness
            best_faction = faction

    return best_faction


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
    logger.info(f"Raw OCR results from points region: {results!r}")
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
    screen_offset = (window.left, window.top)
    logger.info(f"Screen offset: {screen_offset}")
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    from app.screen_processing.screen_capture import ScreenCapture

    sc = ScreenCapture()

    max_retries = 5
    for attempt in range(max_retries):
        if _is_faction_store_screen(img):
            break

        logger.info(
            f"Not on Faction Store screen (attempt {attempt + 1}/{max_retries}). Looking for known buttons"
        )

        if any(
            [
                click_button_if_visible("TopLeftBackArrow.jpg", img, screen_offset),
                click_button_if_visible("collect.jpg", img, screen_offset),
                click_button_if_visible("Done.jpg", img, screen_offset),
                click_button_if_visible("Factions Button.jpg", img, screen_offset),
                click_button_if_visible("Factions Button2.jpg", img, screen_offset),
                is_button_visible(
                    "STFC busy screen.jpg", img, screen_offset, lambda: time.sleep(1.0)
                ),
            ]
        ):
            image_path = sc.capture_window(window)
            img = cv2.imread(image_path)
            logger.info(f"Captured fresh screenshot: {image_path}")
        else:
            raise RuntimeError(
                "Not on the reputation page, can't identify any known buttons"
            )
    else:
        raise RuntimeError(
            f"Could not reach Faction Store screen after {max_retries} attempts."
        )

    img = cv2.imread(image_path)
    if not is_template_visible("Faction Store Header.jpg", img):
        raise RuntimeError("Could not verify Faction Store screen — header not found.")

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
        logger.info(
            f"click_faction_button: clicked '{faction.get('name')}' using {filename}"
        )
    else:
        logger.warning(
            f"click_faction_button: snippet {filename} exists but was not matched on screen for '{faction.get('name')}'"
        )
    return clicked


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

    # Click Rogue button first to establish a known scroll position in the sidebar.
    start_path = sc.capture_window(window)
    start_img = cv2.imread(start_path)
    if start_img is not None:
        if click_button_if_visible("RepButtonRog.jpg", start_img, screen_offset):
            logger.info(
                "click_all_faction_buttons: clicked Rogue to establish start position"
            )
            time.sleep(1.4)
        else:
            logger.warning(
                "click_all_faction_buttons: Rogue button not visible, proceeding from current position"
            )
    else:
        logger.warning(
            "click_all_faction_buttons: could not capture initial screenshot for Rogue click"
        )

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
            time.sleep(1.4)  # let the UI finish updating before the next capture
            points_path = sc.capture_window(window)
            points = _extract_points(points_path)
            if points is None:
                # No "Points:" label on screen — faction has no reputation yet.
                points = 0
                logger.info(
                    f"click_all_faction_buttons: '{name}' has no reputation — recording 0"
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
