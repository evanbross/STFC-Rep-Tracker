# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
import threading
from collections.abc import Callable
from typing import Any, TypeVar

from flask import Blueprint, jsonify, current_app, request
from flask.typing import ResponseReturnValue

from app.domain_errors import DomainError
from app.screen_processing.capture_errors import CaptureError
from app.screen_processing.process_away_teams import AwayTeamOrchestrator
from app.screen_processing.process_event_rewards import EventRewardsOrchestrator
from app.screen_processing.process_gifts import GiftsOrchestrator
from app.screen_processing.process_hostile_templates import HostileTemplateOrchestrator
from app.screen_processing.process_reputations import (
    IdentifyFactionOrchestrator,
    ProcessReputationsOrchestrator,
)
from app.screen_processing.process_system_targets import SystemTargetOrchestrator
from app.screen_processing.process_territory_capture import TerritoryCaptureOrchestrator
from app.views.request_models import AttackIn, RefreshTargetsIn, TemplateCropIn
from app.views.validation import parse_body

logger = logging.getLogger(__name__)

capture_bp = Blueprint("capture", __name__)

OrchestratorT = TypeVar("OrchestratorT")  # the orchestrator type a route builds and then calls


def _get_db():
    return current_app.config["DATABASE"]


# ai: claude-opus-5-5 | 2026-11-06
# One automation at a time (N-S1): two requests driving the mouse and keyboard
# in the game window at once corrupt each other's navigation. A second request
# is refused immediately rather than queued, so a double-click or a second tab
# cannot run the same capture twice in a row.
_automation_lock = threading.Lock()
AUTOMATION_BUSY_MESSAGE = "Another capture is in progress"


# ai: claude-opus-5-5 | 2026-11-06
def _run_capture(
    make_orchestrator: Callable[[], OrchestratorT],
    capture_fn: Callable[[OrchestratorT], Any],
    log_msg: str,
    error_msg: str,
) -> ResponseReturnValue:
    """Run one capture under the automation lock and map its outcome to a response (N-O5).

    - CaptureError subclasses carry a user-facing message and their own status.
    - NotImplementedError (a placeholder capture) is a 501.
    - DomainError (e.g. an unknown faction) goes to the app-level handlers.
    - Anything else is logged with its traceback and answered with error_msg,
      so exception text never reaches the client. This is the request
      boundary, which is where a catch-all belongs.
    """
    if not _automation_lock.acquire(blocking=False):
        logger.info("refused %s: %s", request.path, AUTOMATION_BUSY_MESSAGE)
        return jsonify({"error": AUTOMATION_BUSY_MESSAGE, "busy": True}), 409
    try:
        return jsonify(capture_fn(make_orchestrator()))
    except CaptureError as e:
        logger.warning("%s: %s", log_msg, e)
        return jsonify({"error": str(e)}), e.status_code
    except NotImplementedError:
        logger.warning("%s: not implemented", log_msg)
        return jsonify({"error": f"{error_msg}: not implemented yet"}), 501
    except DomainError:
        raise
    except Exception:
        logger.exception(log_msg)
        return jsonify({"error": error_msg}), 500
    finally:
        _automation_lock.release()


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
    # ai: claude-opus-5-5 | 2026-11-06
    return _run_capture(
        lambda: IdentifyFactionOrchestrator(_get_db()),
        lambda o: o.identify(),
        "Error identifying faction",
        "Failed to identify faction",
    )


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
      501:
        description: Not implemented yet (placeholder)
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
    body = parse_body(RefreshTargetsIn)  # ai: claude-opus-5-5 | 2026-11-06

    return _run_capture(
        lambda: SystemTargetOrchestrator(_get_db()),
        lambda o: o.refresh_targets(body.system_name, body.known_candidates),
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
    body = parse_body(AttackIn)  # ai: claude-opus-5-5 | 2026-11-06

    return _run_capture(
        lambda: SystemTargetOrchestrator(_get_db()),
        lambda o: o.attack_target(body.click_x, body.click_y, body.vx, body.vy, body.scanned_at),
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
    body = parse_body(TemplateCropIn)  # ai: claude-opus-5-5 | 2026-11-06

    return _run_capture(
        lambda: HostileTemplateOrchestrator(_get_db()),
        lambda o: o.save_template(body.x, body.y, body.w, body.h, kind=body.kind),
        "Error saving combat template",
        "Save failed",
    )
