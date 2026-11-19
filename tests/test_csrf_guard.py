# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Cross-origin write protection (R2)."""
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from app.views import community_mod_view
from tests.api_helpers import create_faction

pytestmark = pytest.mark.db

_ENTRY = '{"faction": "Federation", "value": 1}'


def test_cross_origin_write_is_rejected(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    # A text/plain body is what a hostile page can send without a CORS preflight.
    response = client.post(
        "/api/status_entries/", data=_ENTRY, content_type="text/plain",
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert client.get("/api/status_entries/all").get_json() == []


def test_cross_origin_referer_is_rejected(client: FlaskClient) -> None:
    response = client.post(
        "/api/capture-screen/reputations", headers={"Referer": "https://evil.example/page"},
    )

    assert response.status_code == 403


def test_same_origin_write_is_allowed(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    response = client.post(
        "/api/status_entries/",
        json={"faction": "Federation", "value": 1},
        headers={"Origin": "http://localhost"},
    )

    assert response.status_code == 201


def test_cors_listed_origin_is_allowed(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    response = client.post(
        "/api/status_entries/",
        json={"faction": "Federation", "value": 1},
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 201


def test_cross_origin_read_is_not_blocked(client: FlaskClient) -> None:
    response = client.get("/api/factions/", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200


def test_text_plain_body_is_not_parsed_as_json(client: FlaskClient) -> None:
    """Without force=True a non-JSON content type is not treated as JSON."""
    create_faction(client, "FED", "Federation")

    response = client.post("/api/status_entries/", data=_ENTRY, content_type="text/plain")

    assert response.status_code == 400
    assert client.get("/api/status_entries/all").get_json() == []


# ai: claude-opus-5-5 | 2026-11-18
def test_community_mod_endpoint_rejects_browser_pages(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mod posts here with no Origin; a browser page on another origin must not.

    The capture file is redirected so a regression that lets the request through
    can never append test data to the real community-data file.
    """
    capture_file = tmp_path / "community-data.jsonl"
    monkeypatch.setattr(community_mod_view, "_CAPTURE_FILE", str(capture_file))

    response = client.post(
        "/api/community-mod/", json={"x": 1}, headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert "Access-Control-Allow-Origin" not in response.headers
    assert not capture_file.exists()
