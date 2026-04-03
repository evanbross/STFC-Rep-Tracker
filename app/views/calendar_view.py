import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("calendar", __name__)


@calendar_bp.route("/status", methods=["GET"])
def google_calendar_status():
    """
    Return whether a valid Google Calendar token is present.
    ---
    tags:
      - Calendar
    responses:
      200:
        description: Authentication status
    """
    try:
        from app.google_calendar import is_authenticated
        return jsonify({"authenticated": is_authenticated()})
    except Exception as e:
        return jsonify({"authenticated": False, "error": str(e)})


@calendar_bp.route("/auth", methods=["POST"])
def google_calendar_auth():
    """
    Run the Google Calendar OAuth2 browser consent flow and save the token.
    Only needs to be called once (or after the token expires and cannot be refreshed).
    Requires google_credentials.json to be present at the project root (or the path
    configured under google_calendar.credentials_file in settings.yaml).
    ---
    tags:
      - Calendar
    responses:
      200:
        description: OAuth2 flow completed and token saved
      500:
        description: Auth flow failed (missing credentials file, browser unavailable, etc.)
    """
    try:
        from app.google_calendar import run_auth_flow
        result = run_auth_flow()
        return jsonify(result)
    except FileNotFoundError as e:
        logger.error("Google credentials file missing: %s", e)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.exception("Google Calendar auth flow failed")
        return jsonify({"error": str(e)}), 500
