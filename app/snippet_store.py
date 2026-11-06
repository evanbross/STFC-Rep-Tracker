# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""The one place that knows where template snippets live (N-O1).

Snippets come from two folders, both named by settings ``snippets_dir``:

- the **user** folder under ``runtime_dir()``, where every new snippet is
  written (uploads, captured combat templates, target samples), and
- the **bundled** folder under ``resource_dir()``, holding the defaults
  shipped with the build.

Lookups check the user folder first, so a user file overrides a bundled one
of the same name. In the frozen build the bundled folder is inside
``_internal``, which a reinstall replaces; writing there used to lose
user-added snippets on every upgrade. In a source checkout both folders are
the same directory, so nothing changes there.
"""
import os

from werkzeug.security import safe_join

from app.app_config import capture_cfg
from app.paths import resource_path, runtime_path

_DEFAULT_SNIPPETS_DIR = "app/screen_snippets"


def _configured_dir() -> str:
    return capture_cfg("snippets_dir", default=_DEFAULT_SNIPPETS_DIR)


def user_snippets_dir() -> str:
    """Writable snippets folder; every new snippet goes here."""
    return runtime_path(_configured_dir())


def bundled_snippets_dir() -> str:
    """Read-only snippets folder shipped with the build."""
    return resource_path(_configured_dir())


def snippet_dirs() -> list[str]:
    """Lookup order: user folder, then bundled (one entry when they are the same folder)."""
    user, bundled = user_snippets_dir(), bundled_snippets_dir()
    return [user] if os.path.normcase(user) == os.path.normcase(bundled) else [user, bundled]


def find_snippet(filename: str) -> str | None:
    """Absolute path of an existing snippet, user folder first; None if absent.

    ``filename`` may include a subfolder (``target_samples/x.png``). A name that
    escapes the snippets folders (``../x``, an absolute path) is never found.
    """
    for directory in snippet_dirs():
        candidate = safe_join(directory, filename)
        if candidate and os.path.isfile(candidate):
            return os.path.normpath(candidate)
    return None


def snippet_exists(filename: str) -> bool:
    return find_snippet(filename) is not None


def new_snippet_path(filename: str) -> str:
    """Path in the user folder to write a new snippet to, creating its parent folder.

    Raises ValueError for a name that would escape the user folder.
    """
    candidate = safe_join(user_snippets_dir(), filename)
    if candidate is None:
        raise ValueError(f"Snippet name escapes the snippets folder: {filename!r}")
    os.makedirs(os.path.dirname(candidate), exist_ok=True)
    return os.path.normpath(candidate)
