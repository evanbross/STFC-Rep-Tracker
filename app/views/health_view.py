# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-19
"""GET /api/health: the backend is serving, which launch it is, and where to open it."""
from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

health_bp = Blueprint("health", __name__)


@health_bp.route("", methods=["GET"])
def health() -> ResponseReturnValue:
    """
    Readiness check for the launcher
    ---
    tags:
      - Health
    responses:
      200:
        description: >-
          `launch_id` echoes the LAUNCH_ID the launcher started this process with (null when started
          some other way), so the launcher knows the answer came from its own child. `url` is where to
          open the app. `caddy_app_name` is the Caddy route this process registered, or null.
    """
    route = current_app.config.get("CADDY_ROUTE")
    return jsonify({
        "status": "ok",
        "launch_id": current_app.config.get("LAUNCH_ID") or None,
        "url": route.url if route is not None else request.host_url.rstrip("/"),
        "caddy_app_name": route.name if route is not None and route.registered else None,
    })
