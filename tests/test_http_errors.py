# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-17
"""Werkzeug HTTP errors under /api/ come back as {"error": ...} JSON.

Regression: a backend started before the Spock's Club routes existed answered
POST /api/spocks-club/preview with the SPA catch-all's HTML 405 page, and the UI
could only say "Couldn't read that export."
"""
import pytest
from flask import Flask, abort
from flask.testing import FlaskClient

from app.views.validation import register_error_handlers


@pytest.fixture(name="client")
def fixture_client() -> FlaskClient:
    app = Flask("http_errors_test")
    register_error_handlers(app)

    @app.route("/api/things/<name>")
    def get_thing(name: str):
        abort(404)

    # Mirrors main.py's GET-only catch-all that serves the React app.
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_react(path: str):
        return "<html>spa</html>"

    return app.test_client()


def test_unrouted_api_post_explains_restart(client: FlaskClient) -> None:
    response = client.post("/api/spocks-club/preview")

    assert response.status_code == 405
    assert response.is_json
    assert "POST /api/spocks-club/preview" in response.json["error"]
    assert "restart the backend" in response.json["error"]


def test_unrouted_api_delete_explains_restart(client: FlaskClient) -> None:
    response = client.delete("/api/nope")

    assert response.status_code == 405
    assert "restart the backend" in response.json["error"]


def test_abort_inside_a_route_keeps_its_own_description(client: FlaskClient) -> None:
    response = client.get("/api/things/missing")

    assert response.status_code == 404
    assert response.is_json
    assert "restart" not in response.json["error"]


def test_non_api_errors_stay_html(client: FlaskClient) -> None:
    response = client.post("/factions")

    assert response.status_code == 405
    assert not response.is_json
