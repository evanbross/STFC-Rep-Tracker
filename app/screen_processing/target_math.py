# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Pure cross-frame tracking, intercept, and scoring math for system targets.

Extracted from process_system_targets.py so it can be unit-tested without
importing the screen-capture stack. Reads tunables via capture_cfg only.
"""
import math
import re

from app.app_config import capture_cfg


def names_conflict(name_a: str | None, name_b: str | None) -> bool:
    """Return True only if both names are present and clearly different.

    Normalizes case/punctuation first so minor OCR noise between frames
    (e.g. a dropped space or a misread punctuation mark) doesn't split one
    real target into two tracks.
    """
    if not name_a or not name_b:
        return False
    normalize = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return normalize(name_a) != normalize(name_b)


# ai: claude-sonnet-5 | 2026-09-14
def match_and_track(frame0: list[dict], frame1: list[dict], elapsed_sec: float) -> list[dict]:
    """Match frame1 detections back to frame0 by nearest position and derive velocity.

    Greedy nearest-neighbor matching — not globally optimal, but adequate for
    the handful of targets typically on screen at once. Matches are only
    considered between icons of the same "type" (template), which also
    sidesteps most ambiguity. A frame1 detection with no plausible frame0
    match (moved further than max_track_distance_px, or newly appeared) is
    kept with velocity_known=False rather than dropped, since it may still be
    worth inspecting even without a speed estimate.
    """
    max_dist = capture_cfg("combat", "max_track_distance_px", default=250)

    pairs: list[tuple[float, int, int]] = []
    for i1, d1 in enumerate(frame1):
        for i0, d0 in enumerate(frame0):
            if d1["type"] != d0["type"]:
                continue
            if names_conflict(d1["name"], d0["name"]):
                continue
            dist = math.hypot(d1["click_x"] - d0["click_x"], d1["click_y"] - d0["click_y"])
            if dist <= max_dist:
                pairs.append((dist, i1, i0))
    pairs.sort(key=lambda p: p[0])

    assigned: dict[int, int] = {}
    used0: set[int] = set()
    for dist, i1, i0 in pairs:
        if i1 in assigned or i0 in used0:
            continue
        assigned[i1] = i0
        used0.add(i0)

    tracked: list[dict] = []
    for i1, d1 in enumerate(frame1):
        candidate = dict(d1)
        if i1 in assigned:
            d0 = frame0[assigned[i1]]
            candidate["vx"] = (d1["click_x"] - d0["click_x"]) / elapsed_sec
            candidate["vy"] = (d1["click_y"] - d0["click_y"]) / elapsed_sec
            candidate["velocity_known"] = True
        else:
            candidate["vx"] = 0.0
            candidate["vy"] = 0.0
            candidate["velocity_known"] = False
        tracked.append(candidate)
    return tracked


# ai: claude-sonnet-5 | 2026-09-14
def time_to_intercept(
    rel_x: float, rel_y: float, target_vx: float, target_vy: float, interceptor_speed: float
) -> float | None:
    """Solve the classic pursuit-intercept quadratic for the smallest positive time.

    Given a stationary interceptor's relative offset to a target (rel_x,
    rel_y) and the target's velocity (target_vx, target_vy), finds the
    smallest t > 0 such that a point moving at interceptor_speed (any
    direction) reaches the target's future position at exactly time t:
        |rel + target_vel * t| = interceptor_speed * t
    Returns None if the interceptor can never catch the target (too slow and
    the target is opening the distance faster than the interceptor can close it).
    """
    a = target_vx**2 + target_vy**2 - interceptor_speed**2
    b = 2 * (rel_x * target_vx + rel_y * target_vy)
    c = rel_x**2 + rel_y**2

    if abs(a) < 1e-9:
        if abs(b) < 1e-9:
            return 0.0 if c <= 1e-9 else None
        t = -c / b
        return t if t > 1e-6 else None

    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return None
    sqrt_disc = math.sqrt(discriminant)
    roots = [(-b - sqrt_disc) / (2 * a), (-b + sqrt_disc) / (2 * a)]
    positive_roots = [t for t in roots if t > 1e-6]
    return min(positive_roots) if positive_roots else None


# ai: claude-sonnet-5 | 2026-09-14
def _loot_value(cargo: dict, weights: dict) -> float:
    return sum(amount * weights.get(resource, 1.0) for resource, amount in cargo.items())


# ai: claude-sonnet-5 | 2026-09-18
def score_candidates(candidates: list[dict]) -> list[dict]:
    """Attach a normalized "score" (0.0-1.0) to each candidate.

    score = loot_weight * normalized_loot_value
          + ease_weight * normalized_ease (favors lower level / hull / shield)
          + intercept_weight * normalized_speed (favors a shorter time_to_intercept_sec)
          - skull_score_penalty if the label's skull (dangerous) glyph matched
          + diamond_score_bonus if the label's diamond (bounty) glyph matched
    Candidates with an unknown intercept time (own ship not detected) get a
    neutral 0.5 for that component rather than being penalized or favored.
    The skull/diamond adjustment is applied after the weighted sum and the
    result is clamped back to [0.0, 1.0].
    """
    if not candidates:
        return candidates

    resource_weights = capture_cfg("combat", "resource_value_weights", default={}) or {}
    score_weights = capture_cfg(
        "combat", "score_weights", default={"loot": 0.3, "ease": 0.3, "intercept": 0.4}
    )
    loot_weight = score_weights.get("loot", 0.3)
    ease_weight = score_weights.get("ease", 0.3)
    intercept_weight = score_weights.get("intercept", 0.4)
    skull_penalty = capture_cfg("combat", "skull_score_penalty", default=0.5)
    diamond_bonus = capture_cfg("combat", "diamond_score_bonus", default=0.3)

    loot_values = [_loot_value(c.get("cargo", {}), resource_weights) for c in candidates]
    max_loot = max(loot_values) or 1.0

    levels = [c["level"] for c in candidates if c.get("level") is not None]
    max_level = max(levels) if levels else 1

    intercept_times = [
        c["time_to_intercept_sec"]
        for c in candidates
        if c.get("time_to_intercept_sec") is not None
    ]
    max_intercept_time = max(intercept_times) if intercept_times else None

    for candidate, loot_value in zip(candidates, loot_values):
        loot_norm = loot_value / max_loot

        level = candidate.get("level")
        level_norm = (level / max_level) if level is not None else 0.5
        ease_components = [1.0 - level_norm]
        hull_pct = candidate.get("hull_pct")
        shield_pct = candidate.get("shield_pct")
        if hull_pct is not None:
            ease_components.append(1.0 - hull_pct / 100)
        if shield_pct is not None:
            ease_components.append(1.0 - shield_pct / 100)
        ease_norm = sum(ease_components) / len(ease_components)

        intercept_time = candidate.get("time_to_intercept_sec")
        if intercept_time is not None and max_intercept_time:
            intercept_norm = 1.0 - (intercept_time / max_intercept_time)
        else:
            intercept_norm = 0.5

        score = loot_weight * loot_norm + ease_weight * ease_norm + intercept_weight * intercept_norm
        if candidate.get("hazard"):
            score -= skull_penalty
        if candidate.get("bounty"):
            score += diamond_bonus

        candidate["loot_value"] = loot_value
        candidate["score"] = round(max(0.0, min(1.0, score)), 4)

    return sorted(candidates, key=lambda c: c["score"], reverse=True)
