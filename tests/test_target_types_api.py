# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Contract tests for /api/target-types against a real Postgres schema."""
import pytest
from flask.testing import FlaskClient

from app.database.database import Database

pytestmark = pytest.mark.db


def test_list_and_set_preference(client: FlaskClient, db: Database) -> None:
    seen = db.target_types.upsert_seen("Sol", "scout.png", display_name="Scout")
    db.target_types.upsert_seen("Sol", "scout.png")   # repeat sighting bumps the count

    [listed] = client.get("/api/target-types/system/Sol").get_json()
    assert (listed["id"], listed["preference"], listed["times_seen"]) == (seen["id"], "unknown", 2)

    response = client.put(f"/api/target-types/{seen['id']}", json={"preference": "target", "display_name": "Easy"})

    assert response.status_code == 200
    assert (response.get_json()["preference"], response.get_json()["display_name"]) == ("target", "Easy")


def test_other_system_is_empty(client: FlaskClient, db: Database) -> None:
    db.target_types.upsert_seen("Sol", "scout.png")

    assert client.get("/api/target-types/system/Vulcan").get_json() == []


def test_invalid_preference_is_400(client: FlaskClient, db: Database) -> None:
    seen = db.target_types.upsert_seen("Sol", "scout.png")

    assert client.put(f"/api/target-types/{seen['id']}", json={"preference": "maybe"}).status_code == 400


def test_unknown_id_is_404(client: FlaskClient) -> None:
    assert client.put("/api/target-types/999999", json={"preference": "avoid"}).status_code == 404
