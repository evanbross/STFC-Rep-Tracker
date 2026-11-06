# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging

from flask import Blueprint, current_app, jsonify

from app.google_calendar import check_territory_systems, is_authenticated, run_auth_flow

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
        return jsonify({"authenticated": is_authenticated()})
    except Exception:
        logger.exception("Error checking Google Calendar auth status")
        return jsonify({"authenticated": False, "error": "Failed to check authentication status"})


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
        result = run_auth_flow()
        # After auth, immediately check calendar events for all saved territory systems
        db = current_app.config["DATABASE"]
        systems = db.territory_systems.get_all()
        check_territory_systems(systems)
        result["systems"] = systems
        return jsonify(result)
    except FileNotFoundError as e:
        logger.error("Google credentials file missing: %s", e)
        return jsonify({"error": "Google credentials file not found"}), 500
    except Exception:
        logger.exception("Google Calendar auth flow failed")
        return jsonify({"error": "Google Calendar auth flow failed"}), 500
