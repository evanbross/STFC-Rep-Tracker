import logging

from flask import Blueprint, jsonify, current_app

from app.screen_processing.process_away_teams import AwayTeamOrchestrator
from app.screen_processing.process_event_rewards import EventRewardsOrchestrator
from app.screen_processing.process_gifts import GiftsOrchestrator
from app.screen_processing.process_territory_capture import TerritoryCaptureOrchestrator
from app.screen_processing.process_reputations import (
    ProcessReputationsOrchestrator,
    capture_and_identify_faction,
)

logger = logging.getLogger(__name__)

capture_bp = Blueprint("capture", __name__)


def _get_db():
    return current_app.config["DATABASE"]


def _run_capture(make_orchestrator, capture_fn, log_msg, error_msg):
    """Run a capture operation, returning a JSON response with appropriate status code."""
    try:
        result = capture_fn(make_orchestrator())
        return jsonify(result)
    except Exception as e:
        logger.exception(log_msg)
        status_code = 404 if "not found" in str(e).lower() else 500
        return jsonify({"error": error_msg}), status_code


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
    return _run_capture(
        lambda: ProcessReputationsOrchestrator(_get_db()),
        lambda o: o.process_reputations(),
        "Error during screen capture and analysis",
        "Reputation capture failed",
    )


@capture_bp.route("/reputations/<int:faction_id>", methods=["POST"])
def capture_single_faction_reputation(faction_id):
    """
    Navigate to the Faction Store and capture reputation points for a single faction
    ---
    tags:
      - Capture
    parameters:
      - name: faction_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Reputation points captured and saved for the faction
      404:
        description: Game window or faction not found
      500:
        description: Unexpected error during capture
    """
    return _run_capture(
        lambda: ProcessReputationsOrchestrator(_get_db()),
        lambda o: o.process_single_faction(faction_id),
        "Error during single faction screen capture",
        "Faction capture failed",
    )


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
        status_code = 404 if "not found" in str(e).lower() else 500
        return jsonify({"error": "Failed to identify faction"}), status_code


@capture_bp.route("/away-team-collect", methods=["POST"])
def capture_away_team_collect():
    """
    Navigate to the Away Team screen and collect completed missions only (no new starts)
    ---
    tags:
      - Capture
    responses:
      200:
        description: Completed Away Team missions collected
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    return _run_capture(
        AwayTeamOrchestrator,
        lambda o: o.capture_away_team_collect(),
        "Error during Away Team collect",
        "Away Team collect failed",
    )


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
    return _run_capture(
        AwayTeamOrchestrator,
        lambda o: o.capture_away_team(),
        "Error during Away Team screen capture",
        "Away Team capture failed",
    )


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
    return _run_capture(
        GiftsOrchestrator,
        lambda o: o.capture_gifts(),
        "Error during Gifts screen capture",
        "Gifts capture failed",
    )


@capture_bp.route("/territory-capture", methods=["POST"])
def navigate_territory_capture():
    """
    Navigate to home screen, click Alliance, then click Territory
    ---
    tags:
      - Capture
    responses:
      200:
        description: Successfully navigated to Territory Capture screen
      404:
        description: Game window not found
      500:
        description: Unexpected error during navigation
    """
    return _run_capture(
        TerritoryCaptureOrchestrator,
        lambda o: o.navigate_to_territory_capture(),
        "Error during Territory Capture navigation",
        "Territory Capture navigation failed",
    )


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
    return _run_capture(
        EventRewardsOrchestrator,
        lambda o: o.capture_event_rewards(),
        "Error during Event Rewards screen capture",
        "Event Rewards capture failed",
    )
