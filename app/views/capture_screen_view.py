# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging

from flask import Blueprint, jsonify, current_app, request

from app.screen_processing.process_away_teams import AwayTeamOrchestrator
from app.screen_processing.process_event_rewards import EventRewardsOrchestrator
from app.screen_processing.process_gifts import GiftsOrchestrator
from app.screen_processing.process_hostile_templates import HostileTemplateOrchestrator
from app.screen_processing.process_system_targets import SystemTargetOrchestrator
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
        if isinstance(result, dict) and "error" in result:
            status_code = 404 if "not found" in str(result["error"]).lower() else 500
            return jsonify(result), status_code
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


@capture_bp.route("/reputations/<string:faction_code>", methods=["POST"])
def capture_single_faction_reputation(faction_code):
    """
    Navigate to the Faction Store and capture reputation points for a single faction
    ---
    tags:
      - Capture
    parameters:
      - name: faction_code
        in: path
        type: string
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
        lambda o: o.process_single_faction(faction_code),
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
        if isinstance(result, dict) and "error" in result:
            status_code = 404 if "not found" in str(result["error"]).lower() else 500
            return jsonify(result), status_code
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


@capture_bp.route("/system-targets/scan", methods=["POST"])
def scan_system_targets():
    """
    Scan the current system screen for attackable targets, ranked best-first
    ---
    tags:
      - Capture
    responses:
      200:
        description: Candidate targets detected and scored
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    return _run_capture(
        lambda: SystemTargetOrchestrator(_get_db()),
        lambda o: o.scan_targets(),
        "Error scanning system targets",
        "System target scan failed",
    )


@capture_bp.route("/system-targets/refresh", methods=["POST"])
def refresh_system_targets():
    """
    Cheaply re-rank the current target list without re-clicking any target
    ---
    tags:
      - Capture
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [system_name]
          properties:
            system_name:
              type: string
            known_candidates:
              type: array
              description: The candidate list from the last scan/refresh, used to carry forward cargo/hull/shield.
              items:
                type: object
    responses:
      200:
        description: Candidates re-ranked with fresh position/intercept data
      400:
        description: Missing system_name
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    data = request.get_json(silent=True) or {}
    system_name = data.get("system_name")
    if not system_name:
        return jsonify({"error": "system_name is required"}), 400
    known_candidates = data.get("known_candidates") or []

    return _run_capture(
        lambda: SystemTargetOrchestrator(_get_db()),
        lambda o: o.refresh_targets(system_name, known_candidates),
        "Error refreshing system targets",
        "System target refresh failed",
    )


@capture_bp.route("/system-targets/attack", methods=["POST"])
def attack_system_target():
    """
    Re-select a previously scanned target and click Attack
    ---
    tags:
      - Capture
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [click_x, click_y]
          properties:
            click_x:
              type: integer
            click_y:
              type: integer
            vx:
              type: number
              description: Target's tracked velocity in px/sec, from the scan candidate.
            vy:
              type: number
            scanned_at:
              type: number
              description: Epoch seconds the position was captured at, from the scan candidate.
    responses:
      200:
        description: Target selected and Attack clicked
      400:
        description: Missing or invalid click coordinates
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    data = request.get_json(silent=True) or {}
    try:
        click_x = int(data["click_x"])
        click_y = int(data["click_y"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "click_x and click_y are required integers"}), 400

    try:
        vx = float(data.get("vx", 0.0))
        vy = float(data.get("vy", 0.0))
        scanned_at = float(data["scanned_at"]) if "scanned_at" in data else None
    except (TypeError, ValueError):
        return jsonify({"error": "vx, vy, and scanned_at must be numbers"}), 400

    return _run_capture(
        lambda: SystemTargetOrchestrator(_get_db()),
        lambda o: o.attack_target(click_x, click_y, vx, vy, scanned_at),
        "Error attacking system target",
        "Attack failed",
    )


# ai: claude-sonnet-5 | 2026-09-17
@capture_bp.route("/hostile-template/capture", methods=["POST"])
def capture_hostile_template_screen():
    """
    Activate the game window and capture a fresh screenshot for drawing a combat template crop box
    ---
    tags:
      - Capture
    responses:
      200:
        description: Screenshot captured (base64 PNG) with detected system name
      404:
        description: Game window not found
      500:
        description: Unexpected error during capture
    """
    return _run_capture(
        lambda: HostileTemplateOrchestrator(_get_db()),
        lambda o: o.capture_screen(),
        "Error capturing screen for hostile ship template",
        "Screen capture failed",
    )


_ALLOWED_TEMPLATE_KINDS = {"hostile_ship", "skull_glyph", "diamond_glyph"}


# ai: claude-sonnet-5 | 2026-09-18
@capture_bp.route("/hostile-template/save", methods=["POST"])
def save_hostile_template():
    """
    Crop the last captured screenshot and register it as a new combat template (hostile ship icon, or skull/diamond label glyph)
    ---
    tags:
      - Capture
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [x, y, w, h]
          properties:
            x:
              type: integer
            y:
              type: integer
            w:
              type: integer
            h:
              type: integer
            kind:
              type: string
              enum: [hostile_ship, skull_glyph, diamond_glyph]
              default: hostile_ship
    responses:
      200:
        description: Template saved and settings.yaml updated
      400:
        description: Missing/invalid crop coordinates, invalid kind, or no screenshot captured yet
      500:
        description: Unexpected error during save
    """
    data = request.get_json(silent=True) or {}
    try:
        x = int(data["x"])
        y = int(data["y"])
        w = int(data["w"])
        h = int(data["h"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "x, y, w, and h are required integers"}), 400

    kind = data.get("kind", "hostile_ship")
    if kind not in _ALLOWED_TEMPLATE_KINDS:
        return jsonify({"error": f"kind must be one of {sorted(_ALLOWED_TEMPLATE_KINDS)}"}), 400

    return _run_capture(
        lambda: HostileTemplateOrchestrator(_get_db()),
        lambda o: o.save_template(x, y, w, h, kind=kind),
        "Error saving combat template",
        "Save failed",
    )
