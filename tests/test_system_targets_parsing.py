# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""system_targets_parsing: scan geometry and candidate bookkeeping (R12). No OpenCV or EasyOCR."""
import pytest

from app.screen_processing import system_targets_parsing as stp


def _cand(type_: str = "frigate.png", name: str | None = "Hirogen", x: int = 100, y: int = 100,
          vx: float = 0.0, vy: float = 0.0) -> stp.Candidate:
    return {"type": type_, "name": name, "click_x": x, "click_y": y, "vx": vx, "vy": vy}


# ── regions ───────────────────────────────────────────────────────────────────

def test_frac_region_is_clipped_to_the_image() -> None:
    assert stp.frac_region(1000, 500, 0.35, 0.0, 0.3, 0.08) == (350, 0, 650, 40)
    assert stp.frac_region(1000, 500, 0.9, 0.9, 0.5, 0.5) == (900, 450, 1000, 500)


@pytest.mark.parametrize(("region", "empty"), [((0, 0, 1, 1), False), ((5, 0, 5, 9), True), ((0, 9, 9, 3), True)])
def test_is_empty(region: stp.Region, empty: bool) -> None:
    assert stp.is_empty(region) is empty


def test_label_region_sits_above_the_icon_centered_on_it() -> None:
    region = stp.label_region((400, 300, 40, 50), 1920, gap_frac=0.1, height_frac=0.6, width_mult=3.0)
    # 30 px tall, ending 5 px above the icon; 120 px wide around x=420
    assert region == (360, 265, 480, 295)


def test_label_region_clips_at_the_top_and_left_edges() -> None:
    assert stp.label_region((10, 5, 40, 50), 1920, gap_frac=0.1, height_frac=0.6, width_mult=3.0) == (0, 0, 120, 0)


def test_sample_region_includes_the_label_above() -> None:
    assert stp.sample_region((400, 300, 40, 50), 1920, 1080) == (380, 250, 460, 350)


def test_candidate_from_icon_clicks_the_icon_center() -> None:
    candidate = stp.candidate_from_icon((400, 300, 40, 50), "frigate.png", "Hirogen", 31, True, False)
    assert (candidate["click_x"], candidate["click_y"]) == (420, 325)
    assert candidate["type"] == "frigate.png" and candidate["level"] == 31 and candidate["hazard"] is True


def test_empty_measurements_are_independent_dicts() -> None:
    first = stp.empty_measurements()
    first["cargo"]["Parsteel"] = 1
    assert stp.empty_measurements() == {"cargo": {}, "hull_pct": None, "shield_pct": None}


# ── motion and reacquisition ──────────────────────────────────────────────────

def test_predict_position_follows_velocity() -> None:
    assert stp.predict_position(_cand(x=100, y=200, vx=10, vy=-5), 2.0) == (120, 190)


def test_nearest_within_picks_the_closest_inside_the_radius() -> None:
    points = [(0, 0), (110, 100), (105, 100), (500, 500)]
    assert stp.nearest_within(points, 100, 100, max_dist=50) == (105, 100)
    assert stp.nearest_within([(500, 500)], 100, 100, max_dist=50) is None
    assert stp.nearest_within([], 0, 0, max_dist=50) is None


# ── filtering and ranking inputs ──────────────────────────────────────────────

def test_filter_players_keeps_unnamed_candidates() -> None:
    candidates = [_cand(name="[ALLY] Bob"), _cand(name="Hirogen"), _cand(name=None)]
    assert [c["name"] for c in stp.filter_players(candidates, r"\[.*?\]")] == ["Hirogen", None]


@pytest.mark.parametrize(
    ("filename", "expected"),
    [("hostile_ship-battleship_2.png", "Hostile Ship Battleship 2"), ("Swarm.jpg", "Swarm")],
)
def test_default_display_name(filename: str, expected: str) -> None:
    assert stp.default_display_name(filename) == expected


def test_approved_candidates_keep_only_target_types() -> None:
    rows = [
        {"template_filename": "a.png", "preference": "target"},
        {"template_filename": "b.png", "preference": "avoid"},
        {"template_filename": "c.png", "preference": "unknown"},
    ]
    candidates = [_cand("a.png"), _cand("b.png"), _cand("c.png"), _cand("never_seen.png")]
    assert [c["type"] for c in stp.approved_candidates(candidates, rows)] == ["a.png"]


def test_split_reachable_drops_targets_the_ship_cannot_catch() -> None:
    near = _cand(x=110, y=100)
    fleeing = _cand(x=300, y=100, vx=100)  # faster than the interceptor, moving away

    reachable, unreachable = stp.split_reachable([near, fleeing], (100, 100), interceptor_speed=40.0)

    assert reachable == [near] and unreachable == 1
    assert near["time_to_intercept_sec"] == pytest.approx(0.25)
    assert fleeing["time_to_intercept_sec"] is None


def test_split_reachable_without_own_position_keeps_everything() -> None:
    candidates = [_cand(), _cand(x=900)]
    reachable, unreachable = stp.split_reachable(candidates, None, interceptor_speed=40.0)
    assert reachable == candidates and unreachable == 0
    assert all(c["time_to_intercept_sec"] is None for c in candidates)


def test_to_screen_coords_shifts_in_place() -> None:
    candidates = [_cand(x=10, y=20)]
    stp.to_screen_coords(candidates, (100, 200))
    assert (candidates[0]["click_x"], candidates[0]["click_y"]) == (110, 220)


# ── carrying measurements between refreshes ───────────────────────────────────

def test_carry_over_copies_from_the_closest_matching_known_target() -> None:
    offset = (1000, 500)
    known = [  # screen coordinates, as the last scan returned them
        {**_cand(x=1100, y=600), "cargo": {"Parsteel": 5}, "hull_pct": 80, "shield_pct": 10},
        {**_cand(x=1300, y=600), "cargo": {"Ore": 9}, "hull_pct": 20, "shield_pct": 0},
    ]
    fresh = [_cand(x=110, y=100), _cand(x=290, y=100)]  # image-local

    stp.carry_over_measurements(fresh, known, offset, max_dist=50)

    assert fresh[0]["cargo"] == {"Parsteel": 5} and fresh[0]["hull_pct"] == 80
    assert fresh[1]["cargo"] == {"Ore": 9} and fresh[1]["shield_pct"] == 0


@pytest.mark.parametrize(
    "known",
    [
        {**_cand(type_="other.png", x=100, y=100), "cargo": {"Ore": 1}},  # different type
        {**_cand(name="Totally Different Name", x=100, y=100), "cargo": {"Ore": 1}},  # conflicting name
        {**_cand(x=400, y=100), "cargo": {"Ore": 1}},  # too far
    ],
)
def test_carry_over_leaves_unmatched_targets_empty(known: stp.Candidate) -> None:
    fresh = [_cand(x=100, y=100)]
    stp.carry_over_measurements(fresh, [known], (0, 0), max_dist=50)
    assert {k: fresh[0][k] for k in ("cargo", "hull_pct", "shield_pct")} == stp.empty_measurements()
