# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-17
"""Import faction reputation from a Spock's Club data export.

Two steps, so the user sees what will be saved first:
- POST /preview takes the uploaded TSV and returns each mapped faction's value.
- POST /import saves the confirmed readings at one timestamp.
"""
import logging
from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from app.spocks_club_parsing import (
    SpocksClubFormatError,
    export_time_from_filename,
    match_factions,
    parse_resource_amounts,
)
from app.views.request_models import SpocksClubImportIn, SpocksClubPreviewForm
from app.views.validation import parse_body, parse_form

logger = logging.getLogger(__name__)

spocks_club_bp = Blueprint("spocks_club", __name__)

# Real exports are about 2 MB; anything far larger isn't one.
MAX_EXPORT_BYTES = 20 * 1024 * 1024


def _export_time(filename: str | None, last_modified_ms: int | None) -> tuple[datetime, str]:
    """When the export was taken, and where that came from: the filename, the file's date, or now."""
    from_name = export_time_from_filename(filename)
    if from_name is not None:
        return from_name, "filename"
    if last_modified_ms is not None:
        return datetime.fromtimestamp(last_modified_ms / 1000, UTC), "file_modified"
    return datetime.now(UTC), "now"


@spocks_club_bp.route("/preview", methods=["POST"])
def preview_import() -> ResponseReturnValue:
    """
    Read a Spock's Club export and show the reputation it holds for each faction
    ---
    tags:
      - Spock's Club
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: The TSV exported from Spock's Club
      - name: last_modified
        in: formData
        type: integer
        required: false
        description: The file's last-modified time in ms since the epoch; used when the filename has no export time
    responses:
      200:
        description: Mapped readings, factions with no reading, and the suggested timestamp
      400:
        description: No file, or a file that isn't a Spock's Club export
      413:
        description: File too large
    """
    form = parse_form(SpocksClubPreviewForm)
    upload = request.files.get("file")
    if upload is None:
        return jsonify({"error": "Choose a Spock's Club export (.tsv) to import."}), 400

    raw = upload.read(MAX_EXPORT_BYTES + 1)
    if len(raw) > MAX_EXPORT_BYTES:
        return jsonify({"error": "That file is too large to be a Spock's Club export."}), 413
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return jsonify({"error": "That file isn't a text export. Choose the .tsv file from Spock's Club."}), 400
    try:
        amounts = parse_resource_amounts(text)
    except SpocksClubFormatError as exc:
        return jsonify({"error": str(exc)}), 400

    db = current_app.config["DATABASE"]
    readings, unmatched = match_factions(db.factions.get_all_factions(), amounts)
    current = {f["code"]: f for f in db.factions.get_faction_summary()}
    exported_at, source = _export_time(upload.filename, form.last_modified)
    logger.info("Spock's Club preview: %d reading(s), %d unmatched", len(readings), len(unmatched))

    return jsonify({
        "exported_at": exported_at.isoformat(),
        "exported_at_source": source,
        "readings": [
            {
                "faction_code": reading.faction_code,
                "faction_name": reading.faction_name,
                "resource_id": reading.resource_id,
                "value": reading.value,
                "previous_value": current[reading.faction_code]["current_value"]
                if current[reading.faction_code]["last_updated"] else None,
                "previous_updated": current[reading.faction_code]["last_updated"],
            }
            for reading in readings
        ],
        "unmatched": unmatched,
    })


@spocks_club_bp.route("/import", methods=["POST"])
def import_readings() -> ResponseReturnValue:
    """
    Save previewed Spock's Club readings as status entries
    ---
    tags:
      - Spock's Club
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - exported_at
            - readings
          properties:
            exported_at:
              type: string
              format: date-time
              description: ISO 8601 with an offset; every reading is saved at this instant
            readings:
              type: array
              items:
                type: object
                required: [faction_code, value]
                properties:
                  faction_code:
                    type: string
                  value:
                    type: integer
    responses:
      201:
        description: Saved entries, and codes skipped because they already had a reading at that instant
      400:
        description: Invalid body (missing fields, a faction twice, or a future timestamp)
      404:
        description: Unknown faction code; nothing was saved
    """
    body = parse_body(SpocksClubImportIn)
    saved, skipped = current_app.config["DATABASE"].status_entries.add_entries_at(
        body.exported_at, {reading.faction_code: reading.value for reading in body.readings}
    )
    logger.info("Spock's Club import: %d saved, %d skipped", len(saved), len(skipped))
    return jsonify({"saved": saved, "skipped": skipped}), 201
