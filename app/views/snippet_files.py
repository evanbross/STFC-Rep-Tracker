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

The snippets directory can also hold non-image files (an archive, for example),
so the image routes serve only the extensions the app itself writes or accepts
for upload. Lookup (user folder, then bundled) and traversal checks live in
app.snippet_store.
"""
import os

from flask import Response, abort, send_file

from app.snippet_store import find_snippet

SNIPPET_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})


def is_snippet_image(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SNIPPET_IMAGE_EXTENSIONS


def send_snippet_image(filename: str) -> Response:
    """Serve an image from the snippets folders; anything else is a 404."""
    if not is_snippet_image(filename):
        abort(404)
    path = find_snippet(filename)
    if path is None:
        abort(404)
    return send_file(path)
