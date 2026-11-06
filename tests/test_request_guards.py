# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Pure tests for the cross-origin write decision (no Flask app, no DB)."""
import pytest

from app.request_guards import is_trusted_api_write_origin

SELF = "http://localhost:7300"
CORS = ["http://localhost:5173", "http://stfc.localhost"]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (None, True),                                      # curl / test client / community mod
        ("", True),
        ("http://localhost:7300", True),                   # the app's own pages
        ("http://LOCALHOST:7300", True),                   # origins compare case-insensitively
        ("http://localhost:5173", True),                   # Vite dev server (CORS list)
        ("http://stfc.localhost/factions?x=1", True),      # Referer form: path is ignored
        ("https://evil.example", False),
        ("http://localhost:8080", False),                  # another local app is still foreign
        ("https://localhost:7300", False),                 # scheme is part of the origin
        ("null", False),                                   # sandboxed iframe / file:// page
        ("http://localhost:7300.evil.example", False),     # prefix match must not pass
    ],
)
def test_is_trusted_api_write_origin(source: str | None, expected: bool) -> None:
    assert is_trusted_api_write_origin(source, SELF, CORS) is expected


def test_blank_cors_entries_are_ignored() -> None:
    # CORS_ORIGINS="" splits to [""]; that must not make "://" a trusted origin.
    assert is_trusted_api_write_origin("null", SELF, [""]) is False
