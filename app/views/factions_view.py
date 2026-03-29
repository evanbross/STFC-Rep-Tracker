import logging
import os

from flask import Blueprint, jsonify, request, current_app, send_from_directory
from werkzeug.utils import secure_filename

from app.app_config import capture_cfg

logger = logging.getLogger(__name__)

factions_bp = Blueprint("factions", __name__)


def _snippets_dir():
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__), "..", "..",
            capture_cfg("snippets_dir", default="app/screen_snippets"),
        )
    )


@factions_bp.route("/<int:faction_id>/selected-snippets", methods=["GET"])
def get_selected_snippets(faction_id):
    db = current_app.config["DATABASE"]
    snippets = db.selected_snippets.get_snippets_for_faction(faction_id)
    return jsonify(snippets)


@factions_bp.route("/<int:faction_id>/selected-snippets", methods=["POST"])
def add_selected_snippet(faction_id):
    """Upload an image file and register it as a selected snippet for a faction."""
    db = current_app.config["DATABASE"]
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    snippet_type = request.form.get("snippet_type") or None
    custom_name = request.form.get("filename", "").strip()

    filename = secure_filename(custom_name if custom_name else file.filename)
    if not filename:
        return jsonify({"error": "No filename"}), 400

    dest = os.path.join(_snippets_dir(), filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    file.save(dest)

    new_id = db.selected_snippets.add_snippet(faction_id, filename, snippet_type)
    return jsonify({"id": new_id, "faction_id": faction_id, "filename": filename, "snippet_type": snippet_type}), 201


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
    responses:
      201:
        description: Faction created successfully
      400:
        description: Missing required fields or faction already exists
    """
    db = current_app.config["DATABASE"]
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    name = data.get("name")
    code = data.get("code")
    color = data.get("color")
    reputation_table_name = data.get("reputation_table_name")
    on_chart = data.get("on_chart", 0)
    display_order = data.get("display_order")

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
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Error adding faction")
        return jsonify({"error": "Failed to add faction"}), 500


@factions_bp.route("/<int:id>", methods=["PUT"])
def update_faction(id):
    """
    Update an existing faction
    ---
    tags:
      - Factions
    parameters:
      - name: id
        in: path
        type: integer
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
    responses:
      200:
        description: Faction updated successfully
      404:
        description: Faction not found
    """
    db = current_app.config["DATABASE"]
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400
    name = data.get("name")
    code = data.get("code")
    color = data.get("color")
    reputation_table_name = data.get("reputation_table_name")
    on_chart = data.get("on_chart", 0)
    display_order = data.get("display_order")

    if not name or not code:
        return jsonify({"error": "Missing name or code"}), 400

    try:
        result = db.factions.update_faction(
            id,
            name,
            code,
            color,
            reputation_table_name,
            int(on_chart),
            int(display_order) if display_order is not None else None,
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
