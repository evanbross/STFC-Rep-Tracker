import logging
import re
import time
from datetime import datetime, timedelta

from app.app_config import capture_cfg
from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    get_reader,
    is_button_visible,
    match_template,
    wait_and_click_any,
)

logger = logging.getLogger(__name__)


def _parse_time_remaining(text):
    """Parse a countdown string like '2d 4h 30m', '4h 6m', or '45m' into a timedelta.

    Returns None if no time components are found.
    Common OCR substitutions handled: 'O'→0, 'l'/'I'→1, 'S'→5.
    """
    # Normalise common OCR character substitutions in the digits
    normalised = text
    normalised = re.sub(r'(?<!\w)[Oo](?=\s*[dhm])', '0', normalised)

    days = hours = minutes = 0
    d = re.search(r'(\d+)\s*d', normalised, re.IGNORECASE)
    h = re.search(r'(\d+)\s*h', normalised, re.IGNORECASE)
    m = re.search(r'(\d+)\s*m(?!s)', normalised, re.IGNORECASE)  # exclude 'ms'
    if d:
        days = int(d.group(1))
    if h:
        hours = int(h.group(1))
    if m:
        minutes = int(m.group(1))
    if days == 0 and hours == 0 and minutes == 0:
        return None
    return timedelta(days=days, hours=hours, minutes=minutes)


def _is_time_string(text):
    """Return True if text looks like a countdown timer (digits + d/h/m unit)."""
    return bool(re.search(r'\d+\s*[dhm]', text, re.IGNORECASE))


def _bbox_top_y(bbox):
    """Return the y-coordinate of the top edge of an EasyOCR bounding box."""
    # EasyOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    return bbox[0][1]


def _bbox_center_x(bbox):
    return (bbox[0][0] + bbox[1][0]) / 2


_TERRITORY_PAGE_TEMPLATES = ["Alliance Territory 1.jpg", "Alliance Territory 2.jpg"]
_ZONE_SLOTS_TEMPLATES = ["Alliance Territory Zone Slots 1.jpg", "Alliance Territory Zone Slots 2.jpg"]


def _find_zone_slots_bottom(img):
    """Return the y-coordinate of the bottom edge of the Zone Slots header in img.

    Tries each template in _ZONE_SLOTS_TEMPLATES.  If none is found, falls back to
    the territory.title_bar_crop_px setting so OCR still avoids the title bar.
    """
    for filename in _ZONE_SLOTS_TEMPLATES:
        try:
            result = match_template(filename, img)
            if result is None:
                continue
            template, max_val, max_loc = result
            threshold = capture_cfg("button_match_threshold", default=0.85)
            if max_val >= threshold:
                bottom_y = max_loc[1] + template.shape[0]
                logger.debug(
                    "Zone Slots header '%s' found at y=%d (score=%.2f), cropping above y=%d",
                    filename, max_loc[1], max_val, bottom_y,
                )
                return bottom_y
        except FileNotFoundError:
            logger.debug("Zone Slots template not found on disk: %s", filename)

    fallback = capture_cfg("territory", "title_bar_crop_px", default=40)
    logger.warning(
        "Zone Slots header not detected — falling back to %d px title-bar crop", fallback
    )
    return fallback


def _extract_territory_systems(img):
    """Run OCR on the territory screen image and return parsed system/timer pairs.

    Crops the image above the "Alliance Territory Zone Slots" header so that only
    the system list is passed to OCR.  Falls back to a configurable pixel offset if
    the header template is not found.

    EasyOCR returns (bbox, text, confidence) tuples when detail=1.  We sort all
    results top-to-bottom and pair each non-time label with the nearest time string
    directly below it (within a vertical tolerance).

    Returns a list of dicts:
        [{"name": str, "time_remaining": str, "event_time": "YYYY-MM-DD HH:MM"}, ...]
    """
    crop_y = _find_zone_slots_bottom(img)
    img = img[crop_y:, :]
    logger.debug("Territory OCR crop: top %d px removed", crop_y)

    reader = get_reader()
    raw = reader.readtext(img, detail=1)
    if not raw:
        logger.warning("OCR returned no results from territory screen")
        return []

    logger.debug(
        "Territory OCR raw: %s",
        [(t, f"{c:.2f}") for _, t, c in raw],
    )

    # Discard very low-confidence results and empty strings
    results = [
        (bbox, text.strip(), conf)
        for bbox, text, conf in raw
        if conf >= 0.3 and text.strip()
    ]

    # Sort top-to-bottom
    results.sort(key=lambda r: _bbox_top_y(r[0]))

    now = datetime.now()
    systems = []
    consumed = set()

    for i, (bbox, text, conf) in enumerate(results):
        if i in consumed:
            continue
        if _is_time_string(text):
            continue

        # This could be a system name — look for a time string below it
        name_y = _bbox_top_y(bbox)

        for j in range(i + 1, len(results)):
            if j in consumed:
                continue
            j_bbox, j_text, _ = results[j]
            j_y = _bbox_top_y(j_bbox)

            if j_y - name_y > 200:
                break  # too far below, give up

            if not _is_time_string(j_text):
                continue

            delta = _parse_time_remaining(j_text)
            event_time = (now + delta).strftime("%Y-%m-%d %H:%M") if delta else None
            systems.append(
                {
                    "name": text,
                    "time_remaining": j_text,
                    "event_time": event_time,
                }
            )
            consumed.add(i)
            consumed.add(j)
            logger.info("Territory system: '%s' — %s → %s", text, j_text, event_time)
            break

    if not systems:
        logger.warning("No territory systems with timers found in OCR output")
    return systems


class TerritoryCaptureOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()

    def navigate_to_territory_capture(self):
        """Navigate to home → Alliance → Territory, then OCR the takeover timers.

        Returns:
          {"success": True, "systems": [...]} on success, where each system is:
            {"name": str, "time_remaining": str, "event_time": "YYYY-MM-DD HH:MM"}
          {"error": str} on failure.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(str(e))
            return {"error": str(e)}

        screen_offset = (window.left, window.top)

        # Check if we're already on the Alliance Territory page
        img = self.sc.capture(window)
        if img is not None and is_button_visible(_TERRITORY_PAGE_TEMPLATES, img):
            logger.info("already on Alliance Territory page — skipping navigation")
        else:
            try:
                self.sc.navigate_to_home_screen(window)
            except RuntimeError as e:
                logger.error(f"Could not reach home screen: {e}")
                return {"error": str(e)}

            img = self.sc.capture(window)
            if not click_button_if_visible(
                ["Alliance Button 1.jpg", "Alliance Button 2.jpg"], img, screen_offset
            ):
                logger.error("Alliance Button not found on home screen")
                return {
                    "error": "Alliance Button not found — add Alliance Button 1.jpg to app/screen_snippets/"
                }
            logger.info("clicked Alliance Button")

            if not wait_and_click_any(
                ["Territory Button 1.jpg", "Territory Button 2.jpg"],
                self.sc,
                window,
                screen_offset,
            ):
                logger.error("Territory Button not found after clicking Alliance")
                return {
                    "error": "Territory Button not found — add Territory Button 1.jpg to app/screen_snippets/"
                }
            logger.info("clicked Territory Button")

            # Wait for the territory list to finish loading
            time.sleep(1.5)

        img = self.sc.capture(window)
        if img is None:
            return {"error": "Could not capture territory screen after navigation"}

        systems = _extract_territory_systems(img)
        return {"success": True, "systems": systems}
