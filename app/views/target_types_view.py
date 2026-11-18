# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging

from flask import Blueprint, jsonify, current_app
from flask.typing import ResponseReturnValue

from app.database.database import Database
from app.views.request_models import TargetPreferenceIn
from app.views.snippet_files import send_snippet_image
from app.views.validation import parse_body

logger = logging.getLogger(__name__)

target_types_bp = Blueprint("target_types", __name__)


def _get_db() -> Database:
    return current_app.config["DATABASE"]


@target_types_bp.route("/system/<path:system_name>", methods=["GET"])
def get_target_types(system_name: str) -> ResponseReturnValue:
    """
    List every hostile ship type seen in a system, with its target/avoid preference
    ---
    tags:
      - Target Types
    parameters:
      - name: system_name
        in: path
        type: string
        required: true
    responses:
      200:
        description: Target types for this system (empty list if never scanned)
    """
    return jsonify(_get_db().target_types.get_for_system(system_name))


@target_types_bp.route("/<int:type_id>", methods=["PUT"])
def update_target_type(type_id: int) -> ResponseReturnValue:
    """
    Set a target type's target/avoid/unknown preference, and optionally rename it
    ---
    tags:
      - Target Types
    parameters:
      - name: type_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [preference]
          properties:
            preference:
              type: string
              enum: [unknown, target, avoid]
            display_name:
              type: string
    responses:
      200:
        description: Updated target type
      400:
        description: Invalid preference
      404:
        description: Target type not found
    """
    body = parse_body(TargetPreferenceIn)  # ai: claude-opus-5-5 | 2026-11-06
    updated = _get_db().target_types.set_preference(type_id, body.preference, body.display_name)
    if updated is None:
        return jsonify({"error": "Target type not found"}), 404
    return jsonify(updated)


@target_types_bp.route("/sample-image/<path:filename>", methods=["GET"])
def get_sample_image(filename: str) -> ResponseReturnValue:
    """
    Serve a saved example-target crop image
    ---
    tags:
      - Target Types
    parameters:
      - name: filename
        in: path
        type: string
        required: true
    responses:
      200:
        description: Image file
      404:
        description: Not found
    """
    return send_snippet_image(filename)  # ai: claude-opus-5-5 | 2026-11-06
