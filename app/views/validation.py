# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Request-body parsing and the app-wide mapping of expected errors to HTTP status.

Routes call parse_body(Model) / parse_query(Model) and let InvalidRequestError, NotFoundError and
ConflictError propagate; register_error_handlers() turns them into 400/404/409
JSON responses. Error bodies keep the {"error": ...} shape the frontend reads.
"""
import logging
from typing import TypeVar

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue
from pydantic import BaseModel, ValidationError
from werkzeug.exceptions import HTTPException

from app.domain_errors import ConflictError, NotFoundError, NoUpdatableFieldsError

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class InvalidRequestError(Exception):
    """A request body failed validation; carries client-safe field messages."""

    def __init__(self, fields: list[dict[str, str]]) -> None:
        super().__init__("Invalid request")
        self.fields = fields


def _field_errors(exc: ValidationError) -> list[dict[str, str]]:
    """Field path and message per error, never the rejected input value."""
    return [
        {"field": ".".join(str(part) for part in err["loc"]) or "body", "message": err["msg"]}
        for err in exc.errors(include_url=False, include_input=False)
    ]


def parse_body(model: type[ModelT], *, optional: bool = False) -> ModelT:
    """Validate the JSON request body against `model`.

    A missing or non-JSON body is an error unless `optional`, in which case
    the model is built from its defaults.
    """
    data = request.get_json(silent=True)
    if data is None:
        if not optional:
            raise InvalidRequestError([{"field": "body", "message": "Request body must be JSON"}])
        data = {}
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise InvalidRequestError(_field_errors(exc)) from exc


# ai: claude-opus-5-5 | 2026-11-06
def parse_query(model: type[ModelT]) -> ModelT:
    """Validate the query string against `model` (first value of each repeated key)."""
    try:
        return model.model_validate(request.args.to_dict())
    except ValidationError as exc:
        raise InvalidRequestError(_field_errors(exc)) from exc


def register_error_handlers(flask_app: Flask) -> None:
    """Map the expected exception types to JSON responses app-wide."""

    @flask_app.errorhandler(InvalidRequestError)
    def handle_invalid_request(exc: InvalidRequestError) -> ResponseReturnValue:
        summary = "; ".join(f"{f['field']}: {f['message']}" for f in exc.fields)
        return jsonify({"error": f"Invalid request: {summary}", "fields": exc.fields}), 400

    @flask_app.errorhandler(NoUpdatableFieldsError)  # ai: claude-opus-5-5 | 2026-11-06
    def handle_no_updatable_fields(exc: NoUpdatableFieldsError) -> ResponseReturnValue:
        return jsonify({"error": str(exc)}), 400

    @flask_app.errorhandler(NotFoundError)
    def handle_not_found(exc: NotFoundError) -> ResponseReturnValue:
        return jsonify({"error": str(exc)}), 404

    @flask_app.errorhandler(ConflictError)
    def handle_conflict(exc: ConflictError) -> ResponseReturnValue:
        logger.info("conflict: %s", exc)
        return jsonify({"error": str(exc)}), 409

    # The outermost boundary: anything unexpected is logged with its traceback
    # and answered without exception text, which can carry SQL or paths.
    @flask_app.errorhandler(Exception)
    def handle_unexpected(exc: Exception) -> ResponseReturnValue:
        if isinstance(exc, HTTPException):
            return exc
        logger.exception("unhandled error in %s %s", request.method, request.path)
        return jsonify({"error": "Unexpected server error"}), 500
