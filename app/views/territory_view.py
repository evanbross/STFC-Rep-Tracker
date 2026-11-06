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

from app.views.request_models import CalendarEventIn, TerritorySystemIn
from app.views.validation import parse_body

logger = logging.getLogger(__name__)

territory_bp = Blueprint("territory", __name__)


def _annotate_with_calendar(systems: list[dict]) -> list[dict]:
    """Append calendar_event data to each system if Google Calendar is authenticated.

    Failures are swallowed — calendar checks must never break territory endpoints.
    """
    try:
        from app.google_calendar import check_territory_systems, is_authenticated
        if is_authenticated():
            check_territory_systems(systems)
    except Exception:
        pass
    return systems


@territory_bp.get("/systems")
def get_systems():
    db = current_app.config["DATABASE"]
    systems = db.territory_systems.get_all()
    _annotate_with_calendar(systems)
    return jsonify(systems)


# ai: claude-opus-5-5 | 2026-11-06
@territory_bp.post("/systems")
def upsert_system():
    body = parse_body(TerritorySystemIn)
    system = current_app.config["DATABASE"].territory_systems.upsert(body.name, body.day_of_week, body.event_time)
    _annotate_with_calendar([system])
    return jsonify(system), 200


# ai: claude-opus-5-5 | 2026-11-06
@territory_bp.put("/systems/<int:system_id>")
def update_system(system_id: int):
    body = parse_body(TerritorySystemIn)
    system = current_app.config["DATABASE"].territory_systems.update(
        system_id, body.name, body.day_of_week, body.event_time
    )
    if not system:
        return jsonify({"error": "not found"}), 404
    _annotate_with_calendar([system])
    return jsonify(system)


@territory_bp.post("/systems/check-calendar")
def check_calendar():
    """Re-run the Google Calendar lookup for all territory systems and return the results."""
    db = current_app.config["DATABASE"]
    systems = db.territory_systems.get_all()
    _annotate_with_calendar(systems)
    return jsonify(systems)


@territory_bp.get("/calendars")
def list_calendars():
    """Return the authenticated user's Google Calendar list."""
    try:
        from app.google_calendar import list_calendars as _list_calendars
        return jsonify(_list_calendars())
    except Exception:
        logger.exception("Error listing Google Calendars")
        return jsonify({"error": "Failed to list calendars"}), 500


@territory_bp.post("/systems/<int:system_id>/calendar-event")
def create_calendar_event(system_id: int):
    """Create a Google Calendar event for the next occurrence of this territory system.

    Accepts an optional JSON body with a 'calendar_id' key (defaults to 'primary').
    """
    db = current_app.config["DATABASE"]
    system = db.territory_systems.get_by_id(system_id)
    if not system:
        return jsonify({"error": "not found"}), 404

    body = parse_body(CalendarEventIn, optional=True)  # ai: claude-opus-5-5 | 2026-11-06

    try:
        from app.google_calendar import create_territory_event
        system["calendar_event"] = create_territory_event(system, calendar_id=body.calendar_id)
        return jsonify(system)
    except Exception:
        logger.exception("Error creating Google Calendar event for territory system %s", system_id)
        return jsonify({"error": "Failed to create calendar event"}), 500


@territory_bp.delete("/systems/<int:system_id>")
def delete_system(system_id: int):
    db = current_app.config["DATABASE"]
    if not db.territory_systems.delete(system_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True})