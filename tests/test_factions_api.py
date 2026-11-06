# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Contract tests for /api/factions against a real Postgres schema."""
import pytest
from flask.testing import FlaskClient

from app.database.database import Database
from tests.api_helpers import create_faction, create_fkr_faction, insert_entries

pytestmark = pytest.mark.db


def test_create_and_list(client: FlaskClient) -> None:
    created = create_faction(client, "FED", "Federation")

    assert created["code"] == "FED"
    assert created["id"] == "FED"
    listed = client.get("/api/factions/").get_json()
    assert [f["code"] for f in listed] == ["FED"]
    assert listed[0]["selected_snippets"] == []


def test_create_requires_name_and_code(client: FlaskClient) -> None:
    response = client.post("/api/factions/", json={"name": "No Code"})

    assert response.status_code == 400


def test_rename_code_cascades_to_status_entries(client: FlaskClient) -> None:
    create_faction(client, "ROM", "Romulan")
    assert client.post("/api/status_entries/", json={"faction": "Romulan", "value": 42}).status_code == 201

    response = client.put("/api/factions/ROM", json={"code": "RSE", "name": "Romulan"})

    assert response.status_code == 200
    entries = client.get("/api/status_entries/Romulan").get_json()
    assert [e["faction_code"] for e in entries] == ["RSE"]


def test_update_unknown_faction_is_404(client: FlaskClient) -> None:
    response = client.put("/api/factions/NOPE", json={"code": "NOPE", "name": "Nobody"})

    assert response.status_code == 404


@pytest.mark.xfail(strict=True, reason="N-S3: duplicate create returns 400, should be 409 (Phase 2)")
def test_duplicate_create_is_409(client: FlaskClient) -> None:
    create_faction(client, "KLI", "Klingon")

    response = client.post("/api/factions/", json={"code": "KLI", "name": "Klingon"})

    assert response.status_code == 409


@pytest.mark.xfail(strict=True, reason="N-S3: duplicate rename returns 404, should be 409 (Phase 2)")
def test_duplicate_update_is_409(client: FlaskClient) -> None:
    create_faction(client, "KLI", "Klingon")
    create_faction(client, "ROM", "Romulan", display_order=2)

    response = client.put("/api/factions/ROM", json={"code": "KLI", "name": "Romulan"})

    assert response.status_code == 409


def test_selected_snippets_empty_for_new_faction(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    response = client.get("/api/factions/FED/selected-snippets")

    assert response.status_code == 200
    assert response.get_json() == []


@pytest.mark.usefixtures("fixed_avg_window")
def test_summary_numbers(client: FlaskClient, db: Database) -> None:
    create_fkr_faction(client, db, "FED", "Federation")
    # 1000 → 2000 → 4000 over 20 minutes: last step +2000 in 10 min (200/min),
    # averaged over the window +3000 in 20 min (150/min).
    insert_entries(db, "FED", {0: 1000, 10: 2000, 20: 4000})

    [summary] = client.get("/api/factions/summary").get_json()

    assert summary["current_value"] == 4000
    assert summary["last_delta"] == 2000
    assert summary["entry_count"] == 3
    assert summary["rep_level"] == "Tolerated"            # FKR tier 500..4999
    status = summary["status"]
    assert status["raw_value_delta_per_minute"] == pytest.approx(200.0)
    assert status["avg_value_delta_per_minute"] == pytest.approx(150.0)
    assert status["next_rep_level"] == "Neighbor"
    assert status["goal_value"] == 5000
    assert status["minutes_to_goal"] == pytest.approx(6.66)   # (4999 - 4000) / 150


def test_summary_without_entries(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    [summary] = client.get("/api/factions/summary").get_json()

    assert summary["current_value"] == 0
    assert summary["last_updated"] is None
    assert summary["rep_level"] == "Unknown"


def test_summary_sort_descending(client: FlaskClient, db: Database) -> None:
    create_faction(client, "AAA", "Alpha", display_order=1)
    create_faction(client, "BBB", "Bravo", display_order=2)
    insert_entries(db, "AAA", {0: 10})
    insert_entries(db, "BBB", {0: 99})

    summary = client.get("/api/factions/summary?sort=-current_value").get_json()

    assert [s["code"] for s in summary] == ["BBB", "AAA"]
