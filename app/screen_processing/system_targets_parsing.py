# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Pure geometry and candidate bookkeeping for system-target scans (R12).

Extracted from process_system_targets.py so it can be tested without OpenCV,
EasyOCR or pyautogui. Nothing here reads settings: callers read the tunables
from capture_cfg and pass them in, so a test states its inputs outright.

Coordinates are image-local pixels unless a name says "screen". A Region is
(x1, y1, x2, y2), half-open like a numpy slice img[y1:y2, x1:x2].
"""
import math
import os
import re
from collections.abc import Iterable
from typing import Any

from app.screen_processing.target_math import names_conflict, time_to_intercept

Region = tuple[int, int, int, int]
Box = tuple[int, int, int, int]  # (x, y, w, h), as template matching returns
Point = tuple[int, int]
Candidate = dict[str, Any]


def frac_region(img_w: int, img_h: int, x_frac: float, y_frac: float, w_frac: float, h_frac: float) -> Region:
    """A region given as fractions of the image size, clipped to the image."""
    x1 = int(img_w * x_frac)
    y1 = int(img_h * y_frac)
    x2 = min(img_w, x1 + int(img_w * w_frac))
    y2 = min(img_h, y1 + int(img_h * h_frac))
    return x1, y1, x2, y2


def is_empty(region: Region) -> bool:
    """True when slicing the region out of an image would give no pixels."""
    x1, y1, x2, y2 = region
    return x2 <= x1 or y2 <= y1


def label_region(icon: Box, img_w: int, *, gap_frac: float, height_frac: float, width_mult: float) -> Region:
    """The name/level label above a ship icon, sized from the icon so it scales with resolution."""
    x, y, w, h = icon
    label_h = max(1, int(h * height_frac))
    label_y2 = max(0, y - int(h * gap_frac))
    label_y1 = max(0, label_y2 - label_h)

    label_w = max(1, int(w * width_mult))
    center_x = x + w // 2
    label_x1 = max(0, center_x - label_w // 2)
    label_x2 = min(img_w, label_x1 + label_w)
    return label_x1, label_y1, label_x2, label_y2


def sample_region(icon: Box, img_w: int, img_h: int) -> Region:
    """The icon plus roughly one icon-height of label above it, for the classification screen.

    TODO: calibrate. This assumes the label sits about one icon-height above.
    """
    x, y, w, h = icon
    return max(0, x - w // 2), max(0, y - h), min(img_w, x + w + w // 2), min(img_h, y + h)


def box_center(box: Box) -> Point:
    x, y, w, h = box
    return x + w // 2, y + h // 2


def candidate_from_icon(icon: Box, type_filename: str, name: str | None, level: int | None,
                        hazard: bool, bounty: bool) -> Candidate:
    """The candidate dict scan/refresh pass around; click_x/click_y is the icon center."""
    x, y, w, h = icon
    click_x, click_y = box_center(icon)
    return {
        "x": x, "y": y, "w": w, "h": h,
        "type": type_filename,
        "click_x": click_x, "click_y": click_y,
        "name": name, "level": level,
        "hazard": hazard, "bounty": bounty,
    }


def empty_measurements() -> dict[str, Any]:
    """Cargo/hull/shield for a candidate whose info panel wasn't read. A new dict each call."""
    return {"cargo": {}, "hull_pct": None, "shield_pct": None}


def extrapolate(x: float, y: float, vx: float, vy: float, elapsed_sec: float) -> tuple[float, float]:
    """Move a point forward along its velocity (px/sec) by elapsed_sec."""
    return x + vx * elapsed_sec, y + vy * elapsed_sec


def predict_position(candidate: Candidate, elapsed_sec: float) -> tuple[float, float]:
    """Where a tracked candidate's icon center should be elapsed_sec after its frame."""
    return extrapolate(candidate["click_x"], candidate["click_y"], candidate["vx"], candidate["vy"], elapsed_sec)


def nearest_within(points: Iterable[Point], x: float, y: float, max_dist: float) -> Point | None:
    """The point closest to (x, y), if it is within max_dist; ties keep the first seen."""
    best: Point | None = None
    best_dist = float("inf")
    for point in points:
        dist = math.hypot(point[0] - x, point[1] - y)
        if dist <= max_dist and dist < best_dist:
            best, best_dist = point, dist
    return best


def filter_players(candidates: list[Candidate], player_name_pattern: str) -> list[Candidate]:
    """Drop candidates whose name matches the player pattern (e.g. an "[ALLY]" tag).

    Candidates with no name (OCR failure) are kept: inspecting them by click
    is a better signal than a missing label.
    """
    return [c for c in candidates if not (c["name"] and re.search(player_name_pattern, c["name"]))]


def default_display_name(type_filename: str) -> str:
    """Title-case a template filename: hostile_ship-battleship_2.png -> Hostile Ship Battleship 2."""
    stem = os.path.splitext(type_filename)[0]
    return re.sub(r"[_\-]+", " ", stem).strip().title()


def approved_candidates(candidates: list[Candidate], type_rows: list[dict[str, Any]]) -> list[Candidate]:
    """Candidates whose type this system's target_types rows mark as "target"."""
    preferences = {row["template_filename"]: row["preference"] for row in type_rows}
    return [c for c in candidates if preferences.get(c["type"]) == "target"]


def split_reachable(candidates: list[Candidate], own_pos: Point | None,
                    interceptor_speed: float) -> tuple[list[Candidate], int]:
    """Set time_to_intercept_sec on each candidate; return (reachable, unreachable_count).

    Without the own ship's position nothing can be ruled out, so every
    candidate is kept with time_to_intercept_sec None.
    """
    reachable: list[Candidate] = []
    unreachable = 0
    for candidate in candidates:
        if own_pos is None:
            candidate["time_to_intercept_sec"] = None
            reachable.append(candidate)
            continue
        t = time_to_intercept(
            candidate["click_x"] - own_pos[0], candidate["click_y"] - own_pos[1],
            candidate["vx"], candidate["vy"], interceptor_speed,
        )
        candidate["time_to_intercept_sec"] = t
        if t is None:
            unreachable += 1
        else:
            reachable.append(candidate)
    return reachable, unreachable


def to_screen_coords(candidates: list[Candidate], screen_offset: Point) -> None:
    """Shift click_x/click_y from image-local to screen coordinates, in place."""
    for candidate in candidates:
        candidate["click_x"] += screen_offset[0]
        candidate["click_y"] += screen_offset[1]


def carry_over_measurements(candidates: list[Candidate], known_candidates: list[Candidate],
                            screen_offset: Point, max_dist: float) -> None:
    """Copy cargo/hull/shield onto each candidate from the closest compatible known one, in place.

    known_candidates come from the last scan/refresh, so their click_x/click_y
    are screen coordinates; they are shifted back to image-local first. A known
    candidate is compatible when its type matches and its name doesn't
    conflict. A candidate with no compatible match within max_dist gets empty
    measurements.
    """
    known_local = [
        {**known, "click_x": known["click_x"] - screen_offset[0], "click_y": known["click_y"] - screen_offset[1]}
        for known in known_candidates
    ]
    for candidate in candidates:
        best: Candidate | None = None
        best_dist = max_dist
        for known in known_local:
            if known.get("type") != candidate["type"] or names_conflict(known.get("name"), candidate.get("name")):
                continue
            dist = math.hypot(candidate["click_x"] - known["click_x"], candidate["click_y"] - known["click_y"])
            if dist <= best_dist:
                best, best_dist = known, dist
        source = best or empty_measurements()
        candidate["cargo"] = source.get("cargo", {})
        candidate["hull_pct"] = source.get("hull_pct")
        candidate["shield_pct"] = source.get("shield_pct")
