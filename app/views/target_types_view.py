# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
import os

from flask import Blueprint, jsonify, request, current_app, send_from_directory

from app.app_config import capture_cfg

logger = logging.getLogger(__name__)

target_types_bp = Blueprint("target_types", __name__)

_ALLOWED_PREFERENCES = {"unknown", "target", "avoid"}


def _get_db():
    return current_app.config["DATABASE"]


def _snippets_dir():
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__), "..", "..",
            capture_cfg("snippets_dir", default="app/screen_snippets"),
        )
    )


@target_types_bp.route("/system/<path:system_name>", methods=["GET"])
def get_target_types(system_name):
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
def update_target_type(type_id):
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
    data = request.get_json(silent=True) or {}
    preference = data.get("preference")
    if preference not in _ALLOWED_PREFERENCES:
        return jsonify({"error": f"preference must be one of {sorted(_ALLOWED_PREFERENCES)}"}), 400

    display_name = data.get("display_name")
    updated = _get_db().target_types.set_preference(type_id, preference, display_name)
    if updated is None:
        return jsonify({"error": "Target type not found"}), 404
    return jsonify(updated)


@target_types_bp.route("/sample-image/<path:filename>", methods=["GET"])
def get_sample_image(filename):
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
    return send_from_directory(_snippets_dir(), filename)
