import logging

from flask import Blueprint, jsonify, request, current_app
from flask.views import MethodView

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
        responses:
          200:
            description: A flat list of status entries
          400:
            description: Invalid sort value
        """
        db = current_app.config["DATABASE"]
        faction_name = request.args.get("faction_name", type=str)
        limit = request.args.get("limit", type=int)
        offset = request.args.get("offset", type=int)
        sort = request.args.get("sort", type=str)
        try:
            entries = db.get_status_entries_dao().get_all_entries(
                faction_name=faction_name, limit=limit, offset=offset, sort=sort
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
            description: Missing faction or value
          404:
            description: Faction not found
        """
        db = current_app.config["DATABASE"]
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Request body must be valid JSON"}), 400
        faction_name = data.get("faction")
        value = data.get("value")

        if not faction_name or value is None:
            return jsonify({"error": "Missing faction or value"}), 400

        try:
            entry = db.status_entries.add_status_entry(faction_name, int(value))
            return jsonify(entry), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logger.exception("Error adding status entry")
            return jsonify({"error": "Failed to add status entry"}), 500


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
