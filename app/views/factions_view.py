from flask import Blueprint, jsonify, request, current_app

factions_bp = Blueprint("factions", __name__)


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
    data = request.json
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
        return jsonify({"error": str(e)}), 500


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
    data = request.json
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
        return jsonify({"error": str(e)}), 500


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
