# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Calendar matching: one events.list call per check, matched in memory (N-P5).

Google is never called; a fake service records the list requests it receives.
"""
from datetime import UTC, datetime, timedelta

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from app import google_calendar
from app.google_calendar import check_events_exist, check_territory_systems, match_events

DAY = (datetime(2026, 11, 9, tzinfo=UTC), datetime(2026, 11, 10, tzinfo=UTC))


def _event(summary: str, start: str, end: str) -> dict:
    key = "dateTime" if "T" in start else "date"
    return {"summary": summary, "start": {key: start}, "end": {key: end}}


class _FakeEvents:
    def __init__(self, pages: list[list[dict]], error: Exception | None) -> None:
        self.pages = pages
        self.error = error
        self.requests: list[dict] = []

    def list(self, **kwargs: object) -> "_FakeEvents":
        self.requests.append(kwargs)
        return self

    def execute(self) -> dict:
        if self.error:
            raise self.error
        index = len(self.requests) - 1
        result: dict = {"items": self.pages[index]}
        if index + 1 < len(self.pages):
            result["nextPageToken"] = f"page{index + 1}"
        return result


class _FakeService:
    def __init__(self, pages: list[list[dict]], error: Exception | None = None) -> None:
        self.fake_events = _FakeEvents(pages, error)

    def events(self) -> _FakeEvents:
        return self.fake_events


@pytest.fixture(name="install_service")
def fixture_install_service(monkeypatch: pytest.MonkeyPatch):
    def install(pages: list[list[dict]], error: Exception | None = None) -> _FakeService:
        service = _FakeService(pages, error)
        monkeypatch.setattr(google_calendar, "_build_service", lambda: service)
        return service
    return install


def test_match_is_case_insensitive_title_substring() -> None:
    events = [_event("Territory Capture - KALANDRA", "2026-11-09T18:00:00+00:00", "2026-11-09T19:00:00+00:00")]

    assert match_events("Kalandra", DAY, events) == {
        "summary": "Territory Capture - KALANDRA", "start": "2026-11-09T18:00:00+00:00",
    }


def test_match_ignores_events_outside_the_day() -> None:
    events = [_event("Kalandra", "2026-11-10T00:00:00+00:00", "2026-11-10T01:00:00+00:00")]

    assert match_events("Kalandra", DAY, events) is False


def test_match_counts_all_day_and_overlapping_events() -> None:
    all_day = [_event("Kalandra", "2026-11-09", "2026-11-10")]
    overnight = [_event("Kalandra", "2026-11-08T23:00:00+00:00", "2026-11-09T01:00:00+00:00")]

    assert match_events("Kalandra", DAY, all_day)["start"] == "2026-11-09"
    assert match_events("Kalandra", DAY, overnight) is not False


def test_match_skips_malformed_events() -> None:
    events = [{"summary": "Kalandra", "start": {}}, _event("Kalandra", "2026-11-09", "2026-11-10")]

    assert match_events("Kalandra", DAY, events)["start"] == "2026-11-09"


def test_all_systems_share_one_list_call(install_service) -> None:
    service = install_service([[]])
    systems = [{"name": f"S{d}", "day_of_week": d, "event_time": "12:00"} for d in range(7)]

    check_territory_systems(systems)

    assert len(service.fake_events.requests) == 1
    assert [s["calendar_event"] for s in systems] == [False] * 7
    span = service.fake_events.requests[0]
    assert datetime.fromisoformat(span["timeMax"]) - datetime.fromisoformat(span["timeMin"]) <= timedelta(days=8)


def test_every_page_is_read(install_service) -> None:
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    start = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
    hit = _event("Kalandra", start.isoformat(), (start + timedelta(hours=1)).isoformat())
    service = install_service([[], [hit]])
    systems = [{"name": "Kalandra", "day_of_week": tomorrow.weekday(), "event_time": "13:00"}]

    check_territory_systems(systems)

    assert len(service.fake_events.requests) == 2
    assert service.fake_events.requests[1]["pageToken"] == "page1"
    assert systems[0]["calendar_event"]["summary"] == "Kalandra"


def test_lookup_failure_marks_every_scheduled_system(install_service) -> None:
    install_service([[]], error=HttpError(Response({"status": 500}), b"boom"))
    systems = [{"name": "A", "day_of_week": 1, "event_time": "12:00"}, {"name": "B", "day_of_week": 2, "event_time": "12:00"}]

    check_territory_systems(systems)

    assert {(s["calendar_event"], s["calendar_error"]) for s in systems} == {(None, "Calendar lookup failed")}


def test_unscheduled_system_is_none_and_others_still_checked(install_service) -> None:
    service = install_service([[]])
    systems = [{"name": "NoTime", "day_of_week": 1, "event_time": ""}, {"name": "B", "day_of_week": 2, "event_time": "12:00"}]

    check_territory_systems(systems)

    assert [s["calendar_event"] for s in systems] == [None, False]
    assert len(service.fake_events.requests) == 1


def test_nothing_to_check_makes_no_call(install_service) -> None:
    service = install_service([[]])

    check_events_exist([{"name": "Bad", "event_time": "not a date"}])

    assert service.fake_events.requests == []


def test_not_authenticated_is_reported_on_every_system(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_authenticated() -> None:
        raise RuntimeError("Google Calendar is not authenticated.")
    monkeypatch.setattr(google_calendar, "_build_service", not_authenticated)
    systems = [{"name": "A", "day_of_week": 1, "event_time": "12:00"}]

    check_territory_systems(systems)

    assert systems[0]["calendar_event"] is None
    assert "not authenticated" in systems[0]["calendar_error"]
