import logging
import os
import time

import cv2
import easyocr
import numpy as np

logger = logging.getLogger(__name__)

_ocr_reader = None


def _get_reader():
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


_SNIPPETS_DIR = os.path.join(os.path.dirname(__file__), "..", "screen_snippets")
# _BACK_ARROW_TEMPLATE = os.path.join(_SNIPPETS_DIR, "Faction Store Header.jpg")

# Fraction of the image to search for the back arrow
_TOP_LEFT_FRACTION = 0.25
# Minimum match confidence (0–1) to consider the arrow present
_BUTTON_MATCH_THRESHOLD = 0.85


def _match_template(filename, img):
    """Returns (template, max_val, max_loc) or None if the file can't be loaded."""
    template_path = os.path.normpath(os.path.join(_SNIPPETS_DIR, filename))
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template image not found: {template_path}")
    template = cv2.imread(template_path)
    if template is None:
        return None
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return template, max_val, max_loc


def _is_template_visible(filename, img):
    """Return True if the template image is found in img above the match threshold."""
    if not (match := _match_template(filename, img)):
        return False
    _, max_val, _ = match
    return max_val >= _BUTTON_MATCH_THRESHOLD


def _show_reticle(x, y, duration_ms=5000, radius=20):
    """Briefly flash a crosshair reticle at absolute screen position (x, y)."""
    import threading
    import tkinter as tk

    def _run():
        root = tk.Tk()
        root.overrideredirect(True)
        root.wm_attributes("-topmost", True)
        root.wm_attributes("-transparentcolor", "black")
        root.configure(bg="black")
        size = radius * 2 + 10
        offset = size // 2
        root.geometry(f"{size}x{size}+{x - offset}+{y - offset}")
        canvas = tk.Canvas(
            root, width=size, height=size, bg="black", highlightthickness=0
        )
        canvas.pack()
        cx = cy = size // 2
        canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius, outline="red", width=2
        )
        canvas.create_line(cx - radius, cy, cx - 4, cy, fill="red", width=2)
        canvas.create_line(cx + 4, cy, cx + radius, cy, fill="red", width=2)
        canvas.create_line(cx, cy - radius, cx, cy - 4, fill="red", width=2)
        canvas.create_line(cx, cy + 4, cx, cy + radius, fill="red", width=2)
        root.after(duration_ms, root.destroy)
        root.mainloop()

    threading.Thread(target=_run, daemon=True).start()


def _is_button_visible(button_filename, img, screen_offset=(0, 0), on_found=None):
    """Returns (template, max_val, max_loc) if the button is visible in img, else None."""
    if not (match := _match_template(button_filename, img)):
        return None

    template, max_val, max_loc = match
    if max_val < _BUTTON_MATCH_THRESHOLD:
        return None

    if on_found:
        on_found()
    return match


def _click_button_if_visible(button_filename, img, screen_offset=(0, 0), on_found=None):
    """If the button template image is visible in img, click it. Returns True if clicked.

    on_found: optional callable invoked with (center_x, center_y) after the click.
    """
    if not (match := _is_button_visible(button_filename, img, screen_offset)):
        return False
    template, max_val, max_loc = match

    import pyautogui

    th, tw = template.shape[:2]
    center_x = screen_offset[0] + max_loc[0] + tw // 2
    center_y = screen_offset[1] + max_loc[1] + th // 2

    logger.info(
        f"Clicking {button_filename} button at {center_x}, {center_y}, match % {max_val:.2f}"
    )
    # _show_reticle(center_x, center_y)
    pyautogui.click(center_x, center_y)
    if on_found:
        on_found(center_x, center_y)
    return True


def _is_faction_store_screen(img):
    """Return True if the top-left back-arrow is visible in img (numpy BGR array)."""
    return _is_button_visible("Faction Store Header.jpg", img) is not None


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
    """Scale up and threshold a BGR region to improve OCR accuracy on small UI text."""
    gray = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2GRAY)
    scaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    thresh = cv2.adaptiveThreshold(
        scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )
    return thresh


def _extract_points(image_path):
    import re

    img = cv2.imread(image_path)
    height, width = img.shape[:2]

    # "Points: X,XXX" is in the top-left faction panel, not the right panel
    points_region = img[0 : int(height * 0.10), 0 : int(width * 0.22)]
    preprocessed = _preprocess_for_ocr(points_region)

    results = _get_reader().readtext(preprocessed, detail=0)
    text = " ".join(results)
    logger.debug(f"Raw OCR results from points region: {results!r}")
    logger.debug(f"Joined OCR text: {text!r}")

    # Parse out the number after "Points"
    match = re.search(r"Points[:\s]*([\d,]+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))

    # Fallback: grab any number with 3+ digits (avoids matching short noise values)
    numbers = re.findall(r"[\d,]{3,}", text)
    if numbers:
        return int(str(max(numbers, key=len)).replace(",", ""))

    return None


def analyze_screenshot(window, image_path, faction_names):
    screen_offset = (window.left, window.top)
    logger.info(f"Screen offset: {screen_offset}")
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    from app.reputation_sucker.screen_capture import ScreenCapture

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
                _click_button_if_visible("TopLeftBackArrow.jpg", img, screen_offset),
                _click_button_if_visible("collect.jpg", img, screen_offset),
                _click_button_if_visible("Done.jpg", img, screen_offset),
                _click_button_if_visible("Factions Button.jpg", img, screen_offset),
                _click_button_if_visible("Factions Button2.jpg", img, screen_offset),
                _is_button_visible(
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
    if not _is_template_visible("Faction Store Header.jpg", img):
        raise RuntimeError("Could not verify Faction Store screen — header not found.")

    faction = _find_highlighted_faction(image_path, faction_names)
    points = _extract_points(image_path)

    logger.info(f"Highlighted faction: {faction}")
    logger.info(f"Points: {points:,}" if points else "Points: Could not extract")

    return faction, points


# if __name__ == "__main__":
#     import sys
#
#     path = sys.argv[1] if len(sys.argv) > 1 else "screenshot.png"
#     analyze_screenshot(path)
