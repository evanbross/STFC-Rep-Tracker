# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import json
import logging
import os
import sys
import threading
from datetime import datetime, UTC

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from app.app_config import capture_cfg

logger = logging.getLogger(__name__)

community_mod_bp = Blueprint("community_mod", __name__)


def _runtime_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


# ai: claude-opus-5-5 | 2026-11-06
# JSON Lines: one capture per line, so each append is a single write and a
# torn write can damage at most its own line. The older community-data.json
# ("---"-separated, indented) is left untouched.
_CAPTURE_FILE = os.path.join(_runtime_dir(), "community-data.jsonl")
_capture_lock = threading.Lock()
_DEFAULT_MAX_PAYLOAD_BYTES = 1_000_000

ISOGEN_1_RID = 2991010408
TRITANIUM_RID = 743985951

_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key", "x-auth-token"}


@community_mod_bp.route("/", methods=["POST"])
def receive_payload():
    """
    Receive and capture a JSON payload from the STFC community mod.
    ---
    tags:
      - Community Mod
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
    responses:
      200:
        description: Payload captured successfully
      400:
        description: Request body is not valid JSON
    """
    logger.info("community-mod: POST request received from %s", request.remote_addr)
    logger.info(
        "community-mod: Content-Type=%s  Content-Length=%s",
        request.content_type,
        request.content_length,
    )

    # ai: claude-opus-5-5 | 2026-11-06
    max_payload_bytes = max_payload_size()
    raw = _read_body_up_to(max_payload_bytes)
    if raw is None:
        logger.warning("community-mod: rejected payload over %d bytes", max_payload_bytes)
        return jsonify({"error": "Payload too large"}), 413

    if not request.is_json:
        logger.warning("community-mod: rejected Content-Type %s", request.content_type)
        return jsonify({"error": "Request body must be valid JSON"}), 400
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("community-mod: received non-JSON payload")
        return jsonify({"error": "Request body must be valid JSON"}), 400

    logger.info(
        "community-mod: parsed JSON payload with %d top-level key(s): %s",
        len(data),
        list(data.keys()) if isinstance(data, dict) else "(list/other)",
    )

    safe_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _SENSITIVE_HEADERS
    }
    capture = {
        "received_at": datetime.now(UTC).isoformat(),  # + "Z",
        "headers": safe_headers,
        "payload": data,
    }

    capture_path = append_capture(capture)  # ai: claude-opus-5-5 | 2026-11-06
    logger.info("community-mod: payload appended to %s", capture_path)
    return jsonify({"status": "captured"}), 200


# ai: claude-opus-5-5 | 2026-11-06
def max_payload_size() -> int:
    """Largest accepted community-mod body in bytes (settings: community_mod.max_payload_bytes)."""
    return int(capture_cfg("community_mod", "max_payload_bytes", default=_DEFAULT_MAX_PAYLOAD_BYTES))


# ai: claude-opus-5-5 | 2026-11-06
def _read_body_up_to(limit: int) -> bytes | None:
    """Return the request body, or None if it is longer than `limit` bytes.

    A declared Content-Length over the cap makes Werkzeug raise 413. A chunked
    body has no length, and Werkzeug silently truncates it at the cap instead,
    so read one byte past the limit and treat that byte as proof of overflow.
    """
    request.max_content_length = limit + 1
    try:
        raw = request.get_data(cache=True)
    except RequestEntityTooLarge:
        return None
    return None if len(raw) > limit else raw


# ai: claude-opus-5-5 | 2026-11-06
def append_capture(record: dict) -> str:
    """Append one record as a JSON Lines row and return the file path.

    One write() of one line, under a lock shared by both Flask servers in
    this process (7300 and 7443). Multi-process servers (Gunicorn workers in
    Docker) would need a file lock; capture never runs there.
    """
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    capture_path = os.path.normpath(_CAPTURE_FILE)
    with _capture_lock, open(capture_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line)
    return capture_path
