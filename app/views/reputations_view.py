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

from flask import Blueprint, Response, jsonify

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


# ai: claude-opus-5-5 | 2026-11-06
@reputations_bp.route("/types", methods=["GET"])
def get_reputation_types() -> Response:
    """
    Reputation types a faction can use, one per *_reputations_dao.py implementation
    ---
    tags:
      - Reputations
    responses:
      200:
        description: "[{table_name, dao_name}], sorted by table name"
    """
    return jsonify(ReputationsDAO.available_types())


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
    daos = ReputationsDAO.all_daos()  # ai: claude-opus-5-5 | 2026-11-06
    result: list[dict[str, Any]] = []
    for dao_name, dao in daos.items():
        logger.info(f"Fetching reputations for {dao_name}")
        try:
            reps = dao.get_all()  # ai: claude-opus-5-5 | 2026-11-06
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

    # The DAO writes the row and refreshes its in-memory tier cache.
    dao = ReputationsDAO.get_dao_by_table_name(table_name)
    if dao is None:
        raise NotFoundError(f"Unknown reputation table: '{table_name}'")
    dao.update_row(row_id, sent)

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
    dao = ReputationsDAO.get_dao_by_table_name(table_name)
    if dao is None:
        return jsonify({"error": f"Unknown reputation table: '{table_name}'"}), 404
    return jsonify(dao.get_all())  # ai: claude-opus-5-5 | 2026-11-06
