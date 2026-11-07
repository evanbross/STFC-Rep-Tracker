# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""territory_parsing: row geometry and name/timer pairing (R12). No OpenCV or EasyOCR."""
from datetime import UTC, datetime

import pytest

from app.screen_processing import territory_parsing as tp

_NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


def _ocr(text: str, y: float, conf: float = 0.9, x: float = 100) -> tp.OcrResult:
    """One EasyOCR readtext(detail=1) entry with a 20 px tall box at (x, y)."""
    return ([[x, y], [x + 80, y], [x + 80, y + 20], [x, y + 20]], text, conf)


# ── territory_row / token picking ─────────────────────────────────────────────

def test_territory_row_adds_the_countdown_to_now() -> None:
    assert tp.territory_row("Saldeti", "20h 03m", _NOW) == {
        "name": "Saldeti", "time_remaining": "20h 03m", "event_time": "2026-11-07 08:03",
    }


def test_territory_row_keeps_an_unparseable_timer_without_a_time() -> None:
    assert tp.territory_row("Gelida", "500ms", _NOW)["event_time"] is None


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["Saldeti", "Next Takeover:", "20h 03m"], ("Saldeti", "20h 03m")),
        (["02d 18h", "Gelida"], ("Gelida", "02d 18h")),
        (["Zamaro"], ("Zamaro", None)),
        ([], (None, None)),
    ],
)
def test_name_and_timer(tokens: list[str], expected: tuple[str | None, str | None]) -> None:
    assert tp.name_and_timer(tokens) == expected


def test_first_timer_skips_non_timers() -> None:
    assert tp.first_timer(["", "Next", "06d 00h", "06d 22h"]) == "06d 00h"


# ── row geometry ──────────────────────────────────────────────────────────────

def test_row_height_is_the_mean_portrait_spacing() -> None:
    portraits = [(0, 0, 100, 150), (0, 165, 100, 150), (0, 330, 100, 150)]
    assert tp.estimate_row_height(portraits) == 165


def test_row_height_from_a_single_portrait_is_twice_its_height() -> None:
    assert tp.estimate_row_height([(0, 10, 100, 150)]) == 300


def test_strip_ends_just_below_its_rows_takeover_label() -> None:
    portraits = [(200, 160, 110, 150), (200, 0, 110, 150)]  # unsorted on purpose
    labels = [(340, 205, 104, 23), (340, 44, 104, 23)]

    strips = tp.row_strip_regions(
        portraits, labels, 1800, 1000, max_row_height_px=300, name_timer_height_frac=0.65,
    )

    assert strips == [(0, (310, 0, 1800, 44 + 23 + 4)), (160, (310, 160, 1800, 205 + 23 + 4))]


def test_strip_without_a_label_uses_the_row_height_fraction() -> None:
    portraits = [(200, 0, 110, 150), (200, 200, 110, 150)]
    far_label = [(340, 600, 104, 23)]  # beyond max_row_height_px of both rows

    strips = tp.row_strip_regions(
        portraits, far_label, 1800, 1000, max_row_height_px=300, name_timer_height_frac=0.5,
    )

    assert [region for _, region in strips] == [(310, 0, 1800, 100), (310, 200, 1800, 300)]


def test_strips_are_clipped_to_the_image_and_empty_ones_dropped() -> None:
    portraits = [(0, 900, 100, 150), (1750, 100, 100, 150)]  # second starts past the right edge

    strips = tp.row_strip_regions(
        portraits, [], 1800, 1000, max_row_height_px=300, name_timer_height_frac=1.0,
    )

    assert strips == [(900, (100, 900, 1800, 1000))]


def test_timer_strip_is_measured_in_name_heights_and_clipped() -> None:
    assert tp.timer_strip_rows((336, 139, 73, 28), 1000, 3.0) == (167, 251)
    assert tp.timer_strip_rows((336, 980, 73, 28), 1000, 3.0) == (1008, 1000)


# ── full-image fallback pairing ───────────────────────────────────────────────

def test_full_image_pairs_each_name_with_the_timer_below_it() -> None:
    raw = [
        _ocr("Gelida", 200),
        _ocr("02d 18h", 225),
        _ocr("Saldeti", 30),
        _ocr("20h 03m", 55),
    ]

    rows = tp.pair_full_image_results(raw, _NOW, min_conf=0.2, pair_max_gap_px=300, emblem_skip_px=100)

    assert [(r["name"], r["time_remaining"]) for r in rows] == [("Saldeti", "20h 03m"), ("Gelida", "02d 18h")]


def test_full_image_skips_badge_labels_close_below_a_timer() -> None:
    raw = [
        _ocr("Saldeti", 30),
        _ocr("20h 03m", 55),
        _ocr("Sarcophagus Forges", 120),  # badge: 65 px below the timer
        _ocr("Gelida", 200),              # 145 px below: a real name
        _ocr("02d 18h", 225),
    ]

    rows = tp.pair_full_image_results(raw, _NOW, min_conf=0.2, pair_max_gap_px=300, emblem_skip_px=100)

    assert [r["name"] for r in rows] == ["Saldeti", "Gelida"]


def test_full_image_drops_low_confidence_and_distant_timers() -> None:
    raw = [
        _ocr("Saldeti", 30),
        _ocr("20h 03m", 55, conf=0.1),  # below min_conf
        _ocr("Zamaro", 400),
        _ocr("06d 00h", 800),           # 400 px below: too far to pair
    ]

    assert tp.pair_full_image_results(raw, _NOW, min_conf=0.2, pair_max_gap_px=300, emblem_skip_px=10) == []
