import json
import logging
import os
from datetime import datetime, UTC

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

community_mod_bp = Blueprint("community_mod", __name__)

_CAPTURE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "community-data.json"
)


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

    data = request.get_json(force=True, silent=True)
    if data is None:
        logger.warning("community-mod: received non-JSON payload")
        return jsonify({"error": "Request body must be valid JSON"}), 400

    logger.info(
        "community-mod: parsed JSON payload with %d top-level key(s): %s",
        len(data),
        list(data.keys()) if isinstance(data, dict) else "(list/other)",
    )

    capture = {
        "received_at": datetime.now(UTC).isoformat() + "Z",
        "headers": dict(request.headers),
        "payload": data,
    }

    capture_path = os.path.normpath(_CAPTURE_FILE)
    with open(capture_path, "w", encoding="utf-8") as f:
        json.dump(capture, f, indent=2)

    logger.info("community-mod: payload captured to %s", capture_path)
    return jsonify({"status": "captured"}), 200
