# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-19
"""Community-mod payloads update faction reputation, against a real Postgres schema.

The capture file is redirected to tmp_path so nothing here appends to the real one.
"""
from datetime import datetime, UTC
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from app.database.database import Database
from app.views import community_mod_view
from tests.api_helpers import create_faction

pytestmark = pytest.mark.db

_URL = "/api/community-mod/"
FED_ID = 970475396
ROM_ID = 4135751670  # above 2**31, as some game resource IDs are


@pytest.fixture(name="mod_client")
def fixture_mod_client(client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    monkeypatch.setattr(community_mod_view, "_CAPTURE_FILE", str(tmp_path / "community-data.jsonl"))
    create_faction(client, "FED", "Federation", display_order=1, spocks_resource_id=FED_ID)
    create_faction(client, "ROM", "Romulan", display_order=2, spocks_resource_id=ROM_ID)
    create_faction(client, "MAV", "Maverick", display_order=3)  # no resource ID
    return client


def _resources(amounts_by_rid: dict[int, int]) -> list[dict]:
    return [{"type": "resource", "rid": rid, "amount": amount} for rid, amount in amounts_by_rid.items()]


def _post(client: FlaskClient, payload: object) -> int:
    response = client.post(_URL, json=payload)
    assert response.status_code == 200
    return response.get_json()["readings_saved"]


def _entries(db: Database) -> list[tuple[str, int, datetime]]:
    with db.connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT faction_code, value, timestamp FROM status_entries ORDER BY id")
        return cursor.fetchall()


def test_mapped_resources_are_saved_at_the_receive_time(mod_client: FlaskClient, db: Database) -> None:
    before = datetime.now(UTC)

    saved = _post(mod_client, _resources({FED_ID: 1045097591, ROM_ID: 52, 908921776: 828291}))

    assert saved == 2
    entries = _entries(db)
    assert sorted((code, value) for code, value, _ in entries) == [("FED", 1045097591), ("ROM", 52)]
    assert all(before <= moment <= datetime.now(UTC) for _, _, moment in entries)
    summary = {f["code"]: f for f in mod_client.get("/api/factions/summary").get_json()}
    assert summary["FED"]["current_value"] == 1045097591


def test_unchanged_values_are_not_saved_again(mod_client: FlaskClient, db: Database) -> None:
    _post(mod_client, _resources({FED_ID: 100, ROM_ID: 50}))

    assert _post(mod_client, _resources({FED_ID: 100, ROM_ID: 50})) == 0
    assert _post(mod_client, _resources({FED_ID: 150, ROM_ID: 50})) == 1

    assert [(code, value) for code, value, _ in _entries(db)] == [("FED", 100), ("ROM", 50), ("FED", 150)]


def test_a_value_is_compared_with_the_latest_entry_not_any_entry(mod_client: FlaskClient, db: Database) -> None:
    for value in (100, 150, 100):
        _post(mod_client, _resources({FED_ID: value}))

    assert [value for _, value, _ in _entries(db)] == [100, 150, 100]


@pytest.mark.parametrize("payload", [
    [{"type": "officer", "oid": 1, "level": 30}],
    [{"type": "resource", "rid": 908921776, "amount": 828291}],
    {"type": "resource", "rid": FED_ID, "amount": 5},
])
def test_payloads_without_mapped_resources_save_nothing(
    mod_client: FlaskClient, db: Database, payload: object
) -> None:
    assert _post(mod_client, payload) == 0
    assert _entries(db) == []


def test_a_save_sends_a_readings_event(mod_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(community_mod_view, "_KEEPALIVE_SECONDS", 0.05)
    stream = community_mod_view.capture_event_stream()
    assert next(stream).startswith("retry:")

    _post(mod_client, _resources({FED_ID: 100}))

    assert next(stream).startswith("event: capture\n")
    assert next(stream) == "event: readings\ndata: {}\n\n"
    stream.close()


def test_an_unchanged_payload_sends_no_readings_event(mod_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _post(mod_client, _resources({FED_ID: 100}))
    monkeypatch.setattr(community_mod_view, "_KEEPALIVE_SECONDS", 0.05)
    stream = community_mod_view.capture_event_stream()
    assert next(stream).startswith("retry:")

    _post(mod_client, _resources({FED_ID: 100}))

    assert next(stream).startswith("event: capture\n")
    assert next(stream) == ": keepalive\n\n"
    stream.close()
