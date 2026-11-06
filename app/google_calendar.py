# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
"""Google Calendar integration — read-only event lookup.

First-time setup:
  1. Download OAuth2 credentials from Google Cloud Console and save as the path
     configured under google_calendar.credentials_file in settings.yaml
     (default: google_credentials.json at the project root).
  2. Call run_auth_flow() once (exposed via POST /api/calendar/auth) to open the
     browser consent screen and write the token file.  Subsequent calls refresh
     the token automatically.

Only requires calendar.readonly scope.
"""

import logging
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.app_config import capture_cfg
from app.paths import runtime_path

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# ai: claude-opus-5-5 | 2026-11-06
def _credentials_path() -> str:
    return runtime_path(capture_cfg("google_calendar", "credentials_file"))


# ai: claude-opus-5-5 | 2026-11-06
def _token_path() -> str:
    return runtime_path(capture_cfg("google_calendar", "token_file"))


def _build_service():
    """Return an authenticated Google Calendar service.

    If no token exists or the token is unusable (expired scope, revoked, etc.),
    the OAuth2 browser flow is run automatically to obtain a fresh token.
    Raises if the credentials file is missing or the flow fails.
    """
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_file = _token_path()
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, _SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        except GoogleAuthError as e:
            # Stale token (scope mismatch, revocation, etc.) — delete and re-auth.
            logger.warning("Token refresh failed (%s) — running auth flow.", e)
            try:
                os.remove(token_file)
            except OSError:
                pass
            creds = None

    if not creds or not creds.valid:
        raise RuntimeError(
            "Google Calendar is not authenticated. "
            "Open the Territory Schedule and connect your calendar first."
        )

    return build("calendar", "v3", credentials=creds)


def is_authenticated() -> bool:
    """Return True if a valid (or refreshable) token exists."""
    from google.oauth2.credentials import Credentials

    token_file = _token_path()
    if not os.path.exists(token_file):
        return False
    try:
        creds = Credentials.from_authorized_user_file(token_file, _SCOPES)
        return creds.valid or (creds.expired and bool(creds.refresh_token))
    except Exception:
        return False


def run_auth_flow() -> dict:
    """Run the OAuth2 browser consent flow and save the resulting token.

    Must be called from a context where a browser can be opened (i.e. the
    machine running the Flask server).  Raises if credentials_file is missing.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds_file = _credentials_path()
    if not os.path.exists(creds_file):
        raise FileNotFoundError(
            f"Google credentials file not found: {creds_file}\n"
            "Download it from Google Cloud Console (OAuth 2.0 Client ID → Desktop app) "
            "and save it at that path."
        )

    flow = InstalledAppFlow.from_client_secrets_file(creds_file, _SCOPES)
    try:
        creds = flow.run_local_server(port=0)
    except OSError as e:
        import errno
        if e.errno in (errno.EACCES, 10013):
            raise RuntimeError(
                "Google OAuth2 flow failed: Windows blocked the local callback server.\n"
                "This usually means the OS has reserved most dynamic ports (common with Hyper-V/WSL).\n"
                "Run this in an admin terminal to check:\n"
                "  netsh int ipv4 show excludedportrange protocol=tcp\n"
                "To reset the dynamic port range:\n"
                "  netsh int ipv4 set dynamicport tcp start=49152 num=16384\n"
                "  (Restart required)"
            ) from e
        raise

    token_file = _token_path()
    with open(token_file, "w") as f:
        f.write(creds.to_json())

    logger.info("Google Calendar token saved to %s", token_file)
    return {"success": True, "token_file": token_file}


def _next_weekday_utc(day_of_week: int, utc_time_str: str) -> datetime:
    """Return the next UTC datetime for the given weekday (0=Mon…6=Sun) and 'HH:MM' time string."""
    hours, minutes = map(int, utc_time_str.split(":"))
    now = datetime.now(timezone.utc)
    days_ahead = day_of_week - now.weekday()
    # If the day is today but the time has already passed, push to next week
    if days_ahead < 0 or (
        days_ahead == 0 and (now.hour, now.minute) >= (hours, minutes)
    ):
        days_ahead += 7
    target = now + timedelta(days=days_ahead)
    return target.replace(hour=hours, minute=minutes, second=0, microsecond=0)


# ai: claude-opus-5-5 | 2026-11-06
# Calendar checks fetch every event in the span covering all systems with ONE
# events.list call, then match systems to events in memory (N-P5). They used
# to make one call per system.

DayBounds = tuple[datetime, datetime]


def _event_bounds(event: dict) -> DayBounds | None:
    """Start/end of a Google event as aware datetimes; all-day dates are read as UTC midnight."""
    try:
        start, end = event["start"], event["end"]
        if "dateTime" in start:
            return datetime.fromisoformat(start["dateTime"]), datetime.fromisoformat(end["dateTime"])
        return (
            datetime.fromisoformat(start["date"]).replace(tzinfo=timezone.utc),
            datetime.fromisoformat(end["date"]).replace(tzinfo=timezone.utc),
        )
    except (KeyError, TypeError, ValueError):
        return None


def match_events(name: str, bounds: DayBounds, events: list[dict]) -> dict | bool:
    """Return the first event (by start) overlapping bounds whose title contains name.

    Returns {"summary", "start"} for a hit, or False. The match is a
    case-insensitive substring of the title. Google's q search, used before,
    also matched descriptions and locations.
    """
    day_start, day_end = bounds
    needle = name.casefold()
    for event in events:
        event_bounds = _event_bounds(event)
        if event_bounds is None:
            continue
        starts, ends = event_bounds
        if starts < day_end and ends > day_start and needle in event.get("summary", "").casefold():
            return {
                "summary": event.get("summary", ""),
                "start": event["start"].get("dateTime", event["start"].get("date", "")),
            }
    return False


def _list_events(service, time_min: datetime, time_max: datetime) -> list[dict]:
    """Every event on the primary calendar overlapping [time_min, time_max), ordered by start."""
    events: list[dict] = []
    page_token = None
    while True:
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=2500,
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return events


def _mark_unavailable(systems: list[dict], message: str) -> None:
    for system in systems:
        system["calendar_event"] = None
        system["calendar_error"] = message


def _annotate_systems(systems: list[dict], day_bounds: Callable[[dict], DayBounds]) -> list[dict]:
    """Set calendar_event on each system from one events.list call.

    day_bounds(system) gives the day to search; a system whose bounds cannot
    be computed (missing or malformed time) gets calendar_event = None.
    The systems list is modified in-place and also returned.
    """
    from google.auth.exceptions import GoogleAuthError
    from googleapiclient.errors import HttpError
    from httplib2 import HttpLib2Error

    google_errors = (GoogleAuthError, HttpError, HttpLib2Error, OSError)
    try:
        service = _build_service()
    except RuntimeError as e:
        logger.warning("Google Calendar unavailable: %s", e)
        _mark_unavailable(systems, str(e))
        return systems
    except google_errors as e:
        logger.error("Google Calendar connection failed: %s", e)
        _mark_unavailable(systems, "Calendar connection failed")
        return systems

    bounds_by_index: dict[int, DayBounds] = {}
    for index, system in enumerate(systems):
        try:
            bounds_by_index[index] = day_bounds(system)
        except (KeyError, TypeError, ValueError):
            system["calendar_event"] = None
    if not bounds_by_index:
        return systems

    span_start = min(start for start, _ in bounds_by_index.values())
    span_end = max(end for _, end in bounds_by_index.values())
    try:
        events = _list_events(service, span_start, span_end)
    except google_errors as e:
        logger.error("Calendar lookup failed for %s to %s: %s", span_start.date(), span_end.date(), e)
        _mark_unavailable([systems[i] for i in bounds_by_index], "Calendar lookup failed")
        return systems

    for index, bounds in bounds_by_index.items():
        system = systems[index]
        system["calendar_event"] = match_events(system.get("name", ""), bounds, events)
        logger.info(
            "Calendar check for '%s' on %s: %s",
            system.get("name"), bounds[0].date(), "hit" if system["calendar_event"] else "no event",
        )
    return systems


def _whole_day(moment: datetime) -> DayBounds:
    day_start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start, day_start + timedelta(days=1)


def check_territory_systems(systems: list[dict]) -> list[dict]:
    """Check Google Calendar for events matching each territory schedule system.

    Each system dict must have 'name', 'day_of_week' (int 0-6), and 'event_time' ('HH:MM' UTC).
    Searches the primary calendar on the next occurrence of that weekday (UTC day) for an
    event whose title contains the system name.

    Adds a 'calendar_event' key to each system:
      - None   : calendar unavailable or check failed (with 'calendar_error' when unavailable)
      - False  : no matching event found on that day
      - dict   : {"summary": str, "start": str} of the first matching event

    The systems list is modified in-place and also returned.
    """
    def day_bounds(system: dict) -> DayBounds:
        if system.get("day_of_week") is None or not system.get("event_time"):
            raise ValueError("system has no schedule")
        return _whole_day(_next_weekday_utc(system["day_of_week"], system["event_time"]))

    return _annotate_systems(systems, day_bounds)


def list_calendars() -> list[dict]:
    """Return all calendars the authenticated user has access to.

    Each entry has 'id' and 'summary' keys.  Raises on auth failure.
    """
    service = _build_service()
    result = service.calendarList().list().execute()
    return [
        {"id": entry["id"], "summary": entry.get("summary", entry["id"])}
        for entry in result.get("items", [])
    ]


def create_territory_event(system: dict, calendar_id: str = "primary") -> dict:
    """Create a Google Calendar event for the next occurrence of a territory capture.

    The event is created on *calendar_id* at the UTC time stored in the system,
    with a 1-hour duration.  Returns a dict matching the calendar_event shape used
    by check_territory_systems: {"summary": str, "start": str}.

    Raises on any failure (missing token, API error, etc.).
    """
    service = _build_service()

    event_dt = _next_weekday_utc(system["day_of_week"], system["event_time"])
    end_dt = event_dt + timedelta(hours=1)

    body = {
        "summary": f"Territory Capture - {system['name']}",
        "start": {"dateTime": event_dt.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 10}],
        },
    }

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    logger.info(
        "Created calendar event for '%s' on calendar '%s': %s",
        system["name"],
        calendar_id,
        created.get("htmlLink"),
    )

    return {
        "summary": created.get("summary", ""),
        "start": created["start"].get("dateTime", created["start"].get("date", "")),
    }


# ai: claude-opus-5-5 | 2026-11-06
def check_events_exist(systems: list[dict]) -> list[dict]:
    """Check Google Calendar for existing events matching each captured territory system.

    For each system dict (must have 'name' and 'event_time' as local 'YYYY-MM-DD HH:MM'),
    searches the primary calendar on that local day for an event whose title contains
    the system name. Sets 'calendar_event' exactly as check_territory_systems does.

    The systems list is modified in-place and also returned.
    """
    local_tz = datetime.now().astimezone().tzinfo

    def day_bounds(system: dict) -> DayBounds:
        event_dt = datetime.strptime(system["event_time"], "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
        return _whole_day(event_dt)

    return _annotate_systems(systems, day_bounds)
