# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify

from app.database.reputations_dao import ReputationsDAO
from app.domain_errors import NotFoundError
from app.views.request_models import ReputationRowPatch
from app.views.validation import parse_body

logger = logging.getLogger(__name__)

reputations_bp = Blueprint("reputations", __name__)


def _validate_table_name(table_name: str) -> tuple[Response, int] | None:
    known = ReputationsDAO.get_known_table_names()
    if table_name not in known:
        return jsonify({"error": f"Unknown reputation table: '{table_name}'"}), 404
    return None


def _get_faction_reputations(table_name: str, display_name: str) -> tuple[Response, int] | Response:
    """Shared handler for per-faction reputation GET routes."""
    dao = ReputationsDAO.get_dao_by_table_name(table_name)
    if not dao:
        return jsonify({"error": f"{display_name} reputation DAO not found"}), 404
    return jsonify(dao.get_all())


@reputations_bp.route("", methods=["GET"])
def get_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("fkr_reputations", "FKR")


@reputations_bp.route("/augment", methods=["GET"])
def get_augment_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("augment_reputations", "Augment")


@reputations_bp.route("/rogue", methods=["GET"])
def get_rogue_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("rogue_reputations", "Rogue")


@reputations_bp.route("/bajoran", methods=["GET"])
def get_bajoran_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("bajoran_reputations", "Bajoran")


@reputations_bp.route("/terran", methods=["GET"])
def get_terran_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("terran_reputations", "Terran")


@reputations_bp.route("/dti", methods=["GET"])
def get_dti_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("dti_reputations", "DTI")


@reputations_bp.route("/section31", methods=["GET"])
def get_section31_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("section31_reputations", "Section 31")


@reputations_bp.route("/ex-borg", methods=["GET"])
def get_ex_borg_reputations() -> tuple[Response, int] | Response:
    return _get_faction_reputations("ex_borg_reputations", "Ex-Borg")


@reputations_bp.route("/all", methods=["GET"])
def get_all_reputations_grouped() -> Response:
    """
    Get all reputations grouped by their reputation table
    ---
    tags:
      - Reputations
    responses:
      200:
        description: All reputations grouped by table
    """
    db = current_app.config["DATABASE"]
    daos = ReputationsDAO.get_all_dao_by_class_name()
    result: list[dict[str, Any]] = []
    for dao_name, dao in daos.items():
        logger.info(f"Fetching reputations for {dao_name}")
        try:
            reps = dao.get_all(db)
            title = f"{dao.get_table_name()} Reputation Tiers"
            result.append(
                {
                    "title": title,
                    "table_name": dao.get_table_name(),
                    "data": reps,
                }
            )
        except Exception as e:
            logger.error(f"Error fetching reputations for {dao_name}: {e}")

    return jsonify(result)


@reputations_bp.route("/by-table/<table_name>/<int:row_id>", methods=["PUT"])
def update_reputation_row(table_name: str, row_id: int) -> tuple[Response, int] | Response:
    """
    Update a single reputation tier row by table name and id
    ---
    tags:
      - Reputations
    parameters:
      - name: table_name
        in: path
        type: string
        required: true
      - name: row_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Updated successfully
      400:
        description: Invalid body, or no field this table has
      404:
        description: Unknown table or row
    """
    err = _validate_table_name(table_name)
    if err:
        return err
    # ai: claude-opus-5-5 | 2026-11-06
    # Only fields the client actually sent change; an explicit null is kept so
    # the top tier's high_limit can be cleared.
    sent = parse_body(ReputationRowPatch).model_dump(exclude_unset=True)

    with current_app.config["DATABASE"].connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND table_schema = current_schema()",  # ai: claude-opus-5-5 | 2026-11-05
            (table_name,),
        )
        columns = {row[0].lower(): row[0] for row in cursor.fetchall()}
        if not columns:
            raise NotFoundError(f"Table '{table_name}' not found")

        # Column names come from information_schema, never from the request.
        updates = {columns[field]: value for field, value in sent.items() if field in columns}
        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        assignments = ", ".join(f'"{column}" = %s' for column in updates)
        cursor.execute(
            f'UPDATE "{table_name}" SET {assignments} WHERE id = %s', [*updates.values(), row_id]
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"Row {row_id} not found in '{table_name}'")

    return jsonify({"success": True})


@reputations_bp.route("/by-table/<table_name>", methods=["GET"])
def get_reputations_by_table(table_name: str) -> tuple[Response, int] | Response:
    """
    Get list of all reputations from a specific reputation table
    ---
    tags:
      - Reputations
    parameters:
      - name: table_name
        in: path
        type: string
        required: true
        description: Name of the reputation table
    responses:
      200:
        description: A list of reputations
      400:
        description: Invalid table name
    """
    err = _validate_table_name(table_name)
    if err:
        return err
    db = current_app.config["DATABASE"]
    dao = ReputationsDAO.get_dao_by_table_name(table_name)
    if dao is None:
        return jsonify({"error": f"Unknown reputation table: '{table_name}'"}), 404
    try:
        reputations = dao.get_all(db)
        return jsonify(reputations)
    except Exception:
        logger.exception("Error fetching reputations by table")
        return jsonify({"error": "Failed to retrieve reputations"}), 500
