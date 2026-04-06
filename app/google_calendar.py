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
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# app/google_calendar.py lives inside the app/ package; project root is one level up
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def _credentials_path() -> str:
    from app.app_config import capture_cfg

    return os.path.join(
        _PROJECT_ROOT,
        capture_cfg("google_calendar", "credentials_file"),
    )


def _token_path() -> str:
    from app.app_config import capture_cfg

    return os.path.join(
        _PROJECT_ROOT,
        capture_cfg("google_calendar", "token_file"),
    )


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
        logger.info("No valid token — starting OAuth2 flow.")
        run_auth_flow()
        creds = Credentials.from_authorized_user_file(token_file, _SCOPES)

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
    creds = flow.run_local_server(port=0)

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


def check_territory_systems(systems: list[dict]) -> list[dict]:
    """Check Google Calendar for events matching each territory schedule system.

    Each system dict must have 'name', 'day_of_week' (int 0–6), and 'event_time' ('HH:MM' UTC).
    Searches the primary calendar on the next occurrence of that weekday for any event whose
    title contains the system name.

    Adds a 'calendar_event' key to each system:
      - None   : calendar unavailable or check failed
      - False  : no matching event found on that day
      - dict   : {"summary": str, "start": str} of the first matching event

    The systems list is modified in-place and also returned.
    """
    try:
        service = _build_service()
    except RuntimeError as e:
        logger.warning("Google Calendar unavailable: %s", e)
        for s in systems:
            s["calendar_event"] = None
            s["calendar_error"] = str(e)
        return systems
    except Exception as e:
        logger.error("Google Calendar connection failed: %s", e)
        for s in systems:
            s["calendar_event"] = None
            s["calendar_error"] = "Calendar connection failed"
        return systems

    for system in systems:
        day_of_week = system.get("day_of_week")
        event_time = system.get("event_time")
        name = system.get("name", "")

        if day_of_week is None or not event_time:
            system["calendar_event"] = None
            continue

        try:
            event_dt = _next_weekday_utc(day_of_week, event_time)
            day_start = event_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=day_start.isoformat(),
                    timeMax=day_end.isoformat(),
                    q=name,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            items = result.get("items", [])
            if items:
                ev = items[0]
                system["calendar_event"] = {
                    "summary": ev.get("summary", ""),
                    "start": ev["start"].get("dateTime", ev["start"].get("date", "")),
                }
                logger.info(
                    "Calendar hit for '%s': '%s' at %s",
                    name,
                    ev.get("summary"),
                    system["calendar_event"]["start"],
                )
            else:
                system["calendar_event"] = False
                logger.info("No calendar event for '%s' on %s", name, day_start.date())

        except Exception as e:
            logger.error("Calendar lookup failed for '%s': %s", name, e)
            system["calendar_event"] = None

    return systems


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


def check_events_exist(systems: list[dict]) -> list[dict]:
    """Check Google Calendar for existing events matching each territory system.

    For each system dict (must have 'name' and 'event_time' keys), searches the
    primary calendar on the day of event_time for any event whose title contains
    the system name.

    Adds a 'calendar_event' key to each system:
      - None   : no event_time or calendar check could not run
      - False  : no matching event found on that day
      - dict   : {"summary": str, "start": str} of the first matching event

    The systems list is modified in-place and also returned.
    """
    try:
        service = _build_service()
    except RuntimeError as e:
        logger.warning("Google Calendar unavailable: %s", e)
        for s in systems:
            s["calendar_event"] = None
            s["calendar_error"] = str(e)
        return systems
    except Exception as e:
        logger.error("Google Calendar connection failed: %s", e)
        for s in systems:
            s["calendar_event"] = None
            s["calendar_error"] = "Calendar connection failed"
        return systems

    local_tz = datetime.now().astimezone().tzinfo

    for system in systems:
        event_time_str = system.get("event_time")
        name = system.get("name", "")

        if not event_time_str:
            system["calendar_event"] = None
            continue

        try:
            event_dt = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M").replace(
                tzinfo=local_tz
            )
            day_start = event_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=day_start.isoformat(),
                    timeMax=day_end.isoformat(),
                    q=name,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            items = result.get("items", [])
            if items:
                ev = items[0]
                system["calendar_event"] = {
                    "summary": ev.get("summary", ""),
                    "start": ev["start"].get("dateTime", ev["start"].get("date", "")),
                }
                logger.info(
                    "Calendar hit for '%s': '%s' at %s",
                    name,
                    ev.get("summary"),
                    system["calendar_event"]["start"],
                )
            else:
                system["calendar_event"] = False
                logger.info(
                    "No calendar event for '%s' on %s", name, event_time_str[:10]
                )

        except Exception as e:
            logger.error("Calendar lookup failed for '%s': %s", name, e)
            system["calendar_event"] = None

    return systems
