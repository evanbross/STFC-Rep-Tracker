# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Pure row geometry and name/timer pairing for the Alliance Territory screen (R12).

Extracted from process_territory_capture.py so it can be tested without
OpenCV or EasyOCR. Nothing here reads settings: callers pass the tunables in.

A Box is (x, y, w, h) as template matching returns it. An OcrResult is one
EasyOCR readtext(detail=1) entry, (bbox, text, confidence), where bbox is
[[x1, y1], [x2, y1], [x2, y2], [x1, y2]].
"""
import logging
from datetime import datetime
from typing import Any

from app.screen_processing.ocr_text import is_time_string, parse_time_remaining

logger = logging.getLogger(__name__)

Box = tuple[int, int, int, int]
OcrResult = tuple[Any, str, float]
TerritoryRow = dict[str, str | None]


def territory_row(name: str, time_remaining: str, now: datetime) -> TerritoryRow:
    """The API row for one system: its takeover time is now plus the parsed countdown."""
    delta = parse_time_remaining(time_remaining)
    event_time = (now + delta).strftime("%Y-%m-%d %H:%M") if delta else None
    return {"name": name, "time_remaining": time_remaining, "event_time": event_time}


def name_and_timer(tokens: list[str]) -> tuple[str | None, str | None]:
    """The first non-timer token (the system name) and the first timer token."""
    name = next((t for t in tokens if not is_time_string(t)), None)
    timer = next((t for t in tokens if is_time_string(t)), None)
    return name, timer


def first_timer(tokens: list[str]) -> str | None:
    return next((t for t in tokens if is_time_string(t)), None)


def estimate_row_height(portraits: list[Box]) -> float:
    """Average spacing between portraits (sorted top to bottom).

    With a single portrait, twice its height is the rough estimate.
    """
    if len(portraits) >= 2:
        spacings = [portraits[i + 1][1] - portraits[i][1] for i in range(len(portraits) - 1)]
        return sum(spacings) / len(spacings)
    return portraits[0][3] * 2


def row_strip_regions(
    portraits: list[Box],
    takeover_labels: list[Box],
    img_w: int,
    img_h: int,
    *,
    max_row_height_px: int,
    name_timer_height_frac: float,
) -> list[tuple[int, tuple[int, int, int, int]]]:
    """One (portrait_y, (x1, y1, x2, y2)) strip per portrait, top to bottom.

    Each strip starts right of the portrait and holds only the system name and
    timer. It ends just below that row's Next Takeover label. When no label is
    found within max_row_height_px of the portrait, it ends at
    name_timer_height_frac of the row height estimated from portrait spacing,
    which excludes the badge labels further down and scales with resolution.
    """
    portraits = sorted(portraits, key=lambda m: m[1])
    labels = sorted(takeover_labels, key=lambda m: m[1])
    row_height = estimate_row_height(portraits)

    strips: list[tuple[int, tuple[int, int, int, int]]] = []
    for px, py, pw, _ in portraits:
        label = next((m for m in labels if py <= m[1] < py + max_row_height_px), None)
        if label is not None:
            _, label_y, _, label_h = label
            y2 = min(img_h, label_y + label_h + 4)
        else:
            y2 = min(img_h, py + int(row_height * name_timer_height_frac))
        region = (px + pw, py, img_w, y2)
        if region[2] > region[0] and region[3] > region[1]:
            strips.append((py, region))
    return strips


def timer_strip_rows(name_box: Box, img_h: int, timer_strip_frac: float) -> tuple[int, int]:
    """Rows (y1, y2) of the timer line under a matched system-name snippet.

    The strip is timer_strip_frac name-heights tall, so it scales with resolution.
    """
    _, y, _, h = name_box
    return y + h, min(img_h, y + int(h * (1 + timer_strip_frac)))


def _top_y(bbox: Any) -> float:
    return bbox[0][1]


def pair_full_image_results(
    raw: list[OcrResult],
    now: datetime,
    *,
    min_conf: float,
    pair_max_gap_px: float,
    emblem_skip_px: float,
) -> list[TerritoryRow]:
    """Pair system names with timers from whole-screen OCR (the no-landmark fallback).

    Results are walked top to bottom. A name pairs with the first unused timer
    below it, within pair_max_gap_px. A non-timer token that sits less than
    emblem_skip_px below an earlier timer is a badge label, not a name.
    """
    results = sorted(
        ((bbox, text.strip(), conf) for bbox, text, conf in raw if conf >= min_conf and text.strip()),
        key=lambda r: _top_y(r[0]),
    )
    rows: list[TerritoryRow] = []
    consumed: set[int] = set()

    for i, (bbox, text, _) in enumerate(results):
        if i in consumed or is_time_string(text):
            continue
        name_y = _top_y(bbox)
        if any(
            is_time_string(results[k][1]) and 0 < (name_y - _top_y(results[k][0])) <= emblem_skip_px
            for k in range(i)
        ):
            logger.debug("Skipping '%s': within %.0f px below a timer (badge label)", text, emblem_skip_px)
            continue

        for j in range(i + 1, len(results)):
            if j in consumed:
                continue
            j_bbox, j_text, _ = results[j]
            if _top_y(j_bbox) - name_y > pair_max_gap_px:
                break
            if not is_time_string(j_text):
                continue
            rows.append(territory_row(text, j_text, now))
            consumed.update((i, j))
            break
    return rows
