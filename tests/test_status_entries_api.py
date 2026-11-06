# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Contract tests for /api/status_entries against a real Postgres schema."""
import pytest
from flask.testing import FlaskClient

from app.database.database import Database
from tests.api_helpers import create_faction, insert_entries

pytestmark = pytest.mark.db


def test_post_then_get(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    response = client.post("/api/status_entries/", json={"faction": "Federation", "value": 1234})

    assert response.status_code == 201
    body = response.get_json()
    assert (body["faction_code"], body["value"]) == ("FED", 1234)
    assert body["timestamp"]

    [entry] = client.get("/api/status_entries/all").get_json()
    assert set(entry) == {"id", "faction_code", "faction_name", "timestamp", "value"}
    assert (entry["faction_name"], entry["value"]) == ("Federation", 1234)

    [by_faction] = client.get("/api/status_entries/Federation").get_json()
    assert set(by_faction) == {"timestamp", "value", "value_delta", "faction_code"}


def test_post_unknown_faction_is_404(client: FlaskClient) -> None:
    response = client.post("/api/status_entries/", json={"faction": "Nobody", "value": 1})

    assert response.status_code == 404


@pytest.mark.parametrize("body", [{"faction": "Federation"}, {"value": 5}])
def test_post_missing_fields_is_400(client: FlaskClient, body: dict) -> None:
    assert client.post("/api/status_entries/", json=body).status_code == 400


def test_post_non_numeric_value_is_400(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    response = client.post("/api/status_entries/", json={"faction": "Federation", "value": "abc"})

    assert response.status_code == 400


def test_sort_limit_offset(client: FlaskClient, db: Database) -> None:
    create_faction(client, "FED", "Federation")
    insert_entries(db, "FED", {0: 30, 1: 10, 2: 20})

    response = client.get("/api/status_entries/?sort=value DESC&limit=2&offset=1")

    assert response.status_code == 200
    assert [e["value"] for e in response.get_json()] == [20, 10]


def test_invalid_sort_is_400(client: FlaskClient) -> None:
    response = client.get("/api/status_entries/?sort=value; DROP TABLE factions")

    assert response.status_code == 400


# ai: claude-opus-5-5 | 2026-11-06
def test_days_keeps_only_recent_entries(client: FlaskClient, db: Database) -> None:
    """The Dashboard asks for a recent window instead of the whole history (N-P3)."""
    create_faction(client, "FED", "Federation")
    insert_entries(db, "FED", {0: 1})                       # 2026-01-01: long before the window
    assert client.post("/api/status_entries/", json={"faction": "Federation", "value": 2}).status_code == 201

    recent = client.get("/api/status_entries/all?days=30").get_json()
    everything = client.get("/api/status_entries/all").get_json()

    assert [e["value"] for e in recent] == [2]
    assert [e["value"] for e in everything] == [1, 2]


# ai: claude-opus-5-5 | 2026-11-06
@pytest.mark.parametrize("query", ["days=0", "days=abc", "limit=-1", "offset=x"])
def test_invalid_query_parameter_is_400(client: FlaskClient, query: str) -> None:
    """Bad numbers used to be dropped silently, returning the full history instead."""
    response = client.get(f"/api/status_entries/?{query}")

    assert response.status_code == 400
    assert "fields" in response.get_json()
