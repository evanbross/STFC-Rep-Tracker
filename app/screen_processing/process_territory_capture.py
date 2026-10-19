# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
import re
from datetime import datetime, timedelta, UTC

import cv2
import numpy as np

from app.app_config import capture_cfg
from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    find_all_template_matches,
    get_reader,
    is_button_visible,
    match_template,
    wait_and_click_any,
    wait_for_any_template,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template filename constants
# ---------------------------------------------------------------------------
_TERRITORY_PAGE_TEMPLATES = [
    "Alliance Territory Header 1.jpg",
    "Alliance Territory Header 2.jpg",
]
_ZONE_SLOTS_TEMPLATES = [
    "Alliance Territory Zone Slots 1.jpg",
    "Alliance Territory Zone Slots 2.jpg",
]
_PORTRAIT_TEMPLATES = ["Territory Portrait 1.jpg", "Territory Portrait 2.jpg"]
_NEXT_TAKEOVER_TEMPLATES = [
    "Territory Next Takeover 1.jpg",
    "Territory Next Takeover 2.jpg",
]
_GREEN_FLAG_TEMPLATES = ["Territory Green Flag 1.jpg"]

# Templates that signal the territory page is fully loaded with live data.
_LOAD_READY_TEMPLATES = _NEXT_TAKEOVER_TEMPLATES + _GREEN_FLAG_TEMPLATES


# ---------------------------------------------------------------------------
# Time string parsing helpers
# ---------------------------------------------------------------------------


# Maps single OCR-garbled characters to their most likely digit equivalents.
# Only applied within digit-like sequences immediately preceding a time unit (d/h/m)
# — see _normalize_ocr_digits below.
_OCR_DIGIT_MAP: dict[str, str] = {
    "O": "0",
    "o": "0",
    "A": "0",
    "a": "0",
    "I": "1",
    "l": "1",
    "i": "1",
    "T": "1",
    "Z": "2",
    "z": "2",
    "S": "5",
}


def _normalize_ocr_digits(text: str) -> str:
    """Replace OCR lookalike characters with digits in numeric sequences.

    Scans the string for runs of digits and known OCR lookalikes that are
    immediately followed by a time unit (d, h, m) and substitutes the whole
    run at once.  This handles multi-character garbles like 'ISh' → '15h'
    (where the old per-character regex approach failed because neither I nor S
    was adjacent to a digit when checked individually).

    Characters not in _OCR_DIGIT_MAP (e.g. 'F') are left as-is — they produce
    no digit match and the time component will be treated as absent.
    """
    result: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in _OCR_DIGIT_MAP or ch.isdigit():
            j = i
            while j < len(text) and (text[j] in _OCR_DIGIT_MAP or text[j].isdigit()):
                j += 1
            if j < len(text) and text[j].lower() in "dhm":
                result.extend(_OCR_DIGIT_MAP.get(c, c) for c in text[i:j])
                i = j
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def _parse_time_remaining(text: str) -> timedelta | None:
    """Parse a countdown string like '2d 4h 30m', '4h 6m', or '45m' into a timedelta.

    Returns None if no time components are found.  OCR lookalike characters
    are normalised via _normalize_ocr_digits before parsing.
    """
    normalised = _normalize_ocr_digits(text)
    if normalised != text:
        logger.debug("OCR time normalised: %r → %r", text, normalised)

    days = hours = minutes = 0
    d = re.search(r"(\d+)\s*d", normalised, re.IGNORECASE)
    h = re.search(r"(\d+)\s*h", normalised, re.IGNORECASE)
    m = re.search(r"(\d+)\s*m(?!s)", normalised, re.IGNORECASE)  # exclude 'ms'
    if d:
        days = int(d.group(1))
    if h:
        hours = int(h.group(1))
    if m:
        minutes = int(m.group(1))
    if days == 0 and hours == 0 and minutes == 0:
        return None
    return timedelta(days=days, hours=hours, minutes=minutes)


def _is_time_string(text: str) -> bool:
    """Return True if text looks like a countdown timer (digits + d/h/m unit)."""
    return bool(re.search(r"\d+\s*[dhm]", text, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Image coordinate helpers
# ---------------------------------------------------------------------------


def _bbox_top_y(bbox) -> float:
    """Return the y-coordinate of the top edge of an EasyOCR bounding box."""
    # EasyOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    return bbox[0][1]


def _bbox_center_x(bbox) -> float:
    return (bbox[0][0] + bbox[1][0]) / 2


# ---------------------------------------------------------------------------
# Zone Slots header detection (used to crop the top of the territory screen)
# ---------------------------------------------------------------------------


def _find_zone_slots_bottom(img: np.ndarray) -> int:
    """Return the y-coordinate of the bottom edge of the Zone Slots header in img.

    Tries each template in _ZONE_SLOTS_TEMPLATES.  Falls back to
    territory.title_bar_crop_px if none are found.
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
                    filename,
                    max_loc[1],
                    max_val,
                    bottom_y,
                )
                return bottom_y
        except FileNotFoundError:
            logger.debug("Zone Slots template not found on disk: %s", filename)

    fallback = capture_cfg("territory", "title_bar_crop_px", default=40)
    logger.warning(
        "Zone Slots header not detected — falling back to %d px title-bar crop",
        fallback,
    )
    return fallback


# ---------------------------------------------------------------------------
# Landmark-based row detection
# ---------------------------------------------------------------------------


def _find_row_strips(img: np.ndarray) -> list[tuple[np.ndarray, int]]:
    """Locate each territory row using portrait + Next Takeover label landmarks.

    For each portrait found, locates the matching Next Takeover label in the
    same row and returns a tight crop containing only the system name and timer
    text — badge/emblem labels below the timer are excluded entirely.

    When the Next Takeover template is not available or doesn't match, falls back
    to using portrait-to-portrait spacing to derive strip height automatically.
    This spacing scales with display resolution, so the fallback is still
    resolution-independent.

    Returns a list of (strip_image, portrait_y) sorted top-to-bottom.
    Returns an empty list if portrait templates are not on disk or not detected.
    """
    threshold = capture_cfg("button_match_threshold", default=0.85)
    nt_threshold = capture_cfg("territory", "next_takeover_threshold", default=0.75)
    max_row_height_px = capture_cfg("territory", "max_row_height_px", default=300)
    # Fraction of row height to include in fallback strips.
    # Timer sits at ~24% of row height; badges start at ~70%.  0.50 is a safe midpoint.
    name_timer_height_frac = capture_cfg(
        "territory", "name_timer_height_frac", default=0.50
    )

    portraits: list[tuple[int, int, int, int]] = []
    for tmpl in _PORTRAIT_TEMPLATES:
        try:
            portraits.extend(find_all_template_matches(tmpl, img, threshold))
        except FileNotFoundError:
            logger.debug("Portrait template not found on disk: %s", tmpl)
    if not portraits:
        return []
    portraits.sort(key=lambda m: m[1])
    logger.debug(
        "Found %d portrait(s) at y=%s", len(portraits), [p[1] for p in portraits]
    )

    # Compute average row height from portrait spacing (resolution-independent fallback unit)
    if len(portraits) >= 2:
        spacings = [
            portraits[i + 1][1] - portraits[i][1] for i in range(len(portraits) - 1)
        ]
        row_height = sum(spacings) / len(spacings)
    else:
        row_height = (
            portraits[0][3] * 2
        )  # single portrait — rough estimate from template height
    logger.debug("Estimated row height from portrait spacing: %.0f px", row_height)

    nt_matches: list[tuple[int, int, int, int]] = []
    for tmpl in _NEXT_TAKEOVER_TEMPLATES:
        try:
            found = find_all_template_matches(tmpl, img, nt_threshold)
            nt_matches.extend(found)
            logger.debug(
                "Next Takeover template '%s': %d match(es) at threshold %.2f",
                tmpl,
                len(found),
                nt_threshold,
            )
        except FileNotFoundError:
            logger.debug("Next Takeover template not found on disk: %s", tmpl)
    nt_matches.sort(key=lambda m: m[1])

    img_h, img_w = img.shape[:2]
    strips: list[tuple[np.ndarray, int]] = []

    for px, py, pw, ph in portraits:
        nt = next(
            (m for m in nt_matches if py <= m[1] < py + max_row_height_px),
            None,
        )

        strip_x = px + pw
        if nt is not None:
            _, nty, _, nth = nt
            strip_y2 = min(img_h, nty + nth + 4)
            logger.debug(
                "Row y=%d: using Next Takeover label at y=%d, strip_y2=%d",
                py,
                nty,
                strip_y2,
            )
        else:
            # Derive strip height from portrait spacing — catches name + timer, excludes badges
            strip_y2 = min(img_h, py + int(row_height * name_timer_height_frac))
            logger.debug(
                "Row y=%d: Next Takeover not found, fallback strip_y2=%d (%.0f%% of %.0f px row height)",
                py,
                strip_y2,
                name_timer_height_frac * 100,
                row_height,
            )

        strip = img[py:strip_y2, strip_x:img_w]
        if strip.size > 0:
            strips.append((strip, py))

    return strips


# ---------------------------------------------------------------------------
# OCR on landmark-derived strips
# ---------------------------------------------------------------------------


def _ocr_strips(strips: list[tuple[np.ndarray, int]]) -> list[dict]:
    """OCR each row strip and extract (name, timer) pairs.

    Each strip is upscaled before OCR for better accuracy on small text.
    Because each strip contains only one system name and one timer line,
    extraction is straightforward: find the first non-time token (name)
    and the first time token (timer).
    """
    reader = get_reader()
    scale = capture_cfg("ocr", "scale_factor", default=3)
    min_conf = capture_cfg("territory", "ocr_min_confidence", default=0.2)
    now = datetime.now(UTC)
    systems: list[dict] = []

    for strip, row_y in strips:
        sh, sw = strip.shape[:2]
        logger.info(
            "Strip row y=%d: raw size %dx%d px, upscaling x%d", row_y, sw, sh, scale
        )
        scaled = cv2.resize(
            strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
        )
        raw = reader.readtext(scaled, detail=1)
        logger.info(
            "Strip OCR row y=%d: %s",
            row_y,
            [(t, f"{c:.2f}") for _, t, c in raw],
        )

        tokens = [t.strip() for _, t, c in raw if c >= min_conf and t.strip()]
        name = next((t for t in tokens if not _is_time_string(t)), None)
        time_str = next((t for t in tokens if _is_time_string(t)), None)

        if name and time_str:
            delta = _parse_time_remaining(time_str)
            event_time = (now + delta).strftime("%Y-%m-%d %H:%M") if delta else None
            systems.append(
                {"name": name, "time_remaining": time_str, "event_time": event_time}
            )
            logger.info("Territory system: '%s' — %s → %s", name, time_str, event_time)
        else:
            logger.warning(
                "Row y=%d: could not extract name/timer (tokens=%s)", row_y, tokens
            )

    return systems


# ---------------------------------------------------------------------------
# Full-image OCR fallback
# ---------------------------------------------------------------------------


def _ocr_full_image(img: np.ndarray, img_height: int) -> list[dict]:
    """Full-image OCR fallback used when portrait landmarks are unavailable.

    Runs EasyOCR on the entire (already-cropped) territory screen, then
    filters and pairs tokens using vertical-gap heuristics to exclude
    badge/emblem labels.
    """
    reader = get_reader()
    raw = reader.readtext(img, detail=1)
    if not raw:
        logger.warning("OCR returned no results from territory screen")
        return []

    logger.info(
        "Territory OCR raw (text, conf, left_x, top_y): %s",
        [
            (t, f"{c:.2f}", f"x={bbox[0][0]:.0f}", f"y={bbox[0][1]:.0f}")
            for bbox, t, c in raw
        ],
    )

    min_conf = capture_cfg("territory", "ocr_min_confidence", default=0.2)
    pair_max_gap_px = capture_cfg("territory", "ocr_pair_max_gap_px", default=300)
    emblem_skip_frac = capture_cfg("territory", "emblem_skip_frac", default=0.15)
    emblem_skip_px = img_height * emblem_skip_frac
    logger.debug(
        "Territory emblem skip threshold: %.0f px (%.0f%% of %d px height)",
        emblem_skip_px,
        emblem_skip_frac * 100,
        img_height,
    )

    filtered_out = [(t, f"{c:.2f}") for _, t, c in raw if c < min_conf or not t.strip()]
    if filtered_out:
        logger.info("Territory OCR filtered (conf < %.2f): %s", min_conf, filtered_out)
    results = [
        (bbox, text.strip(), conf)
        for bbox, text, conf in raw
        if conf >= min_conf and text.strip()
    ]
    results.sort(key=lambda r: _bbox_top_y(r[0]))

    now = datetime.now(UTC)
    systems: list[dict] = []
    consumed: set[int] = set()

    for i, (bbox, text, conf) in enumerate(results):
        if i in consumed:
            continue
        if _is_time_string(text):
            continue

        name_y = _bbox_top_y(bbox)
        # Skip badge/emblem labels — they sit closely below their row's timer.
        if any(
            _is_time_string(results[k][1])
            and 0 < (name_y - _bbox_top_y(results[k][0])) <= emblem_skip_px
            for k in range(i)
        ):
            logger.debug(
                "Skipping '%s' — within %.0fpx (%.0f%%) below a timer (badge label)",
                text,
                emblem_skip_px,
                emblem_skip_frac * 100,
            )
            continue

        for j in range(i + 1, len(results)):
            if j in consumed:
                continue
            j_bbox, j_text, _ = results[j]
            j_y = _bbox_top_y(j_bbox)
            if j_y - name_y > pair_max_gap_px:
                break
            if not _is_time_string(j_text):
                continue
            delta = _parse_time_remaining(j_text)
            event_time = (now + delta).strftime("%Y-%m-%d %H:%M") if delta else None
            systems.append(
                {"name": text, "time_remaining": j_text, "event_time": event_time}
            )
            consumed.add(i)
            consumed.add(j)
            logger.info("Territory system: '%s' — %s → %s", text, j_text, event_time)
            break

    if not systems:
        logger.warning(
            "No territory systems with timers found in full-image OCR output"
        )
    return systems


# ---------------------------------------------------------------------------
# Name-template-based extraction (preferred)
# ---------------------------------------------------------------------------


def _extract_by_name_templates(img: np.ndarray) -> list[dict]:
    """Locate each system by its name snippet, then OCR only the timer line below it.

    For each system defined in territory.systems, finds the name template on
    screen via CV2 template matching (no name OCR needed), then OCRs a narrow
    horizontal strip immediately below the name template to read the timer.

    The timer strip height is timer_strip_frac × name_template_height, making
    it automatically resolution-independent.

    Returns an empty list if territory.systems is not configured in settings.yaml.
    """
    systems_config: list[dict] = capture_cfg("territory", "systems", default=[]) or []
    if not systems_config:
        return []

    threshold = capture_cfg("button_match_threshold", default=0.85)
    # How many name-template-heights below the name to search for the timer.
    timer_strip_frac = capture_cfg("territory", "timer_strip_frac", default=3.0)
    scale = capture_cfg("ocr", "scale_factor", default=3)
    min_conf = capture_cfg("territory", "ocr_min_confidence", default=0.2)

    reader = get_reader()
    now = datetime.now(UTC)
    img_h, img_w = img.shape[:2]
    systems: list[dict] = []

    for sys_cfg in systems_config:
        name: str = sys_cfg.get("name", "")
        templates: list[str] = sys_cfg.get("templates", [])
        found = False

        for tmpl in templates:
            try:
                matches = find_all_template_matches(tmpl, img, threshold)
            except FileNotFoundError:
                logger.debug("System name template not found on disk: %s", tmpl)
                continue

            for nx, ny, nw, nh in matches:
                # Timer line sits just below the name template.
                # Use template height as the unit so this scales with resolution.
                # Use full row width (x=0) — the timer label may not be
                # horizontally aligned with the name template.
                timer_y1 = ny + nh
                timer_y2 = min(img_h, ny + int(nh * (1 + timer_strip_frac)))
                timer_strip = img[timer_y1:timer_y2, :]

                if timer_strip.size == 0:
                    logger.warning(
                        "System '%s': timer strip is empty at y=%d", name, ny
                    )
                    continue

                logger.info(
                    "System '%s': name matched at x=%d y=%d (template %dx%d), "
                    "OCR-ing timer strip y=%d–%d (full width)",
                    name,
                    nx,
                    ny,
                    nw,
                    nh,
                    timer_y1,
                    timer_y2,
                )
                scaled = cv2.resize(
                    timer_strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
                )
                # Restrict OCR to the characters that can appear in a timer
                # (DDd HHh format).  The model maps each glyph to the nearest
                # allowed character, so I→1, O→0, S→5 etc. happen at inference
                # time rather than in post-processing.
                raw = reader.readtext(
                    scaled, detail=1, allowlist="0123456789dhm "
                )
                logger.info(
                    "Timer strip OCR for '%s': %s",
                    name,
                    [(t, f"{c:.2f}") for _, t, c in raw],
                )

                tokens = [t.strip() for _, t, c in raw if c >= min_conf and t.strip()]
                time_str = next((t for t in tokens if _is_time_string(t)), None)

                if time_str:
                    delta = _parse_time_remaining(time_str)
                    event_time = (
                        (now + delta).strftime("%Y-%m-%d %H:%M") if delta else None
                    )
                    systems.append(
                        {
                            "name": name,
                            "time_remaining": time_str,
                            "event_time": event_time,
                        }
                    )
                    logger.info(
                        "Territory system: '%s' — %s → %s", name, time_str, event_time
                    )
                    found = True
                    break
                else:
                    logger.warning(
                        "System '%s': no timer found in strip (tokens=%s)", name, tokens
                    )

            if found:
                break

    return systems


# ---------------------------------------------------------------------------
# Main entry point for screen extraction
# ---------------------------------------------------------------------------


def _extract_territory_systems(img: np.ndarray) -> list[dict]:
    """Run OCR on the territory screen and return parsed system/timer pairs.

    Priority order:
      1. Name-template matching — finds each system by its name snippet and
         OCRs only the narrow timer strip below it.  Requires territory.systems
         to be configured in settings.yaml.
      2. Portrait-landmark strips — uses portrait + Next Takeover templates to
         crop per-row strips, then OCRs each strip.
      3. Full-image OCR fallback — runs EasyOCR on the whole screen and uses
         vertical-gap heuristics to filter badge labels.

    Returns a list of dicts:
        [{"name": str, "time_remaining": str, "event_time": "YYYY-MM-DD HH:MM"}, ...]
    """
    crop_y = _find_zone_slots_bottom(img)
    img = img[crop_y:, :]
    img_height = img.shape[0]
    logger.debug(
        "Territory OCR crop: top %d px removed, height %d px", crop_y, img_height
    )

    systems = _extract_by_name_templates(img)
    if systems:
        logger.info("Name-template extraction: found %d system(s)", len(systems))
        return systems

    strips = _find_row_strips(img)
    if strips:
        logger.info("Portrait-landmark OCR: %d row strip(s) found", len(strips))
        return _ocr_strips(strips)

    logger.warning("No landmarks found — falling back to full-image OCR")
    return _ocr_full_image(img, img_height)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TerritoryCaptureOrchestrator:
    def __init__(self) -> None:
        self.sc = ScreenCapture()

    def navigate_to_territory_capture(self) -> dict:
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

        # Navigate to the territory page if not already there.
        # Use multiple visual indicators so the check works even when some
        # snippet files are missing: Alliance Territory header → portraits → green flag.
        _on_page_templates = (
            _TERRITORY_PAGE_TEMPLATES + _PORTRAIT_TEMPLATES + _GREEN_FLAG_TEMPLATES
        )
        img = self.sc.capture(window)
        if img is not None and is_button_visible(_on_page_templates, img):
            logger.info("already on Alliance Territory page — skipping navigation")
        else:
            try:
                self.sc.navigate_to_home_screen(window)
            except RuntimeError as e:
                logger.error("Could not reach home screen: %s", e)
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

        # Wait for the page to finish loading.
        # Next Takeover labels or the green flag signal that live timer data is visible.
        ocr_retries = capture_cfg("territory", "ocr_retries", default=4)
        ocr_retry_delay = capture_cfg("territory", "ocr_retry_delay", default=1.0)
        _, img = wait_for_any_template(
            _LOAD_READY_TEMPLATES,
            self.sc,
            window,
            max_retries=ocr_retries,
            delay=ocr_retry_delay,
        )
        if img is None:
            # Load-ready templates not configured or not found — capture fresh
            logger.warning(
                "Load-ready templates not detected after %d attempts — capturing anyway",
                ocr_retries,
            )
            img = self.sc.capture(window)
        if img is None:
            return {"error": "Could not capture territory screen"}

        systems = _extract_territory_systems(img)
        if not systems:
            return {
                "error": "Territory OCR found no systems — page may not have loaded. "
                "Check that Territory Portrait and Next Takeover snippet images are configured."
            }

        try:
            from app.google_calendar import check_events_exist

            check_events_exist(systems)
        except Exception as e:
            logger.warning("Calendar check skipped: %s", e)
            for s in systems:
                s.setdefault("calendar_event", None)

        return {"success": True, "systems": systems}
