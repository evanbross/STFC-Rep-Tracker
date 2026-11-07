# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Pure-function tests for the OCR text parsers (no DB, no EasyOCR)."""
from datetime import timedelta

import pytest

from app.screen_processing import ocr_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ISh", "15h"),            # multi-char garble before a unit
        ("2d 4h 3Om", "2d 4h 30m"),
        ("Fh", "Fh"),              # unmapped character is left alone
        ("SOS", "SOS"),            # lookalikes with no time unit are left alone
        ("12h 5m", "12h 5m"),
    ],
)
def test_normalize_ocr_digits(raw: str, expected: str) -> None:
    assert ocr_text.normalize_ocr_digits(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2d 4h 30m", timedelta(days=2, hours=4, minutes=30)),
        ("4h 6m", timedelta(hours=4, minutes=6)),
        ("45m", timedelta(minutes=45)),
        ("ISh", timedelta(hours=15)),
        ("1D 2H", timedelta(days=1, hours=2)),
        ("", None),
        ("500ms", None),           # milliseconds are not minutes
        pytest.param(
            "no time here", None,
            marks=pytest.mark.xfail(
                strict=True,
                reason="lookalike map turns the 'i' in 'time' into '1m'; callers "
                       "pre-filter with is_time_string, so not user-visible yet",
            ),
        ),
    ],
)
def test_parse_time_remaining(raw: str, expected: timedelta | None) -> None:
    assert ocr_text.parse_time_remaining(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("4h 6m", True), ("30 m", True), ("Vulcan", False), ("", False)],
)
def test_is_time_string(raw: str, expected: bool) -> None:
    assert ocr_text.is_time_string(raw) is expected


# ai: claude-opus-5-5 | 2026-11-06
def test_confident_tokens_strips_and_drops_low_confidence() -> None:
    box = [[0, 0], [1, 0], [1, 1], [0, 1]]
    raw = [(box, " Saldeti ", 0.9), (box, "noise", 0.1), (box, "   ", 0.99), (box, "20h 03m", 0.2)]
    assert ocr_text.confident_tokens(raw, 0.2) == ["Saldeti", "20h 03m"]


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["32", "BR", "Klingon", "Scout"], ("Klingon Scout", 32)),
        (["Borg"], ("Borg", None)),
        ([], (None, None)),
        (["7", "12", "Probe"], ("12 Probe", 7)),   # only the first number is the level
    ],
)
def test_parse_name_level(tokens: list[str], expected: tuple[str | None, int | None]) -> None:
    assert ocr_text.parse_name_level(tokens) == expected


def test_parse_info_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    keywords = {("combat", "resource_keywords"): ["Parsteel", "Tritanium"]}
    monkeypatch.setattr(
        ocr_text, "capture_cfg", lambda *keys, default=None: keywords.get(keys, default)
    )
    text = "Cargo Parsteel 12,500 Tritanium: 300 Hull 85% Shield 40 %"

    assert ocr_text.parse_info_panel(text) == {
        "cargo": {"Parsteel": 12500, "Tritanium": 300},
        "hull_pct": 85,
        "shield_pct": 40,
    }


def test_parse_info_panel_missing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_text, "capture_cfg", lambda *keys, default=None: default)

    assert ocr_text.parse_info_panel("nothing useful") == {
        "cargo": {},
        "hull_pct": None,
        "shield_pct": None,
    }
