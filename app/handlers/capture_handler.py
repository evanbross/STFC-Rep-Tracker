import logging

from flask import Blueprint, jsonify, current_app

from app.reputation_sucker.rep_tracker import RepTrackerOrchestrator

logger = logging.getLogger(__name__)

capture_bp = Blueprint("capture", __name__)

@capture_bp.route("/api/capture-screen", methods=["POST"])
def capture_screen():
    """
    Capture the screen and analyze it
    ---
    responses:
      200:
        description: Screen captured and analyzed
    """
    try:
        db = current_app.config.get("DATABASE")
        if not db:
            # Fallback if not in config, though it should be
            from main import db as main_db
            db = main_db
            
        orchestrator = RepTrackerOrchestrator(db)
        result = orchestrator.capture_and_analyze()

        if "error" in result:
            status_code = 404 if "not found" in result["error"].lower() else 500
            return jsonify(result), status_code

        return jsonify(result)
    except Exception as e:
        logger.exception("Error during screen capture and analysis")
        return jsonify({"error": str(e)}), 500
