# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import hmac
import json
import logging
import os
import threading
from collections.abc import Iterator
from datetime import datetime, UTC

from flask import Blueprint, Response, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import RequestEntityTooLarge

from app.app_config import capture_cfg
from app.community_mod_parsing import resource_amounts
from app.database.status_entries_dao import iso_utc
from app.paths import runtime_path
from app.spocks_club_parsing import match_factions

logger = logging.getLogger(__name__)

community_mod_bp = Blueprint("community_mod", __name__)


# ai: claude-opus-5-5 | 2026-11-06
# JSON Lines: one capture per line, so each append is a single write and a
# torn write can damage at most its own line. The older community-data.json
# ("---"-separated, indented) is left untouched.
_CAPTURE_FILE = runtime_path("community-data.jsonl")
_capture_lock = threading.Lock()
_DEFAULT_MAX_PAYLOAD_BYTES = 1_000_000

# ai: claude-opus-5-5 | 2026-11-19
# The header carrying the `token` from the mod's [sync.targets.*] table.
SYNC_TOKEN_HEADER = "stfc-sync-token"

_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key", "x-auth-token", SYNC_TOKEN_HEADER}  # ai: claude-opus-5-5 | 2026-11-19

# ai: claude-opus-5-5 | 2026-11-19
# Wakes the /events streams after each capture, and again when a capture saved
# reputation readings. The counters, not the notification, are what a stream
# compares, so a change that lands while a stream is between waits is still
# seen on its next wait.
_capture_changed = threading.Condition()
_capture_count = 0
_readings_count = 0
# A comment line this often keeps idle proxies from closing the stream, and
# makes a closed browser tab surface as a failed write so its thread exits.
_KEEPALIVE_SECONDS = 25.0


@community_mod_bp.route("/", methods=["POST"])
def receive_payload() -> ResponseReturnValue:
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
        description: Payload captured; `readings_saved` counts the faction values that changed and were saved
      400:
        description: Request body is not valid JSON
      401:
        description: COMMUNITY_MOD_TOKEN is set and the stfc-sync-token header doesn't match it
      413:
        description: Payload is larger than community_mod.max_payload_bytes
    """
    logger.info("community-mod: POST request received from %s", request.remote_addr)
    logger.info(
        "community-mod: Content-Type=%s  Content-Length=%s",
        request.content_type,
        request.content_length,
    )

    # ai: claude-opus-5-5 | 2026-11-19
    # Checked before the body is read, so an unauthorised caller costs nothing.
    if not sync_token_accepted(request.headers.get(SYNC_TOKEN_HEADER)):
        logger.warning("community-mod: rejected request with a missing or wrong %s", SYNC_TOKEN_HEADER)
        return jsonify({"error": "Missing or invalid sync token"}), 401

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
    received_at = datetime.now(UTC)  # ai: claude-opus-5-5 | 2026-11-19
    capture = {
        "received_at": received_at.isoformat(),  # ai: claude-opus-5-5 | 2026-11-19
        "headers": safe_headers,
        "payload": data,
    }

    capture_path = append_capture(capture)  # ai: claude-opus-5-5 | 2026-11-06
    logger.info("community-mod: payload appended to %s", capture_path)
    # ai: claude-opus-5-5 | 2026-11-19
    # After the append, so the raw payload is kept even if the database is down.
    saved = save_reputation_changes(data, received_at)
    return jsonify({"status": "captured", "readings_saved": len(saved)}), 200


# ai: claude-opus-5-5 | 2026-11-19
def save_reputation_changes(payload: object, received_at: datetime) -> list[dict]:
    """Save a reading for each faction whose resource in `payload` differs from its latest value.

    Factions are matched on spocks_resource_id, the game's resource ID. Most
    payloads hold no resources at all and never reach the database.
    """
    amounts = resource_amounts(payload)
    if not amounts:
        return []
    db = current_app.config["DATABASE"]
    readings, _ = match_factions(db.factions.get_all_factions(), amounts)
    if not readings:
        return []
    saved = db.status_entries.add_changed_entries_at(
        received_at, {reading.faction_code: reading.value for reading in readings}
    )
    if saved:
        logger.info("community-mod: saved %d changed reputation reading(s)", len(saved))
        _notify_readings()
    return saved


# ai: claude-opus-5-5 | 2026-11-19
def sync_token_accepted(sent: str | None) -> bool:
    """True when no COMMUNITY_MOD_TOKEN is configured, or `sent` matches it.

    compare_digest keeps the comparison time independent of how much matches.
    Both sides are encoded first because it rejects non-ASCII str arguments.
    """
    expected = current_app.config.get("COMMUNITY_MOD_TOKEN", "")
    if not expected:
        return True
    return sent is not None and hmac.compare_digest(sent.encode("utf-8"), expected.encode("utf-8"))


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

    One write() of one line, under a lock shared by the server's request
    threads. The app runs as one process, so no file lock is needed.
    """
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    capture_path = os.path.normpath(_CAPTURE_FILE)
    with _capture_lock, open(capture_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line)
    _notify_capture()  # ai: claude-opus-5-5 | 2026-11-19
    return capture_path


# ai: claude-opus-5-5 | 2026-11-19
def _notify_capture() -> None:
    global _capture_count
    with _capture_changed:
        _capture_count += 1
        _capture_changed.notify_all()


# ai: claude-opus-5-5 | 2026-11-19
def _notify_readings() -> None:
    global _readings_count
    with _capture_changed:
        _readings_count += 1
        _capture_changed.notify_all()


# ai: claude-opus-5-5 | 2026-11-19
def last_capture_time() -> str | None:
    """When the last payload was captured (ISO 8601, UTC), or None if none has been.

    Read from the capture file's modification time: append_capture is its only
    writer, so the file itself is the record and survives restarts.
    """
    try:
        modified = os.stat(_CAPTURE_FILE).st_mtime
    except FileNotFoundError:
        return None
    return iso_utc(datetime.fromtimestamp(modified, UTC))


# ai: claude-opus-5-5 | 2026-11-19
@community_mod_bp.route("/status", methods=["GET"])
def capture_status() -> ResponseReturnValue:
    """
    When the community mod last sent a payload.
    ---
    tags:
      - Community Mod
    responses:
      200:
        description: "`last_received_at` as ISO 8601 UTC, or null if nothing has been received"
    """
    return jsonify({"last_received_at": last_capture_time()})


# ai: claude-opus-5-5 | 2026-11-19
@community_mod_bp.route("/events", methods=["GET"])
def capture_events() -> ResponseReturnValue:
    """
    Server-sent events: `capture` after each payload, and `readings` when one saved reputation values.
    ---
    tags:
      - Community Mod
    produces:
      - text/event-stream
    responses:
      200:
        description: >-
          An open event stream. `capture` carries the new `last_received_at`; `readings` means faction
          values changed, so re-read them. Events missed while disconnected are not replayed: re-read
          /status and the faction summary after reconnecting.
    """
    return Response(
        capture_event_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ai: claude-opus-5-5 | 2026-11-19
def capture_event_stream() -> Iterator[str]:
    """Yield SSE frames: `capture` and `readings` events as their counters change, else a keepalive.

    The first frame goes out at once, so the response headers are sent and the
    browser's EventSource reports the connection open. Several changes in one
    wait collapse into one event of each kind: each only means "go and re-read".
    """
    with _capture_changed:
        seen = _event_counts()
    yield "retry: 10000\n\n"
    while True:
        with _capture_changed:
            _capture_changed.wait_for(lambda: _event_counts() != seen, timeout=_KEEPALIVE_SECONDS)
            current = _event_counts()
        if current == seen:
            yield ": keepalive\n\n"
            continue
        if current[0] != seen[0]:
            yield f"event: capture\ndata: {json.dumps({'last_received_at': last_capture_time()})}\n\n"
        if current[1] != seen[1]:
            # A browser only dispatches an event that has a data line.
            yield "event: readings\ndata: {}\n\n"
        seen = current


# ai: claude-opus-5-5 | 2026-11-19
def _event_counts() -> tuple[int, int]:
    """(captures, reading saves) so far; read it holding _capture_changed."""
    return _capture_count, _readings_count
