# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Pure text parsers for OCR output (no OpenCV / EasyOCR dependency).

Extracted from process_territory_capture.py and process_system_targets.py so
they can be unit-tested without importing the screen-capture stack.
"""
import logging
import re
from datetime import timedelta
from typing import Any

from app.app_config import capture_cfg

logger = logging.getLogger(__name__)


# Maps single OCR-garbled characters to their most likely digit equivalents.
# Only applied within digit-like sequences immediately preceding a time unit (d/h/m)
# — see normalize_ocr_digits below.
OCR_DIGIT_MAP: dict[str, str] = {
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


def normalize_ocr_digits(text: str) -> str:
    """Replace OCR lookalike characters with digits in numeric sequences.

    Scans the string for runs of digits and known OCR lookalikes that are
    immediately followed by a time unit (d, h, m) and substitutes the whole
    run at once.  This handles multi-character garbles like 'ISh' → '15h'
    (where the old per-character regex approach failed because neither I nor S
    was adjacent to a digit when checked individually).

    Characters not in OCR_DIGIT_MAP (e.g. 'F') are left as-is — they produce
    no digit match and the time component will be treated as absent.
    """
    result: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in OCR_DIGIT_MAP or ch.isdigit():
            j = i
            while j < len(text) and (text[j] in OCR_DIGIT_MAP or text[j].isdigit()):
                j += 1
            if j < len(text) and text[j].lower() in "dhm":
                result.extend(OCR_DIGIT_MAP.get(c, c) for c in text[i:j])
                i = j
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def parse_time_remaining(text: str) -> timedelta | None:
    """Parse a countdown string like '2d 4h 30m', '4h 6m', or '45m' into a timedelta.

    Returns None if no time components are found.  OCR lookalike characters
    are normalised via normalize_ocr_digits before parsing.
    """
    normalised = normalize_ocr_digits(text)
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


# ai: claude-opus-5-5 | 2026-11-06
def confident_tokens(raw: list[tuple[Any, str, float]], min_conf: float) -> list[str]:
    """Stripped, non-empty texts from EasyOCR readtext(detail=1) at or above min_conf, in order."""
    return [text.strip() for _, text, conf in raw if conf >= min_conf and text.strip()]


def is_time_string(text: str) -> bool:
    """Return True if text looks like a countdown timer (digits + d/h/m unit)."""
    return bool(re.search(r"\d+\s*[dhm]", text, re.IGNORECASE))


# ai: claude-sonnet-5 | 2026-09-18
def parse_name_level(tokens: list[str]) -> tuple[str | None, int | None]:
    """Split OCR tokens from a label crop into (name, level).

    Label layout, left to right: a bare level number, a ship-class glyph
    (icon, not OCR'd), a 2-4 letter class abbreviation, the ship type name,
    and an optional skull/diamond glyph (also icons, not OCR'd — see
    process_system_targets._detect_label_glyph). So only three kinds of
    text token ever show up: the level number, the short all-caps
    abbreviation, and the name itself. The abbreviation is dropped rather than kept — classification already
    keys off the icon template filename, not this text.
    """
    level: int | None = None
    name_tokens: list[str] = []
    for token in tokens:
        if level is None and re.fullmatch(r"\d{1,3}", token):
            level = int(token)
            continue
        if re.fullmatch(r"[A-Z]{2,4}", token):
            continue
        name_tokens.append(token)
    name = " ".join(name_tokens).strip() or None
    return name, level


# ai: claude-sonnet-5 | 2026-09-14
def parse_info_panel(text: str) -> dict:
    """Extract cargo resource amounts and hull/shield percentages from panel text."""
    keywords: list[str] = capture_cfg("combat", "resource_keywords", default=[]) or []
    cargo: dict[str, int] = {}
    for keyword in keywords:
        match = re.search(rf"{re.escape(keyword)}\D*([\d,]+)", text, re.IGNORECASE)
        if match:
            cargo[keyword] = int(match.group(1).replace(",", ""))

    hull_match = re.search(r"Hull\D*(\d{1,3})\s*%", text, re.IGNORECASE)
    shield_match = re.search(r"Shield\D*(\d{1,3})\s*%", text, re.IGNORECASE)
    return {
        "cargo": cargo,
        "hull_pct": int(hull_match.group(1)) if hull_match else None,
        "shield_pct": int(shield_match.group(1)) if shield_match else None,
    }
