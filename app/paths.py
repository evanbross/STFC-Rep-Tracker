# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Where the app's files live, for source runs and the PyInstaller build (N-O1).

Two roots:

- ``runtime_dir()`` is writable and survives upgrades: the folder holding the
  executable when frozen, the project root otherwise. settings.yaml, .env,
  certificates, screenshots, Google tokens, community captures and
  user-added snippets live here.
- ``resource_dir()`` holds read-only files shipped with the build: the
  PyInstaller ``_internal`` folder when frozen, the project root otherwise.
  The built frontend, logging.yaml and the bundled default snippets live here.

In a source checkout both roots are the project root.

This is a leaf module: it imports nothing from the project, so anything
(including app_config) can import it without creating a cycle.
"""
import os
import sys

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def is_frozen() -> bool:
    """True when running from the PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def runtime_dir() -> str:
    """Writable application folder that survives reinstalls."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return _PROJECT_ROOT


def resource_dir() -> str:
    """Read-only folder holding the files bundled with the build."""
    if is_frozen():
        # PyInstaller sets _MEIPASS on sys at startup; it has no other public name.
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return _PROJECT_ROOT


def runtime_path(relative_path: str) -> str:
    """Resolve a path under runtime_dir(). An absolute path is returned unchanged."""
    return os.path.normpath(os.path.join(runtime_dir(), relative_path))


def resource_path(relative_path: str) -> str:
    """Resolve a path under resource_dir(). An absolute path is returned unchanged."""
    return os.path.normpath(os.path.join(resource_dir(), relative_path))


def settings_path() -> str:
    """settings.yaml, which the user edits and the app rewrites, so it is a runtime file."""
    return runtime_path("settings.yaml")
