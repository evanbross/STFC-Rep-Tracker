# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Contract tests for /api/territory/systems against a real Postgres schema."""
import pytest
from flask.testing import FlaskClient

from app import google_calendar

pytestmark = pytest.mark.db

_SYSTEMS = "/api/territory/systems"


def test_crud_round_trip(client: FlaskClient) -> None:
    created = client.post(_SYSTEMS, json={"name": "Vulcan", "day_of_week": 2, "event_time": "18:30"})
    assert created.status_code == 200
    system = created.get_json()
    assert {k: system[k] for k in ("name", "day_of_week", "event_time")} == {
        "name": "Vulcan", "day_of_week": 2, "event_time": "18:30",
    }

    updated = client.put(
        f"{_SYSTEMS}/{system['id']}", json={"name": "Vulcan", "day_of_week": 3, "event_time": "07:05"}
    )
    assert updated.status_code == 200
    assert (updated.get_json()["day_of_week"], updated.get_json()["event_time"]) == (3, "07:05")

    assert [s["id"] for s in client.get(_SYSTEMS).get_json()] == [system["id"]]

    assert client.delete(f"{_SYSTEMS}/{system['id']}").status_code == 200
    assert client.delete(f"{_SYSTEMS}/{system['id']}").status_code == 404
    assert client.get(_SYSTEMS).get_json() == []


def test_post_same_name_upserts(client: FlaskClient) -> None:
    first = client.post(_SYSTEMS, json={"name": "Risa", "day_of_week": 0, "event_time": "10:00"}).get_json()
    second = client.post(_SYSTEMS, json={"name": "Risa", "day_of_week": 5, "event_time": "11:00"}).get_json()

    assert second["id"] == first["id"]
    assert second["day_of_week"] == 5


def test_update_unknown_is_404(client: FlaskClient) -> None:
    response = client.put(f"{_SYSTEMS}/999999", json={"name": "X", "day_of_week": 1, "event_time": "01:00"})

    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"day_of_week": 1, "event_time": "01:00"},
        {"name": "X", "day_of_week": 7, "event_time": "01:00"},
        {"name": "X", "day_of_week": "1", "event_time": "01:00"},
        {"name": "X", "day_of_week": 1, "event_time": "  "},
    ],
)
def test_invalid_body_is_400(client: FlaskClient, body: dict) -> None:
    assert client.post(_SYSTEMS, json=body).status_code == 400


# ai: claude-opus-5-5 | 2026-11-06
def test_crud_does_not_wait_on_the_calendar(client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a calendar connected, only check-calendar may call it (N-P5)."""
    calls: list[int] = []

    def fake_check(systems: list[dict]) -> list[dict]:
        calls.append(len(systems))
        for system in systems:
            system["calendar_event"] = False
        return systems

    monkeypatch.setattr(google_calendar, "is_authenticated", lambda: True)
    monkeypatch.setattr(google_calendar, "check_territory_systems", fake_check)

    system = client.post(_SYSTEMS, json={"name": "Vulcan", "day_of_week": 2, "event_time": "18:30"}).get_json()
    client.put(f"{_SYSTEMS}/{system['id']}", json={"name": "Vulcan", "day_of_week": 3, "event_time": "07:05"})
    listed = client.get(_SYSTEMS).get_json()

    assert calls == []
    assert "calendar_event" not in listed[0]

    checked = client.post(f"{_SYSTEMS}/check-calendar").get_json()

    assert calls == [1]
    assert checked[0]["calendar_event"] is False
