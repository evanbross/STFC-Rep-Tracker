import json
import logging
import os
from datetime import datetime

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
    data = request.get_json(force=True, silent=True)
    if data is None:
        logger.warning("community-mod: received non-JSON payload")
        return jsonify({"error": "Request body must be valid JSON"}), 400

    capture = {
        "received_at": datetime.utcnow().isoformat() + "Z",
        "headers": dict(request.headers),
        "payload": data,
    }

    capture_path = os.path.normpath(_CAPTURE_FILE)
    with open(capture_path, "w", encoding="utf-8") as f:
        json.dump(capture, f, indent=2)

    logger.info(f"community-mod: payload captured to {capture_path}")
    return jsonify({"status": "captured"}), 200
