# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Snippet image routes serve images only (N-X2), from a temp snippets directory."""
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from app import snippet_store
from app.views import snippet_files

pytestmark = pytest.mark.db

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture(name="snippets")
def fixture_snippets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "snippets"
    (root / "target_samples").mkdir(parents=True)
    (root / "Selected-Desc-FED.png").write_bytes(_PNG)
    (root / "target_samples" / "Sol_scout.png").write_bytes(_PNG)
    (root / "favicon.zip").write_bytes(b"PK\x03\x04")
    (tmp_path / "outside.png").write_bytes(_PNG)
    monkeypatch.setattr(snippet_store, "_configured_dir", lambda: str(root))
    return root


@pytest.mark.parametrize(
    "url",
    ["/api/factions/snippet-image/Selected-Desc-FED.png", "/api/target-types/sample-image/target_samples/Sol_scout.png"],
)
def test_images_are_served(client: FlaskClient, snippets: Path, url: str) -> None:
    response = client.get(url)

    assert response.status_code == 200
    assert response.data == _PNG


@pytest.mark.parametrize(
    "url",
    [
        "/api/factions/snippet-image/favicon.zip",
        "/api/target-types/sample-image/favicon.zip",
        "/api/factions/snippet-image/../outside.png",
        "/api/factions/snippet-image/missing.png",
    ],
)
def test_non_images_and_escapes_are_404(client: FlaskClient, snippets: Path, url: str) -> None:
    assert client.get(url).status_code == 404


@pytest.mark.parametrize(("name", "expected"), [("a.PNG", True), ("a.jpeg", True), ("a.zip", False), ("png", False)])
def test_is_snippet_image(name: str, expected: bool) -> None:
    assert snippet_files.is_snippet_image(name) is expected
