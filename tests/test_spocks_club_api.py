# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-17
"""Contract tests for /api/spocks-club and factions.spocks_resource_id, against a real Postgres schema."""
import io
from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.views.spocks_club_view import MAX_EXPORT_BYTES
from tests.api_helpers import create_faction

pytestmark = pytest.mark.db

FED_ID = 970475396
ROM_ID = 4135751670  # above 2**31, so it must round-trip as BIGINT
EXPORT_NAME = "spocksclub-data-export_2026-11-13T01-13-36-913Z.tsv"
EXPORT_TIME = "2026-11-13T01:13:36.913000+00:00"


def _export_bytes(*rows: str) -> bytes:
    header = "EntityId\tEntityType\tName\tDescription\tField\tValue"
    return ("﻿" + "\r\n".join((header, *rows)) + "\r\n").encode("utf-8")


SAMPLE = _export_bytes(
    f"{FED_ID}\tresource\tFederation Points\t\tamount\t1048139084",
    f"{ROM_ID}\tresource\tRomulan Points\t\tamount\t10000000",
    "0\tbuilding\tOperations\tHQ\tlevel\t45",
)


def _preview(client: FlaskClient, content: bytes = SAMPLE, filename: str = EXPORT_NAME, **form: str):
    data = {"file": (io.BytesIO(content), filename), **form}
    return client.post("/api/spocks-club/preview", data=data, content_type="multipart/form-data")


def _mapped_factions(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation", display_order=1, spocks_resource_id=FED_ID)
    create_faction(client, "ROM", "Romulan", display_order=2, spocks_resource_id=ROM_ID)
    create_faction(client, "MAV", "Maverick", display_order=3)


def test_resource_id_round_trips_through_the_factions_api(client: FlaskClient) -> None:
    created = create_faction(client, "ROM", "Romulan", spocks_resource_id=ROM_ID)
    assert created["spocks_resource_id"] == ROM_ID

    [listed] = client.get("/api/factions/").get_json()
    assert listed["spocks_resource_id"] == ROM_ID

    cleared = client.put("/api/factions/ROM", json={"code": "ROM", "name": "Romulan", "spocks_resource_id": ""})
    assert cleared.status_code == 200
    assert client.get("/api/factions/").get_json()[0]["spocks_resource_id"] is None


def test_two_factions_cannot_share_a_resource_id(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation", spocks_resource_id=FED_ID)

    response = client.post("/api/factions/", json={"code": "DUP", "name": "Dup", "spocks_resource_id": FED_ID})

    assert response.status_code == 409
    assert str(FED_ID) in response.get_json()["error"]


def test_preview_maps_factions_and_takes_the_time_from_the_filename(client: FlaskClient) -> None:
    _mapped_factions(client)
    assert client.post("/api/status_entries/", json={"faction": "Federation", "value": 1000}).status_code == 201

    response = _preview(client)

    assert response.status_code == 200
    body = response.get_json()
    assert (body["exported_at"], body["exported_at_source"]) == (EXPORT_TIME, "filename")
    assert body["unmatched"] == ["Maverick"]
    fed, rom = body["readings"]
    assert (fed["faction_code"], fed["value"], fed["previous_value"]) == ("FED", 1048139084, 1000)
    assert fed["previous_updated"]
    assert (rom["faction_code"], rom["value"], rom["previous_value"]) == ("ROM", 10000000, None)


def test_preview_falls_back_to_the_file_date_then_now(client: FlaskClient) -> None:
    modified = datetime(2026, 11, 17, 16, 40, 15, tzinfo=UTC)

    by_date = _preview(client, filename="export.tsv", last_modified=str(int(modified.timestamp() * 1000))).get_json()
    by_now = _preview(client, filename="export.tsv").get_json()

    assert (by_date["exported_at"], by_date["exported_at_source"]) == (modified.isoformat(), "file_modified")
    assert by_now["exported_at_source"] == "now"
    assert abs(datetime.fromisoformat(by_now["exported_at"]) - datetime.now(UTC)) < timedelta(minutes=1)


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (b"\xff\xfe\x00not utf-8", 400),
        (b"name,value\nfoo,1\n", 400),
    ],
)
def test_preview_rejects_files_that_are_not_exports(client: FlaskClient, content: bytes, status: int) -> None:
    response = _preview(client, content=content)

    assert response.status_code == status
    assert "Spock's Club" in response.get_json()["error"] or ".tsv" in response.get_json()["error"]


def test_preview_without_a_file_is_400(client: FlaskClient) -> None:
    response = client.post("/api/spocks-club/preview", data={}, content_type="multipart/form-data")

    assert response.status_code == 400


def test_import_saves_every_reading_at_the_export_time(client: FlaskClient) -> None:
    _mapped_factions(client)
    readings = [{"faction_code": "FED", "value": 1048139084}, {"faction_code": "ROM", "value": 10000000}]

    response = client.post("/api/spocks-club/import", json={"exported_at": EXPORT_TIME, "readings": readings})

    assert response.status_code == 201
    body = response.get_json()
    assert body["skipped"] == []
    assert [(e["faction_code"], e["value"], e["timestamp"]) for e in body["saved"]] == [
        ("FED", 1048139084, EXPORT_TIME),
        ("ROM", 10000000, EXPORT_TIME),
    ]
    stored = client.get("/api/status_entries/all").get_json()
    assert {(e["faction_code"], e["value"], e["timestamp"]) for e in stored} == {
        ("FED", 1048139084, EXPORT_TIME),
        ("ROM", 10000000, EXPORT_TIME),
    }


def test_importing_the_same_export_twice_adds_nothing(client: FlaskClient) -> None:
    _mapped_factions(client)
    body = {"exported_at": EXPORT_TIME, "readings": [{"faction_code": "FED", "value": 5}]}
    assert client.post("/api/spocks-club/import", json=body).status_code == 201

    again = client.post("/api/spocks-club/import", json=body)

    assert again.status_code == 201
    assert again.get_json() == {"saved": [], "skipped": ["FED"]}
    assert len(client.get("/api/status_entries/all").get_json()) == 1


def test_unknown_faction_saves_nothing(client: FlaskClient) -> None:
    _mapped_factions(client)
    body = {
        "exported_at": EXPORT_TIME,
        "readings": [{"faction_code": "FED", "value": 5}, {"faction_code": "NOPE", "value": 6}],
    }

    response = client.post("/api/spocks-club/import", json=body)

    assert response.status_code == 404
    assert client.get("/api/status_entries/all").get_json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"exported_at": EXPORT_TIME, "readings": []},
        {"exported_at": "2026-11-13T01:13:36", "readings": [{"faction_code": "FED", "value": 1}]},  # no offset
        {"exported_at": "2999-01-01T00:00:00Z", "readings": [{"faction_code": "FED", "value": 1}]},
        {
            "exported_at": EXPORT_TIME,
            "readings": [{"faction_code": "FED", "value": 1}, {"faction_code": "FED", "value": 2}],
        },
    ],
    ids=["no readings", "naive time", "future", "faction twice"],
)
def test_import_rejects_bad_bodies(client: FlaskClient, body: dict) -> None:
    _mapped_factions(client)

    assert client.post("/api/spocks-club/import", json=body).status_code == 400


# ai: claude-opus-5-5 | 2026-11-18
def test_global_request_cap_leaves_room_for_a_full_size_export(flask_app: Flask) -> None:
    """The app-wide MAX_CONTENT_LENGTH must never be what rejects a valid export."""
    assert flask_app.config["MAX_CONTENT_LENGTH"] > MAX_EXPORT_BYTES


def test_request_over_the_global_cap_is_a_json_413(client: FlaskClient, flask_app: Flask) -> None:
    oversized = io.BytesIO(b"x" * (flask_app.config["MAX_CONTENT_LENGTH"] + 1))

    response = client.post(
        "/api/spocks-club/preview",
        data={"file": (oversized, EXPORT_NAME)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.is_json
    assert response.get_json()["error"]
