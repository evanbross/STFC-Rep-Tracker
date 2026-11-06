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
from flask import Blueprint, jsonify, request, current_app, send_from_directory
from werkzeug.utils import secure_filename

from app.app_config import capture_cfg

logger = logging.getLogger(__name__)

factions_bp = Blueprint("factions", __name__)

_ALLOWED_SNIPPET_TYPES = {"button", "desc", None}
_ALLOWED_SNIPPET_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _snippets_dir():
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__), "..", "..",
            capture_cfg("snippets_dir", default="app/screen_snippets"),
        )
    )


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

    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_SNIPPET_EXTENSIONS:
        return jsonify({"error": f"Unsupported file extension: '{ext}'"}), 400

    dest = os.path.join(_snippets_dir(), filename)
    if os.path.exists(dest):
        return jsonify({"error": f"Snippet file '{filename}' already exists"}), 409

    os.makedirs(os.path.dirname(dest), exist_ok=True)
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
    return send_from_directory(_snippets_dir(), filename)


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
        description: Missing required fields or faction already exists
    """
    db = current_app.config["DATABASE"]
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    name = data.get("name")
    code = data.get("code")
    color = data.get("color")
    reputation_table_name = data.get("reputation_table_name")
    on_chart = data.get("on_chart", 0)
    display_order = data.get("display_order")
    reputation_dao_name = data.get("reputation_dao_name")
    snippet_selected_button = data.get("snippet_selected_button")
    snippet_unselected = data.get("snippet_unselected")

    if not name or not code:
        return jsonify({"error": "Missing name or code"}), 400

    try:
        result = db.factions.add_faction(
            name,
            code,
            color,
            reputation_table_name,
            int(on_chart),
            int(display_order) if display_order is not None else None,
            reputation_dao_name,
            snippet_selected_button,
            snippet_unselected,
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Error adding faction")
        return jsonify({"error": "Failed to add faction"}), 500


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
      404:
        description: Faction not found
    """
    db = current_app.config["DATABASE"]
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    name = data.get("name")
    new_code = data.get("code")
    color = data.get("color")
    reputation_table_name = data.get("reputation_table_name")
    on_chart = data.get("on_chart", 0)
    display_order = data.get("display_order")
    reputation_dao_name = data.get("reputation_dao_name")
    snippet_selected_button = data.get("snippet_selected_button")
    snippet_unselected = data.get("snippet_unselected")

    if not name or not new_code:
        return jsonify({"error": "Missing name or code"}), 400

    try:
        result = db.factions.update_faction(
            current_code,
            name,
            new_code,
            color,
            reputation_table_name,
            int(on_chart),
            int(display_order) if display_order is not None else None,
            reputation_dao_name,
            snippet_selected_button,
            snippet_unselected,
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("Error updating faction")
        return jsonify({"error": "Failed to update faction"}), 500


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
