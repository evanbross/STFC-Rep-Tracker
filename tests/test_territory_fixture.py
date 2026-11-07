# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Territory row finding against a real Alliance Territory capture (R12, R14).

fixtures/territory_page.jpg holds four systems, top to bottom: Saldeti,
Gelida, Zamaro and Brijac. Template matching here is real (OpenCV and the
snippets in app/screen_snippets), so a re-captured snippet, a changed crop
rule, or a broken strip formula fails these tests. No OCR runs: EasyOCR
would make the suite slow and need its model downloaded.
"""
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pyautogui", reason="the capture stack needs the Windows automation packages")
cv2 = pytest.importorskip("cv2")

from app.app_config import capture_cfg  # noqa: E402  (after the importorskip guards)
from app.screen_processing.process_territory_capture import (  # noqa: E402
    find_row_strips,
    find_zone_slots_bottom,
)
from app.screen_processing.screen_capture import find_all_template_matches  # noqa: E402
from app.screen_processing.territory_parsing import timer_strip_rows  # noqa: E402

_FIXTURE = Path(__file__).parent / "fixtures" / "territory_page.jpg"
_SYSTEMS = ["Saldeti", "Gelida", "Zamaro", "Brijac"]
_TAKEOVER_LABEL = "Territory Next Takeover 2.jpg"


@pytest.fixture(name="page", scope="module")
def fixture_page() -> np.ndarray:
    """The capture with the title bar and Zone Slots header cropped off, as extraction does."""
    img = cv2.imread(str(_FIXTURE))
    assert img is not None, f"cannot read {_FIXTURE}"
    return img[find_zone_slots_bottom(img):, :]


def _name_box(page: np.ndarray, system: str) -> tuple[int, int, int, int]:
    matches = find_all_template_matches(f"Territory {system} 1.jpg", page)
    assert len(matches) == 1, f"{system}: expected one name match, got {matches}"
    return matches[0]


def test_zone_slots_header_is_found() -> None:
    img = cv2.imread(str(_FIXTURE))
    # The header snippet matches at y=76 and is 44 px tall; the fallback would be 40.
    assert find_zone_slots_bottom(img) == 120


def test_each_system_name_is_found_once_top_to_bottom(page: np.ndarray) -> None:
    ys = [_name_box(page, system)[1] for system in _SYSTEMS]
    assert ys == sorted(ys)


def test_one_strip_per_row_holding_its_name_and_timer_but_no_badges(page: np.ndarray) -> None:
    strips = find_row_strips(page)
    labels = sorted(find_all_template_matches(_TAKEOVER_LABEL, page), key=lambda m: m[1])

    assert len(strips) == len(_SYSTEMS) == len(labels)
    row_ys = [row_y for _, row_y in strips]
    assert row_ys == sorted(row_ys)
    row_spacing = (row_ys[-1] - row_ys[0]) / (len(row_ys) - 1)

    for (strip, row_y), system, label in zip(strips, _SYSTEMS, labels):
        top, bottom = row_y, row_y + strip.shape[0]
        _, name_y, _, name_h = _name_box(page, system)
        _, label_y, _, label_h = label
        assert top <= name_y and name_y + name_h <= bottom, f"{system}: name outside its strip"
        assert label_y + label_h <= bottom, f"{system}: timer line cut off"
        # Badge labels sit in the lower part of the row; the strip must stop above them.
        assert bottom - top < 0.5 * row_spacing, f"{system}: strip reaches into the badges"


def test_timer_strip_under_each_name_covers_its_timer_line(page: np.ndarray) -> None:
    frac = capture_cfg("territory", "timer_strip_frac", default=3.0)
    labels = sorted(find_all_template_matches(_TAKEOVER_LABEL, page), key=lambda m: m[1])

    for system, label in zip(_SYSTEMS, labels):
        y1, y2 = timer_strip_rows(_name_box(page, system), page.shape[0], frac)
        label_center = label[1] + label[3] / 2
        assert y1 <= label_center <= y2, f"{system}: timer strip {y1}..{y2} misses the timer at {label_center}"
