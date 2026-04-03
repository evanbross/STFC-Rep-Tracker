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
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def _credentials_path():
    from app.app_config import capture_cfg
    return os.path.join(
        _PROJECT_ROOT,
        capture_cfg("google_calendar", "credentials_file", default="google_credentials.json"),
    )


def _token_path():
    from app.app_config import capture_cfg
    return os.path.join(
        _PROJECT_ROOT,
        capture_cfg("google_calendar", "token_file", default="google_token.json"),
    )


def _build_service():
    """Return an authenticated Google Calendar service, or raise if not possible."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_file = _token_path()
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError(
                "No valid Google Calendar token. "
                "Call POST /api/calendar/auth to complete the OAuth2 flow."
            )

    return build("calendar", "v3", credentials=creds)


def is_authenticated():
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


def run_auth_flow():
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


def check_events_exist(systems):
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
                    name, ev.get("summary"), system["calendar_event"]["start"],
                )
            else:
                system["calendar_event"] = False
                logger.info("No calendar event for '%s' on %s", name, event_time_str[:10])

        except Exception as e:
            logger.error("Calendar lookup failed for '%s': %s", name, e)
            system["calendar_event"] = None

    return systems
