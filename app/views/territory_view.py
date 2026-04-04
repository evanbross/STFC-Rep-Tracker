from flask import Blueprint, current_app, jsonify, request

territory_bp = Blueprint("territory", __name__)


@territory_bp.get("/systems")
def get_systems():
    db = current_app.config["DATABASE"]
    return jsonify(db.territory_systems.get_all())


@territory_bp.post("/systems")
def upsert_system():
    db = current_app.config["DATABASE"]
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    day_of_week = data.get("day_of_week")
    event_time = (data.get("event_time") or "").strip()

    if not name or day_of_week is None or not event_time:
        return jsonify({"error": "name, day_of_week, and event_time are required"}), 400
    if not isinstance(day_of_week, int) or not (0 <= day_of_week <= 6):
        return jsonify({"error": "day_of_week must be an integer 0–6 (Mon–Sun)"}), 400

    system = db.territory_systems.upsert(name, day_of_week, event_time)
    return jsonify(system), 200


@territory_bp.put("/systems/<int:system_id>")
def update_system(system_id: int):
    db = current_app.config["DATABASE"]
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    day_of_week = data.get("day_of_week")
    event_time = (data.get("event_time") or "").strip()

    if not name or day_of_week is None or not event_time:
        return jsonify({"error": "name, day_of_week, and event_time are required"}), 400
    if not isinstance(day_of_week, int) or not (0 <= day_of_week <= 6):
        return jsonify({"error": "day_of_week must be an integer 0–6 (Mon–Sun)"}), 400

    system = db.territory_systems.update(system_id, name, day_of_week, event_time)
    if not system:
        return jsonify({"error": "not found"}), 404
    return jsonify(system)


@territory_bp.delete("/systems/<int:system_id>")
def delete_system(system_id: int):
    db = current_app.config["DATABASE"]
    if not db.territory_systems.delete(system_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True})