import logging

from flask import Blueprint, jsonify, current_app

from app.screen_processing.process_away_teams import AwayTeamOrchestrator
from app.screen_processing.process_event_rewards import EventRewardsOrchestrator
from app.screen_processing.process_gifts import GiftsOrchestrator
from app.screen_processing.process_reputations import (
    ProcessReputationsOrchestrator,
    capture_and_identify_faction,
)

logger = logging.getLogger(__name__)

capture_bp = Blueprint("capture", __name__)


def _get_db():
    db = current_app.config.get("DATABASE")
    if not db:
        from main import db as main_db

        return main_db
    return db


@capture_bp.route("/reputations", methods=["POST"])
def capture_reputations():
    """
    Navigate to the Faction Store and capture reputation points for all factions
    ---
    tags:
      - Capture
    responses:
      200:
        description: Reputation points captured and saved for all factions
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    try:
        orchestrator = ProcessReputationsOrchestrator(_get_db())
        try:
            result = orchestrator.process_reputations()
            return jsonify(result)
        except Exception as e:
            logger.exception("Error during screen capture and analysis")
            status_code = 404 if "not found" in str(e).lower() else 500
            return jsonify({"error": str(e)}), status_code
    except Exception as e:
        logger.exception("Error during screen capture and analysis")
        return jsonify({"error": str(e)}), 500


@capture_bp.route("/identify-faction", methods=["POST"])
def identify_faction():
    """
    Capture the current Faction Store screen and identify which faction is highlighted
    ---
    tags:
      - Capture
    responses:
      200:
        description: Highlighted faction identified
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    try:
        result = capture_and_identify_faction(_get_db())
        return jsonify(result)
    except Exception as e:
        logger.exception("Error identifying faction")
        return jsonify({"error": str(e)}), 500


@capture_bp.route("/away-team", methods=["POST"])
def capture_away_team():
    """
    Navigate to the Away Team screen and capture mission results
    ---
    tags:
      - Capture
    responses:
      200:
        description: Away Team mission results captured and saved
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
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
    Navigate to the Gifts screen and capture gift data
    ---
    tags:
      - Capture
    responses:
      200:
        description: Gift data captured and saved
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
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
    Navigate to the Event Rewards screen and capture reward data
    ---
    tags:
      - Capture
    responses:
      200:
        description: Event reward data captured and saved
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    try:
        orchestrator = EventRewardsOrchestrator(_get_db())
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
