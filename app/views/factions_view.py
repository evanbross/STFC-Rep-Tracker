# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
import os

import psycopg2.errors
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename

from app.snippet_store import new_snippet_path, snippet_exists
from app.views.request_models import FactionIn
from app.views.snippet_files import is_snippet_image, send_snippet_image
from app.views.validation import parse_body

logger = logging.getLogger(__name__)

factions_bp = Blueprint("factions", __name__)

_ALLOWED_SNIPPET_TYPES = {"button", "desc", None}


@factions_bp.route("/<string:faction_code>/selected-snippets", methods=["GET"])
def get_selected_snippets(faction_code):
    db = current_app.config["DATABASE"]
    snippets = db.selected_snippets.get_snippets_for_faction(faction_code)
    return jsonify(snippets)


@factions_bp.route("/<string:faction_code>/selected-snippets", methods=["POST"])
def add_selected_snippet(faction_code):
    """Upload an image file and register it as a selected snippet for a faction."""
    db = current_app.config["DATABASE"]
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    if not db.factions.get_faction_by_code(faction_code):
        return jsonify({"error": f"Faction '{faction_code}' not found"}), 404

    file = request.files["file"]
    snippet_type = request.form.get("snippet_type") or None
    if snippet_type not in _ALLOWED_SNIPPET_TYPES:
        return jsonify({"error": f"Invalid snippet_type: '{snippet_type}'"}), 400

    custom_name = request.form.get("filename", "").strip()

    filename = secure_filename(custom_name if custom_name else file.filename)
    if not filename:
        return jsonify({"error": "No filename"}), 400

    if not is_snippet_image(filename):  # ai: claude-opus-5-5 | 2026-11-06
        return jsonify({"error": f"Unsupported file extension: '{os.path.splitext(filename)[1]}'"}), 400

    # ai: claude-opus-5-5 | 2026-11-06
    # A name already used by a bundled snippet would silently override it, so it's a conflict too.
    if snippet_exists(filename):
        return jsonify({"error": f"Snippet file '{filename}' already exists"}), 409

    dest = new_snippet_path(filename)
    file.save(dest)

    try:
        new_id = db.selected_snippets.add_snippet(faction_code, filename, snippet_type)
    except psycopg2.errors.ForeignKeyViolation:
        os.remove(dest)
        return jsonify({"error": f"Faction '{faction_code}' not found"}), 404

    return jsonify({"id": new_id, "faction_id": faction_code, "filename": filename, "snippet_type": snippet_type}), 201


@factions_bp.route("/selected-snippets/<int:snippet_id>", methods=["DELETE"])
def delete_selected_snippet(snippet_id):
    db = current_app.config["DATABASE"]
    deleted = db.selected_snippets.delete_snippet(snippet_id)
    if not deleted:
        return jsonify({"error": "Snippet not found"}), 404
    return jsonify({"deleted": snippet_id}), 200


@factions_bp.route("/snippet-image/<path:filename>", methods=["GET"])
def get_snippet_image(filename):
    return send_snippet_image(filename)  # ai: claude-opus-5-5 | 2026-11-06


@factions_bp.route("/", methods=["GET"])
def get_factions():
    db = current_app.config["DATABASE"]
    result = db.factions.get_all_factions()
    return jsonify(result)


@factions_bp.route("/", methods=["POST"])
def add_faction():
    """
    Add a new faction
    ---
    tags:
      - Factions
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
            - code
          properties:
            name:
              type: string
            code:
              type: string
            color:
              type: string
            reputation_table_name:
              type: string
            on_chart:
              type: integer
              default: 0
              description: 1 shows the faction's history series when the Dashboard chart loads; 0 starts it hidden
            display_order:
              type: integer
            reputation_dao_name:
              type: string
            snippet_selected_button:
              type: string
            snippet_unselected:
              type: string
    responses:
      201:
        description: Faction created successfully
      400:
        description: Invalid request body
      409:
        description: A faction with that name or code already exists
    """
    # ai: claude-opus-5-5 | 2026-11-06
    body = parse_body(FactionIn)
    result = current_app.config["DATABASE"].factions.add_faction(
        body.name,
        body.code,
        body.color,
        body.reputation_table_name,
        body.on_chart,
        body.display_order,
        body.reputation_dao_name,
        body.snippet_selected_button,
        body.snippet_unselected,
    )
    return jsonify(result), 201


@factions_bp.route("/<string:current_code>", methods=["PUT"])
def update_faction(current_code):
    """
    Update an existing faction
    ---
    tags:
      - Factions
    parameters:
      - name: current_code
        in: path
        type: string
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
            - code
          properties:
            name:
              type: string
            code:
              type: string
            color:
              type: string
            reputation_table_name:
              type: string
            on_chart:
              type: integer
              description: 1 shows the faction's history series when the Dashboard chart loads; 0 starts it hidden
            display_order:
              type: integer
            reputation_dao_name:
              type: string
            snippet_selected_button:
              type: string
            snippet_unselected:
              type: string
    responses:
      200:
        description: Faction updated successfully
      400:
        description: Invalid request body
      404:
        description: Faction not found
      409:
        description: Another faction already has that name or code
    """
    # ai: claude-opus-5-5 | 2026-11-06
    body = parse_body(FactionIn)
    result = current_app.config["DATABASE"].factions.update_faction(
        current_code,
        body.name,
        body.code,
        body.color,
        body.reputation_table_name,
        body.on_chart,
        body.display_order,
        body.reputation_dao_name,
        body.snippet_selected_button,
        body.snippet_unselected,
    )
    return jsonify(result), 200


@factions_bp.route("/summary", methods=["GET"])
def get_faction_summary():
    """
    Get summary data for all factions
    ---
    tags:
      - Factions
    parameters:
      - name: sort
        in: query
        type: string
        description: Field to sort by (prefix with - for descending)
        enum: [name, display_order, current_value, last_delta, remaining_time, change_rate, rep_level, last_updated, entry_count]
    responses:
      200:
        description: A list of faction summaries
    """
    db = current_app.config["DATABASE"]
    sort_by = request.args.get("sort")
    summary = db.factions.get_faction_summary(sort_by=sort_by)
    return jsonify(summary)
