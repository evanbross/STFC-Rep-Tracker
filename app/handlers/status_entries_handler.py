from flask import Blueprint, jsonify, request, current_app

entries_bp = Blueprint("entries", __name__)


@entries_bp.route("/", methods=["GET"])
def get_all_entries():
    """
    Get all stat entries for all factions
    ---
    tags:
      - Entries
    responses:
      200:
        description: A dictionary where keys are faction names and values are lists of entries
    """
    db = current_app.config["DATABASE"]
    entries = db.stat_entries.get_all_factions_with_entries()
    return jsonify(entries)


@entries_bp.route("/<faction_name>", methods=["GET"])
def get_faction_entries(faction_name):
    """
    Get stat entries for a specific faction
    ---
    tags:
      - Entries
    parameters:
      - name: faction_name
        in: path
        type: string
        required: true
    responses:
      200:
        description: A list of entries for the faction
    """
    db = current_app.config["DATABASE"]
    entries = db.stat_entries.get_faction_entries(faction_name)
    return jsonify(entries)


@entries_bp.route("/", methods=["POST"])
def add_entry():
    """
    Add a new stat entry
    ---
    tags:
      - Entries
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
    data = request.json
    faction_name = data.get("faction")
    value = data.get("value")

    if not faction_name or value is None:
        return jsonify({"error": "Missing faction or value"}), 400

    try:
        entry = db.stat_entries.add_stat_entry(faction_name, int(value))
        return jsonify(entry), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
