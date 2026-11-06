# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Cross-origin write protection shared by every Flask app in the process.

CORS only decides whether a page may *read* a response. It does not stop a page
on another origin from *sending* a POST to http://localhost, which is enough to
drive the game or edit data. This guard rejects such writes before they reach a
route. Leaf module: imports nothing from the project.
"""
import logging
from collections.abc import Iterable
from urllib.parse import urlsplit

from flask import Flask, jsonify, request
from flask.typing import ResponseReturnValue

logger = logging.getLogger(__name__)

UNSAFE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
API_PREFIX = "/api/"


def origin_of(url: str) -> str:
    """Return the scheme://host[:port] part of a URL or Origin header value."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def is_trusted_api_write_origin(source: str | None, self_origin: str, cors_origins: Iterable[str]) -> bool:
    """Decide whether a state-changing request may proceed.

    `source` is the Origin header, falling back to Referer. A request with
    neither (curl, the test client, the community mod) has nothing forgeable to
    check and is allowed: browsers always send Origin on cross-origin POSTs.
    """
    if not source:
        return True
    trusted = {origin_of(self_origin), *(origin_of(o.strip()) for o in cors_origins if o.strip())}
    return origin_of(source) in trusted


def install_cross_origin_write_guard(flask_app: Flask, cors_origins: Iterable[str]) -> None:
    """Register a before_request hook that 403s untrusted cross-origin /api writes."""
    allowed = tuple(cors_origins)

    @flask_app.before_request
    def reject_cross_origin_api_writes() -> ResponseReturnValue | None:
        if request.method not in UNSAFE_METHODS or not request.path.startswith(API_PREFIX):
            return None
        source = request.headers.get("Origin") or request.headers.get("Referer")
        if is_trusted_api_write_origin(source, f"{request.scheme}://{request.host}", allowed):
            return None
        logger.warning("rejected cross-origin %s %s from %s", request.method, request.path, source)
        return jsonify({"error": "Cross-origin request rejected"}), 403
