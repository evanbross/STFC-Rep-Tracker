# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Snippet-image files shared by the factions and target-types blueprints (N-X2).

The snippets directory also holds non-image files (favicon.zip, for example),
so the image routes serve only the extensions the app itself writes or accepts
for upload. send_from_directory already blocks path traversal.
"""
import os

from flask import Response, abort, send_from_directory

from app.app_config import capture_cfg

SNIPPET_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})


def snippets_dir() -> str:
    """Absolute path of the configured snippets directory (settings: snippets_dir)."""
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__), "..", "..",
            capture_cfg("snippets_dir", default="app/screen_snippets"),
        )
    )


def is_snippet_image(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SNIPPET_IMAGE_EXTENSIONS


def send_snippet_image(filename: str) -> Response:
    """Serve an image from the snippets directory; anything else is a 404."""
    if not is_snippet_image(filename):
        abort(404)
    return send_from_directory(snippets_dir(), filename)
