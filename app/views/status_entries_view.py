# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, current_app
from flask.views import MethodView

from app.views.request_models import StatusEntriesQuery, StatusEntryIn
from app.views.validation import parse_body, parse_query

logger = logging.getLogger(__name__)

status_entries_bp = Blueprint("status_entries", __name__)


class StatusEntriesView(MethodView):
    """Handles GET and POST requests for status entries."""

    def get(self):
        """
        Get a flat list of all status entries, with optional filtering, sorting, and paging.
        Also served at /all.
        ---
        tags:
          - Status Entries
        parameters:
          - name: faction_name
            in: query
            type: string
            required: false
            description: Filter entries to a specific faction
          - name: limit
            in: query
            type: integer
            required: false
            description: Maximum number of entries to return
          - name: offset
            in: query
            type: integer
            required: false
            description: Number of entries to skip (requires limit)
          - name: sort
            in: query
            type: string
            required: false
            description: "Column to sort by with optional direction, e.g. 'value DESC'"
          - name: days
            in: query
            type: integer
            required: false
            description: Only entries from the last N days (omit for the full history)
        responses:
          200:
            description: A flat list of status entries
          400:
            description: Invalid sort value or query parameter
        """
        # ai: claude-opus-5-5 | 2026-11-06
        query = parse_query(StatusEntriesQuery)
        since = datetime.now(UTC) - timedelta(days=query.days) if query.days else None
        try:
            entries = current_app.config["DATABASE"].status_entries.get_all_entries(
                faction_name=query.faction_name, limit=query.limit, offset=query.offset, sort=query.sort, since=since
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(entries)

    def post(self):
        """
        Add a new status entry for a faction
        ---
        tags:
          - Status Entries
        parameters:
          - name: body
            in: body
            required: true
            schema:
              type: object
              required:
                - faction
                - value
              properties:
                faction:
                  type: string
                value:
                  type: integer
        responses:
          201:
            description: Entry created successfully
          400:
            description: Missing or non-integer faction/value
          404:
            description: Faction not found
        """
        # ai: claude-opus-5-5 | 2026-11-06
        body = parse_body(StatusEntryIn)
        entry = current_app.config["DATABASE"].status_entries.add_status_entry(body.faction, body.value)
        return jsonify(entry), 201


AllStatusEntriesView = StatusEntriesView


class FactionEntriesView(MethodView):
    """Handles GET requests for status entries scoped to a single faction."""

    def get(self, faction_name):
        """
        Get all status entries for a specific faction
        ---
        tags:
          - Status Entries
        parameters:
          - name: faction_name
            in: path
            type: string
            required: true
            description: Name of the faction to retrieve entries for
        responses:
          200:
            description: A list of status entries for the faction
        """
        db = current_app.config["DATABASE"]
        entries = db.status_entries.get_faction_entries(faction_name)
        return jsonify(entries)


status_entries_bp.add_url_rule(
    "/", view_func=StatusEntriesView.as_view("status_entries"), methods=["GET", "POST"]
)
status_entries_bp.add_url_rule(
    "/all",
    view_func=AllStatusEntriesView.as_view("all_status_entries"),
    methods=["GET"],
)
status_entries_bp.add_url_rule(
    "/<faction_name>",
    view_func=FactionEntriesView.as_view("faction_entries"),
    methods=["GET"],
)
