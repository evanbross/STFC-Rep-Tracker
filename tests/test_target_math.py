# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Pure-function tests for system-target tracking, intercept, and scoring math."""
import pytest

from app.screen_processing import target_math


@pytest.fixture(autouse=True)
def code_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the in-code defaults instead of whatever settings.yaml holds today."""
    monkeypatch.setattr(target_math, "capture_cfg", lambda *keys, default=None: default)


def _det(type_: str, name: str | None, x: float, y: float) -> dict:
    return {"type": type_, "name": name, "click_x": x, "click_y": y}


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("Klingon Scout", "klingon-scout", False),   # OCR noise is not a conflict
        ("Borg Cube", None, False),                  # a missing name never conflicts
        ("Borg", "Romulan", True),
    ],
)
def test_names_conflict(a: str | None, b: str | None, expected: bool) -> None:
    assert target_math.names_conflict(a, b) is expected


def test_match_and_track_derives_velocity() -> None:
    frame0 = [_det("hostile.png", "Scout", 0, 0)]
    frame1 = [_det("hostile.png", "Scout", 10, -4)]

    [tracked] = target_math.match_and_track(frame0, frame1, elapsed_sec=2.0)

    assert tracked["velocity_known"] is True
    assert (tracked["vx"], tracked["vy"]) == (5.0, -2.0)


@pytest.mark.parametrize(
    "frame1",
    [
        [_det("other.png", "Scout", 10, 0)],    # different template type
        [_det("hostile.png", "Romulan", 10, 0)],  # conflicting OCR name
        [_det("hostile.png", "Scout", 1000, 0)],  # beyond max_track_distance_px (250)
    ],
)
def test_match_and_track_keeps_unmatched_without_velocity(frame1: list[dict]) -> None:
    frame0 = [_det("hostile.png", "Scout", 0, 0)]

    [tracked] = target_math.match_and_track(frame0, frame1, elapsed_sec=1.0)

    assert tracked["velocity_known"] is False
    assert (tracked["vx"], tracked["vy"]) == (0.0, 0.0)


def test_match_and_track_is_one_to_one() -> None:
    """Two new detections near one old one: only the nearest inherits its track."""
    frame0 = [_det("h.png", None, 0, 0)]
    frame1 = [_det("h.png", None, 50, 0), _det("h.png", None, 5, 0)]

    far, near = target_math.match_and_track(frame0, frame1, elapsed_sec=1.0)

    assert near["velocity_known"] is True and near["vx"] == 5.0
    assert far["velocity_known"] is False


@pytest.mark.parametrize(
    ("rel", "vel", "speed", "expected"),
    [
        ((30, 40), (0, 0), 10, 5.0),       # stationary target 50px away
        ((10, 0), (-1, 0), 1, 5.0),        # equal speeds, target closing (linear case)
        ((0, 0), (0, 0), 0, 0.0),          # already there
        ((10, 0), (5, 0), 1, None),        # target outruns a slower interceptor
    ],
)
def test_time_to_intercept(
    rel: tuple[float, float], vel: tuple[float, float], speed: float, expected: float | None
) -> None:
    result = target_math.time_to_intercept(rel[0], rel[1], vel[0], vel[1], speed)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def _candidates() -> list[dict]:
    return [
        {"name": "B", "cargo": {"ore": 50}, "level": 20, "time_to_intercept_sec": 20},
        {"name": "A", "cargo": {"ore": 100}, "level": 10, "time_to_intercept_sec": 10},
    ]


def test_score_candidates_weights_and_order() -> None:
    # Default weights loot 0.3 / ease 0.3 / intercept 0.4:
    #   A = 0.3*1.0 + 0.3*0.5 + 0.4*0.5 = 0.65
    #   B = 0.3*0.5 + 0.3*0.0 + 0.4*0.0 = 0.15
    scored = target_math.score_candidates(_candidates())

    assert [(c["name"], c["score"]) for c in scored] == [("A", 0.65), ("B", 0.15)]
    assert scored[0]["loot_value"] == 100


def test_score_candidates_glyph_adjustments_are_clamped() -> None:
    candidates = _candidates()
    candidates[0]["bounty"] = True    # B: 0.15 + 0.3 diamond bonus
    candidates[1]["hazard"] = True    # A: 0.65 - 0.5 skull penalty

    scores = {c["name"]: c["score"] for c in target_math.score_candidates(candidates)}

    assert scores == {"A": 0.15, "B": 0.45}


def test_score_candidates_never_negative() -> None:
    candidates = _candidates()
    candidates[0]["hazard"] = True    # B: 0.15 - 0.5 → clamped to 0.0

    scores = {c["name"]: c["score"] for c in target_math.score_candidates(candidates)}

    assert scores["B"] == 0.0


def test_score_candidates_empty() -> None:
    assert target_math.score_candidates([]) == []
