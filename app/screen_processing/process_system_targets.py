# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
from __future__ import annotations

import logging
import math
import os
import re
import time
from datetime import datetime, UTC
from typing import TYPE_CHECKING

import cv2
import numpy as np
import pyautogui
from werkzeug.utils import secure_filename

from app.app_config import capture_cfg
from app.screen_processing.ocr_text import parse_info_panel, parse_name_level
from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    find_all_template_matches,
    get_reader,
    get_snippets_dir,
    match_template,
    wait_and_click_any,
)
from app.screen_processing.target_math import (
    match_and_track,
    names_conflict,
    score_candidates,
    time_to_intercept,
)

if TYPE_CHECKING:
    from app.database.database import Database

logger = logging.getLogger(__name__)

_TARGET_SAMPLES_SUBDIR = "target_samples"


# ---------------------------------------------------------------------------
# System identification
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def detect_system_name(img: np.ndarray) -> str | None:
    """OCR the current system's name from a configurable screen region.

    Target-type history is tracked per system, so scanning can't proceed
    without this. Returns None if the crop is empty or OCR finds nothing —
    callers must treat that as a hard error, not a silently skipped feature.
    """
    x_frac = capture_cfg("combat", "system_name_x_frac", default=0.35)
    y_frac = capture_cfg("combat", "system_name_y_frac", default=0.0)
    w_frac = capture_cfg("combat", "system_name_w_frac", default=0.3)
    h_frac = capture_cfg("combat", "system_name_h_frac", default=0.08)

    img_h, img_w = img.shape[:2]
    x1 = int(img_w * x_frac)
    y1 = int(img_h * y_frac)
    x2 = min(img_w, x1 + int(img_w * w_frac))
    y2 = min(img_h, y1 + int(img_h * h_frac))
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    reader = get_reader()
    raw = reader.readtext(crop, detail=0)
    text = " ".join(t.strip() for t in raw if t.strip())
    return text or None


# ---------------------------------------------------------------------------
# Detection: ship icons -> name/level labels
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def _find_ship_icons(img: np.ndarray) -> list[dict]:
    """Return {"x","y","w","h","type"} for every hostile ship icon detected in img.

    "type" is the template filename that matched — this is the identity used
    to group targets into the same "kind" for the target_types classification
    table, since it's the only reliable signal template matching gives us.
    """
    templates: list[str] = capture_cfg("combat", "hostile_ship_templates", default=[]) or []
    if not templates:
        logger.warning(
            "combat.hostile_ship_templates is empty — add ship icon snippet "
            "filenames to settings.yaml before scanning"
        )
        return []

    icons: list[dict] = []
    for filename in templates:
        try:
            matches = find_all_template_matches(filename, img)
        except FileNotFoundError:
            logger.error("Hostile ship template not found on disk: %s", filename)
            continue
        for x, y, w, h in matches:
            icons.append({"x": x, "y": y, "w": w, "h": h, "type": filename})
    return icons


# ai: claude-sonnet-5 | 2026-09-14
def _label_crop(img: np.ndarray, icon: dict) -> np.ndarray | None:
    """Crop the name/level label region above a ship icon for OCR.

    The crop is sized relative to the icon's own bounding box so it scales
    with display resolution. Returns None if the computed region is empty.
    """
    x, y, w, h = icon["x"], icon["y"], icon["w"], icon["h"]
    gap_frac = capture_cfg("combat", "label_gap_frac", default=0.1)
    height_frac = capture_cfg("combat", "label_height_frac", default=0.6)
    width_mult = capture_cfg("combat", "label_width_multiplier", default=3.0)

    label_h = max(1, int(h * height_frac))
    label_y2 = max(0, y - int(h * gap_frac))
    label_y1 = max(0, label_y2 - label_h)

    label_w = max(1, int(w * width_mult))
    center_x = x + w // 2
    label_x1 = max(0, center_x - label_w // 2)
    label_x2 = min(img.shape[1], label_x1 + label_w)

    crop = img[label_y1:label_y2, label_x1:label_x2]
    return crop if crop.size > 0 else None


# ai: claude-sonnet-5 | 2026-09-18
def _detect_label_glyph(crop: np.ndarray, templates: list[str]) -> bool:
    """Return True if any of the given glyph templates matches within crop.

    Used for the optional skull (dangerous) / diamond (bounty) glyph that
    can appear at the end of a ship's label — these are icons, not text, so
    OCR can't read them; template matching against the same label crop used
    for OCR is the only way to detect them.
    """
    if crop is None or not templates:
        return False
    threshold = capture_cfg("combat", "glyph_match_threshold", default=0.75)
    for filename in templates:
        try:
            result = match_template(filename, crop)
        except FileNotFoundError:
            logger.error("Glyph template not found on disk: %s", filename)
            continue
        if result is not None and result[1] >= threshold:
            return True
    return False


# ai: claude-sonnet-5 | 2026-09-14
def _label_icons(img: np.ndarray, icons: list[dict]) -> list[dict]:
    """OCR the label above each icon and return candidate dicts.

    Each candidate dict: {"x","y","w","h","type","click_x","click_y","name",
    "level","hazard","bounty"}. Coordinates are image-local pixels (icon
    center) — callers add the window's screen offset only when actually
    issuing a click. hazard/bounty come from template-matching the
    skull/diamond glyph within the same label crop used for OCR (see
    _detect_label_glyph) — they default to False if no glyph templates are
    configured yet.
    """
    reader = get_reader()
    min_conf = capture_cfg("combat", "ocr_min_confidence", default=0.2)
    skull_templates = capture_cfg("combat", "skull_glyph_templates", default=[]) or []
    diamond_templates = capture_cfg("combat", "diamond_glyph_templates", default=[]) or []
    candidates: list[dict] = []

    for icon in icons:
        crop = _label_crop(img, icon)
        name = level = None
        hazard = bounty = False
        if crop is not None:
            raw = reader.readtext(crop, detail=1)
            tokens = [t.strip() for _, t, c in raw if c >= min_conf and t.strip()]
            name, level = parse_name_level(tokens)
            hazard = _detect_label_glyph(crop, skull_templates)
            bounty = _detect_label_glyph(crop, diamond_templates)
        candidates.append(
            {
                "x": icon["x"],
                "y": icon["y"],
                "w": icon["w"],
                "h": icon["h"],
                "type": icon["type"],
                "click_x": icon["x"] + icon["w"] // 2,
                "click_y": icon["y"] + icon["h"] // 2,
                "name": name,
                "level": level,
                "hazard": hazard,
                "bounty": bounty,
            }
        )
        logger.debug(
            "Detected candidate at (%d, %d): type=%r name=%r level=%r hazard=%r bounty=%r",
            icon["x"], icon["y"], icon["type"], name, level, hazard, bounty,
        )

    return candidates


# ---------------------------------------------------------------------------
# Cross-frame tracking (position -> velocity)
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def _predict_position(candidate: dict, elapsed_sec: float) -> tuple[float, float]:
    """Extrapolate a candidate's image-local position forward by elapsed_sec."""
    return (
        candidate["click_x"] + candidate["vx"] * elapsed_sec,
        candidate["click_y"] + candidate["vy"] * elapsed_sec,
    )


# ai: claude-sonnet-5 | 2026-09-14
def _reacquire(img: np.ndarray, predicted_x: float, predicted_y: float, type_filename: str | None = None) -> tuple[int, int] | None:
    """Find a hostile ship icon nearest a predicted position in a fresh capture.

    Targets move continuously, so any position recorded even a second ago is
    stale. This re-runs template matching and returns the closest match
    within combat.reacquire_max_distance_px, or None if nothing is close
    enough to trust. When type_filename is given, only that template is
    matched — narrower and faster, and avoids reacquiring the wrong ship type.
    """
    templates: list[str] = (
        [type_filename] if type_filename
        else (capture_cfg("combat", "hostile_ship_templates", default=[]) or [])
    )
    max_dist = capture_cfg("combat", "reacquire_max_distance_px", default=200)

    best: tuple[int, int] | None = None
    best_dist = float("inf")
    for filename in templates:
        try:
            matches = find_all_template_matches(filename, img)
        except FileNotFoundError:
            continue
        for x, y, w, h in matches:
            cx, cy = x + w // 2, y + h // 2
            dist = math.hypot(cx - predicted_x, cy - predicted_y)
            if dist <= max_dist and dist < best_dist:
                best = (cx, cy)
                best_dist = dist
    return best


# ---------------------------------------------------------------------------
# Player exclusion
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def _filter_players(candidates: list[dict]) -> list[dict]:
    """Drop candidates whose name matches combat.player_name_pattern.

    Candidates with no name at all (OCR failure) are kept — they can still be
    inspected by click, which is a better signal than a missing label.
    """
    pattern = capture_cfg("combat", "player_name_pattern", default=r"\[.*?\]")
    survivors = []
    for c in candidates:
        if c["name"] and re.search(pattern, c["name"]):
            logger.debug("Excluding likely player ship: %r", c["name"])
            continue
        survivors.append(c)
    return survivors


# ---------------------------------------------------------------------------
# Target-type sample capture (for the classification screen)
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def _default_display_name(type_filename: str) -> str:
    stem = os.path.splitext(type_filename)[0]
    return re.sub(r"[_\-]+", " ", stem).strip().title()


# ai: claude-sonnet-5 | 2026-09-14
def _save_type_sample(img: np.ndarray, candidate: dict, system_name: str) -> str | None:
    """Save a crop showing an example of a newly-seen target type to disk.

    Includes the label area above the icon (name/level) as well as the icon
    itself, so the classification screen shows something recognizable rather
    than a bare icon. Returns a path relative to the snippets directory
    (e.g. "target_samples/Foo_bar_20260914_120000.png"), or None on failure.
    """
    x, y, w, h = candidate["x"], candidate["y"], candidate["w"], candidate["h"]
    y1 = max(0, y - h)  # TODO: calibrate — assumes the label sits roughly one icon-height above
    y2 = min(img.shape[0], y + h)
    x1 = max(0, x - w // 2)
    x2 = min(img.shape[1], x + w + w // 2)
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    samples_dir = os.path.join(get_snippets_dir(), _TARGET_SAMPLES_SUBDIR)
    os.makedirs(samples_dir, exist_ok=True)

    stem = os.path.splitext(candidate["type"])[0]
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = secure_filename(f"{system_name}_{stem}_{timestamp}.png")
    if not filename:
        return None
    cv2.imwrite(os.path.join(samples_dir, filename), crop)
    return f"{_TARGET_SAMPLES_SUBDIR}/{filename}"


# ---------------------------------------------------------------------------
# Own (active/interceptor) ship position
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def _find_own_ship_position(img: np.ndarray) -> tuple[int, int] | None:
    """Locate the active ship's icon on the system starmap.

    Returns its image-local center, or None if combat.own_ship_templates is
    unconfigured or nothing matched — callers must degrade gracefully
    (intercept-time scoring simply becomes unavailable) rather than failing
    the whole scan, since loot/ease scoring can still proceed without it.
    """
    templates: list[str] = capture_cfg("combat", "own_ship_templates", default=[]) or []
    if not templates:
        logger.warning(
            "combat.own_ship_templates is empty — intercept-time scoring disabled"
        )
        return None

    matches: list[tuple[int, int, int, int]] = []
    for filename in templates:
        try:
            matches.extend(find_all_template_matches(filename, img))
        except FileNotFoundError:
            logger.error("Own ship template not found on disk: %s", filename)

    if not matches:
        logger.warning("Active ship icon not detected — intercept-time scoring disabled")
        return None
    if len(matches) > 1:
        logger.warning(
            "Multiple active-ship icon matches (%d) — using the first", len(matches)
        )
    x, y, w, h = matches[0]
    return (x + w // 2, y + h // 2)


# ---------------------------------------------------------------------------
# Two-frame sampling (shared by a full scan and a lightweight refresh)
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def _sample_and_track(
    sc: ScreenCapture, window, sample_interval: float, first_frame: np.ndarray | None = None
) -> tuple[list[dict] | None, np.ndarray | None]:
    """Capture two frames sample_interval apart and return tracked, player-filtered hostiles.

    Pass first_frame when the caller already has a fresh capture (e.g. one
    just used for system-name OCR) to avoid an extra screenshot.

    Returns (hostiles, second_frame_image). hostiles is None if either
    capture failed (caller should treat this as an error), or [] if nothing
    was detected in the second frame (caller should treat this as "no
    targets right now", not an error).
    """
    img0 = first_frame if first_frame is not None else sc.capture(window)
    if img0 is None:
        return None, None
    frame0 = _label_icons(img0, _find_ship_icons(img0))

    time.sleep(sample_interval)

    img1 = sc.capture(window)
    if img1 is None:
        return None, None
    frame1_time = time.time()
    frame1 = _label_icons(img1, _find_ship_icons(img1))
    if not frame1:
        return [], img1

    tracked = match_and_track(frame0, frame1, sample_interval)
    for candidate in tracked:
        candidate["frame_time"] = frame1_time

    return _filter_players(tracked), img1


# ai: claude-sonnet-5 | 2026-09-14
def _carry_over_measurements(
    candidates: list[dict], known_candidates: list[dict], screen_offset: tuple[int, int]
) -> None:
    """Copy cargo/hull/shield from the closest matching previously-known candidate.

    Used by the lightweight refresh, which re-detects position/velocity but
    does not re-click targets to re-read their info panel — the last measured
    values are carried forward instead. known_candidates carry click_x/click_y
    as absolute screen coordinates (as returned by scan/refresh), so they're
    converted back to image-local before comparing against freshly detected
    positions. Candidates with no plausible match (brand new since the last
    full scan) get empty/unknown values, mutated in place.
    """
    max_dist = capture_cfg("combat", "reacquire_max_distance_px", default=200)
    known_local = [
        {
            **known,
            "click_x": known["click_x"] - screen_offset[0],
            "click_y": known["click_y"] - screen_offset[1],
        }
        for known in known_candidates
    ]

    for candidate in candidates:
        best: dict | None = None
        best_dist = max_dist
        for known in known_local:
            if known.get("type") != candidate["type"]:
                continue
            if names_conflict(known.get("name"), candidate.get("name")):
                continue
            dist = math.hypot(
                candidate["click_x"] - known["click_x"], candidate["click_y"] - known["click_y"]
            )
            if dist <= best_dist:
                best = known
                best_dist = dist
        candidate["cargo"] = (best or {}).get("cargo", {})
        candidate["hull_pct"] = (best or {}).get("hull_pct")
        candidate["shield_pct"] = (best or {}).get("shield_pct")


# ---------------------------------------------------------------------------
# Per-candidate inspection (click -> info panel -> OCR cargo/hull/shield)
# ---------------------------------------------------------------------------


# ai: claude-sonnet-5 | 2026-09-14
def _inspect_candidates(
    sc: ScreenCapture, window, screen_offset: tuple[int, int], candidates: list[dict]
) -> list[dict]:
    """Click each candidate, OCR its info panel, then deselect.

    Since targets drift continuously, each candidate's recorded position is
    re-predicted from its tracked velocity and re-acquired against a fresh
    capture immediately before clicking — clicking the stale scan-time
    position would frequently miss. candidate["click_x"/"click_y"] and
    candidate["scanned_at"] are updated in place to the freshest known fix so
    that attack_target() can extrapolate from the best available data.

    Mutates and returns candidates (adds "cargo", "hull_pct", "shield_pct").
    Limited to combat.max_candidates_to_inspect since each inspection is a
    real click against the running game.
    """
    reader = get_reader()
    max_inspect = capture_cfg("combat", "max_candidates_to_inspect", default=6)
    click_delay = capture_cfg("combat", "inspect_click_delay", default=0.4)
    deselect_key = capture_cfg("combat", "deselect_key", default="esc")
    deselect_delay = capture_cfg("combat", "deselect_delay", default=0.3)

    x_frac = capture_cfg("combat", "info_panel_x_frac", default=0.65)
    y_frac = capture_cfg("combat", "info_panel_y_frac", default=0.15)
    w_frac = capture_cfg("combat", "info_panel_w_frac", default=0.33)
    h_frac = capture_cfg("combat", "info_panel_h_frac", default=0.6)

    for candidate in candidates[:max_inspect]:
        elapsed = time.time() - candidate["frame_time"]
        pred_x, pred_y = _predict_position(candidate, elapsed)

        pre_img = sc.capture(window)
        reacquired = (
            _reacquire(pre_img, pred_x, pred_y, candidate["type"]) if pre_img is not None else None
        )
        if reacquired is None:
            logger.warning(
                "Could not reacquire %r before inspecting — clicking predicted position",
                candidate.get("name"),
            )
        target_x, target_y = reacquired if reacquired else (int(pred_x), int(pred_y))
        candidate["click_x"], candidate["click_y"] = target_x, target_y
        candidate["scanned_at"] = time.time()

        screen_x = screen_offset[0] + target_x
        screen_y = screen_offset[1] + target_y
        pyautogui.click(screen_x, screen_y)
        time.sleep(click_delay)

        img = sc.capture(window)
        if img is not None:
            img_h, img_w = img.shape[:2]
            px1 = int(img_w * x_frac)
            py1 = int(img_h * y_frac)
            px2 = min(img_w, px1 + int(img_w * w_frac))
            py2 = min(img_h, py1 + int(img_h * h_frac))
            panel = img[py1:py2, px1:px2]
            if panel.size > 0:
                raw = reader.readtext(panel, detail=0)
                parsed = parse_info_panel(" ".join(raw))
                candidate.update(parsed)
            else:
                candidate.update({"cargo": {}, "hull_pct": None, "shield_pct": None})
        else:
            candidate.update({"cargo": {}, "hull_pct": None, "shield_pct": None})

        sc.press_key(window, deselect_key)
        time.sleep(deselect_delay)

    for candidate in candidates[max_inspect:]:
        candidate.setdefault("cargo", {})
        candidate.setdefault("hull_pct", None)
        candidate.setdefault("shield_pct", None)
        candidate.setdefault("scanned_at", candidate["frame_time"])

    return candidates


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SystemTargetOrchestrator:
    """Scans the current system view for attackable targets and, on approval,
    selects one and clicks Attack.

    Does not navigate anywhere — the caller must already be looking at a
    system's starmap in-game before calling scan_targets(). Assumes the
    active/selected ship is stationary while scanning (combat.own_ship_templates
    locates it once) and that targets are in constant motion, so scanning
    samples two frames to derive each target's velocity and estimate time to
    intercept.

    Every distinct hostile ship type (by icon template) is tracked per
    system in the target_types table. A system with unclassified
    ('unknown'-preference) types returns a classification roster instead of
    attack candidates — see scan_targets().
    """

    def __init__(self, db: "Database") -> None:
        self.sc = ScreenCapture()
        self.db = db

    # ai: claude-sonnet-5 | 2026-09-14
    def scan_targets(self) -> dict:
        """Detect hostile targets on screen and return them ranked best-first.

        Returns one of:
          {"success": True, "needs_classification": True, "system_name": str,
           "target_types": [...]}
            — this system has at least one hostile type the user hasn't yet
              marked target/avoid. No attack candidates are produced; the
              frontend should show the classification screen.
          {"success": True, "system_name": str, "candidates": [...], "top_pick": {...} | None}
            — normal result once every seen type is classified. Only types
              marked "target" are included as candidates.
          {"error": str} on failure.

        Each candidate includes click_x/click_y in *screen* coordinates, plus
        vx/vy (px/sec, image-local — translation invariant so valid either
        way) and scanned_at (epoch seconds), all of which attack_target()
        needs to re-predict the target's current position.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(str(e))
            return {"error": str(e)}

        screen_offset = (window.left, window.top)

        img0 = self.sc.capture(window)
        if img0 is None:
            return {"error": "Could not capture system screen"}

        system_name = detect_system_name(img0)
        if not system_name:
            return {
                "error": "Could not determine current system name — check "
                "combat.system_name_* crop settings in settings.yaml"
            }

        if not capture_cfg("combat", "hostile_ship_templates", default=[]):
            return {
                "error": "No ship icons detected — add hostile ship snippet "
                "filenames to combat.hostile_ship_templates in settings.yaml"
            }

        # Targets move continuously, so a single frame can't tell us speed —
        # sample a second frame after a short delay to derive velocity.
        sample_interval = capture_cfg("combat", "velocity_sample_interval", default=1.5)
        hostiles, img1 = _sample_and_track(self.sc, window, sample_interval, first_frame=img0)
        if hostiles is None:
            return {"error": "Could not capture system screen (second sample)"}
        if not hostiles:
            return {"success": True, "system_name": system_name, "candidates": [], "top_pick": None}

        # Record every distinct type seen this scan against this system,
        # whether or not the system already has history — a new type showing
        # up in an otherwise-known system still needs classifying.
        seen_types = {c["type"] for c in hostiles}
        for type_filename in seen_types:
            example = next(c for c in hostiles if c["type"] == type_filename)
            self.db.target_types.upsert_seen(
                system_name,
                type_filename,
                display_name=_default_display_name(type_filename),
                sample_image_filename=_save_type_sample(img1, example, system_name),
                example_name=example.get("name"),
                example_level=example.get("level"),
            )

        if self.db.target_types.has_unclassified(system_name):
            return {
                "success": True,
                "needs_classification": True,
                "system_name": system_name,
                "target_types": self.db.target_types.get_for_system(system_name),
            }

        preferences = {
            row["template_filename"]: row["preference"]
            for row in self.db.target_types.get_for_system(system_name)
        }
        approved = [c for c in hostiles if preferences.get(c["type"]) == "target"]
        if not approved:
            return {
                "success": True,
                "system_name": system_name,
                "candidates": [],
                "top_pick": None,
                "message": "No targets of an approved type are currently on screen.",
            }

        own_pos = _find_own_ship_position(img1)
        interceptor_speed = capture_cfg("combat", "own_ship_speed_px_per_sec", default=40.0)

        reachable: list[dict] = []
        unreachable_count = 0
        for candidate in approved:
            if own_pos is not None:
                rel_x = candidate["click_x"] - own_pos[0]
                rel_y = candidate["click_y"] - own_pos[1]
                t = time_to_intercept(rel_x, rel_y, candidate["vx"], candidate["vy"], interceptor_speed)
                candidate["time_to_intercept_sec"] = t
                if t is None:
                    unreachable_count += 1
                    continue
            else:
                candidate["time_to_intercept_sec"] = None
            reachable.append(candidate)

        if not reachable:
            message = (
                f"{unreachable_count} target(s) detected but none are reachable at the "
                "configured combat.own_ship_speed_px_per_sec"
                if unreachable_count
                else None
            )
            return {
                "success": True,
                "system_name": system_name,
                "candidates": [],
                "top_pick": None,
                "message": message,
            }

        inspected = _inspect_candidates(self.sc, window, screen_offset, reachable)
        scored = score_candidates(inspected)

        for candidate in scored:
            candidate["click_x"] += screen_offset[0]
            candidate["click_y"] += screen_offset[1]
            candidate.pop("frame_time", None)

        return {
            "success": True,
            "system_name": system_name,
            "candidates": scored,
            "top_pick": scored[0] if scored else None,
        }

    # ai: claude-sonnet-5 | 2026-09-14
    def refresh_targets(self, system_name: str, known_candidates: list[dict] | None = None) -> dict:
        """Cheaply re-rank the current candidate list without clicking any target.

        Meant to be polled every few seconds during active combat (a
        lightweight companion to scan_targets()): re-detects each approved
        target's position/velocity and recomputes time-to-intercept and
        score, but does NOT re-click targets to re-read cargo/hull/shield —
        those values are carried forward from known_candidates (the last
        scan_targets()/refresh_targets() result) by matching each freshly
        detected icon back to the closest previous one of the same type.
        A target with no match (new since the last full scan) gets empty/
        unknown cargo/hull/shield rather than being skipped, since it may
        still be worth surfacing — a full scan_targets() call will pick up
        its real numbers once you next run one.

        Does not touch the target_types table — new/unclassified types are
        silently excluded here rather than prompting classification, since
        this is meant to run unattended in a loop. Run scan_targets() to
        pick up newly-appeared types.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(str(e))
            return {"error": str(e)}

        screen_offset = (window.left, window.top)

        if not capture_cfg("combat", "hostile_ship_templates", default=[]):
            return {
                "error": "No ship icons detected — add hostile ship snippet "
                "filenames to combat.hostile_ship_templates in settings.yaml"
            }

        sample_interval = capture_cfg("combat", "refresh_velocity_sample_interval", default=0.8)
        hostiles, img1 = _sample_and_track(self.sc, window, sample_interval)
        if hostiles is None:
            return {"error": "Could not capture system screen"}
        if not hostiles:
            return {"success": True, "system_name": system_name, "candidates": [], "top_pick": None}

        preferences = {
            row["template_filename"]: row["preference"]
            for row in self.db.target_types.get_for_system(system_name)
        }
        approved = [c for c in hostiles if preferences.get(c["type"]) == "target"]
        if not approved:
            return {"success": True, "system_name": system_name, "candidates": [], "top_pick": None}

        _carry_over_measurements(approved, known_candidates or [], screen_offset)

        own_pos = _find_own_ship_position(img1)
        interceptor_speed = capture_cfg("combat", "own_ship_speed_px_per_sec", default=40.0)

        reachable: list[dict] = []
        for candidate in approved:
            if own_pos is not None:
                rel_x = candidate["click_x"] - own_pos[0]
                rel_y = candidate["click_y"] - own_pos[1]
                t = time_to_intercept(rel_x, rel_y, candidate["vx"], candidate["vy"], interceptor_speed)
                candidate["time_to_intercept_sec"] = t
                if t is None:
                    continue
            else:
                candidate["time_to_intercept_sec"] = None
            candidate["scanned_at"] = candidate.pop("frame_time")
            reachable.append(candidate)

        scored = score_candidates(reachable)
        for candidate in scored:
            candidate["click_x"] += screen_offset[0]
            candidate["click_y"] += screen_offset[1]

        return {
            "success": True,
            "system_name": system_name,
            "candidates": scored,
            "top_pick": scored[0] if scored else None,
        }

    # ai: claude-sonnet-5 | 2026-09-14
    def attack_target(
        self,
        click_x: int,
        click_y: int,
        vx: float = 0.0,
        vy: float = 0.0,
        scanned_at: float | None = None,
    ) -> dict:
        """Re-acquire the target near (click_x, click_y) and click Attack.

        click_x/click_y are absolute screen coordinates from a scan_targets()
        candidate. Because targets drift continuously, the position is first
        extrapolated forward using vx/vy/scanned_at (also from that
        candidate) and then re-acquired against a fresh capture before
        clicking — clicking the raw scan-time coordinates would usually miss.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(str(e))
            return {"error": str(e)}

        screen_offset = (window.left, window.top)
        img = self.sc.capture(window)
        if img is None:
            return {"error": "Could not capture system screen"}

        local_x = click_x - screen_offset[0]
        local_y = click_y - screen_offset[1]
        if scanned_at is not None:
            elapsed = max(0.0, time.time() - scanned_at)
            pred_x = local_x + vx * elapsed
            pred_y = local_y + vy * elapsed
        else:
            pred_x, pred_y = local_x, local_y

        reacquired = _reacquire(img, pred_x, pred_y)
        if reacquired is None:
            logger.warning("Could not reacquire target before attacking — clicking predicted position")
        target_x, target_y = reacquired if reacquired else (int(pred_x), int(pred_y))

        pyautogui.click(screen_offset[0] + target_x, screen_offset[1] + target_y)
        select_delay = capture_cfg("combat", "select_delay", default=0.5)
        time.sleep(select_delay)

        attack_templates = capture_cfg(
            "combat", "attack_button_templates", default=["Attack Button 1.jpg"]
        )
        img2 = self.sc.capture(window)
        if img2 is None or not click_button_if_visible(attack_templates, img2, screen_offset):
            return {
                "error": "Attack button not found — target may not have been "
                "selected, or it moved outside the reacquire radius"
            }

        confirm_templates = capture_cfg("combat", "attack_confirm_templates", default=[]) or []
        if confirm_templates:
            confirm_retries = capture_cfg("combat", "confirm_wait_retries", default=4)
            confirm_delay = capture_cfg("combat", "confirm_wait_delay", default=0.3)
            clicked = wait_and_click_any(
                confirm_templates,
                self.sc,
                window,
                screen_offset,
                max_retries=confirm_retries,
                delay=confirm_delay,
            )
            if not clicked:
                return {"error": "Attack confirmation dialog not found after clicking Attack"}

        return {"success": True}
