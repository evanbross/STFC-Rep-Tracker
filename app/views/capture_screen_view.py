import logging

from flask import Blueprint, jsonify, current_app

from app.screen_processing.process_away_teams import AwayTeamOrchestrator
from app.screen_processing.process_gifts import GiftsOrchestrator
from app.screen_processing.process_reputations import RepTrackerOrchestrator

logger = logging.getLogger(__name__)

capture_bp = Blueprint("capture", __name__)


def _get_db():
    db = current_app.config.get("DATABASE")
    if not db:
        from main import db as main_db

        return main_db
    return db


@capture_bp.route("/", methods=["POST"])
def capture_screen():
    """
    Capture the screen and analyze it
    ---
    tags:
      - Capture
    responses:
      200:
        description: Screen captured and analyzed
    """
    try:
        orchestrator = RepTrackerOrchestrator(_get_db())
        try:
            result = orchestrator.capture_and_analyze()
            return jsonify(result)
        except Exception as e:
            logger.exception("Error during screen capture and analysis")
            status_code = 404 if "not found" in str(e).lower() else 500
            return jsonify({"error": str(e)}), status_code
    except Exception as e:
        logger.exception("Error during screen capture and analysis")
        return jsonify({"error": str(e)}), 500


@capture_bp.route("/away-team", methods=["POST"])
def capture_away_team():
    """
    Navigate to the Away Team screen and capture it
    ---
    tags:
      - Capture
    responses:
      200:
        description: Away Team screen captured
    """
    try:
        orchestrator = AwayTeamOrchestrator(_get_db())
        try:
            result = orchestrator.capture_away_team()
            return jsonify(result)
        except Exception as e:
            logger.exception("Error during Away Team screen capture")
            status_code = 404 if "not found" in str(e).lower() else 500
            return jsonify({"error": str(e)}), status_code
    except Exception as e:
        logger.exception("Error during Away Team screen capture")
        return jsonify({"error": str(e)}), 500


@capture_bp.route("/gifts", methods=["POST"])
def capture_gifts():
    """
    Navigate to the Gifts screen and capture it
    ---
    tags:
      - Capture
    responses:
      200:
        description: Gifts screen captured
    """
    try:
        orchestrator = GiftsOrchestrator(_get_db())
        try:
            result = orchestrator.capture_gifts()
            return jsonify(result)
        except Exception as e:
            logger.exception("Error during Gifts screen capture")
            status_code = 404 if "not found" in str(e).lower() else 500
            return jsonify({"error": str(e)}), status_code
    except Exception as e:
        logger.exception("Error during Gifts screen capture")
        return jsonify({"error": str(e)}), 500


@capture_bp.route("/event-rewards", methods=["POST"])
def capture_event_rewards():
    """
    Navigate to the Event Rewards screen and capture it
    ---
    tags:
      - Capture
    responses:
      200:
        description: Event Rewards screen captured
    """
    try:
        orchestrator = RepTrackerOrchestrator(_get_db())
        try:
            result = orchestrator.capture_event_rewards()
            return jsonify(result)
        except Exception as e:
            logger.exception("Error during Event Rewards screen capture")
            status_code = 404 if "not found" in str(e).lower() else 500
            return jsonify({"error": str(e)}), status_code
    except Exception as e:
        logger.exception("Error during Event Rewards screen capture")
        return jsonify({"error": str(e)}), 500
