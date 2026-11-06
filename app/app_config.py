# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
"""Loads settings from settings.yaml at the project root.

Usage:
    from app.app_config import capture_cfg

    threshold = capture_cfg("button_match_threshold")
    titles    = capture_cfg("window_titles")
    retries   = capture_cfg("navigation", "max_retries")
"""
import logging
import os
import re
import sys
from typing import Literal

import yaml

logger = logging.getLogger(__name__)

# ai: claude-opus-5-5 | 2026-11-06
# The combat template kinds that can be saved from the UI; each one has an
# add_<kind>_template() below. Request validation uses this Literal directly.
TemplateKind = Literal["hostile_ship", "skull_glyph", "diamond_glyph"]


def _runtime_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


_SETTINGS_PATH = os.path.join(_runtime_dir(), "settings.yaml")

_cfg: dict = {}


def _load():
    global _cfg
    try:
        with open(_SETTINGS_PATH) as f:
            data = yaml.safe_load(f) or {}
        _cfg = data.get("stfc_config", {})
        logger.debug(f"loaded from {_SETTINGS_PATH}")
    except FileNotFoundError:
        logger.warning(f"{_SETTINGS_PATH} not found — using defaults")
    except Exception as e:
        logger.error(f"failed to load settings: {e}")


_load()


def capture_cfg(*keys, default=None):
    """Look up a value from the stfc_config section by one or more nested keys.

    Examples:
        capture_cfg("button_match_threshold")       -> 0.85
        capture_cfg("navigation", "max_retries")    -> 8
        capture_cfg("factions", "snippet_threshold") -> 0.70
    """
    node = _cfg
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key, default)
        if node is default:
            return default
    return node


# ai: claude-sonnet-5 | 2026-09-18
def _add_combat_template(key: str, filename: str) -> list[str]:
    """Append filename to combat.<key> (a template-filename list) in
    settings.yaml and return the updated list. No-op (returns the existing
    list) if filename is already present.

    Rewrites only that one block in place, line-by-line, rather than
    round-tripping the whole file through yaml.safe_dump — that would strip
    every comment in settings.yaml, which is documentation the user relies
    on. Also updates the in-memory _cfg so capture_cfg() reflects the change
    immediately, without a backend restart.
    """
    current: list[str] = capture_cfg("combat", key, default=[]) or []
    if filename in current:
        return current
    updated = [*current, filename]

    with open(_SETTINGS_PATH) as f:
        lines = f.readlines()

    key_idx = None
    indent = ""
    for i, line in enumerate(lines):
        match = re.match(rf"^( *){re.escape(key)}:", line)
        if match:
            key_idx = i
            indent = match.group(1)
            break
    if key_idx is None:
        raise RuntimeError(f"combat.{key} key not found in settings.yaml")

    item_prefix = f"{indent}  - "
    end_idx = key_idx + 1
    while end_idx < len(lines) and lines[end_idx].startswith(item_prefix):
        end_idx += 1

    new_block = [f"{indent}{key}:\n"]
    new_block += [f"{item_prefix}{name}\n" for name in updated]
    lines[key_idx:end_idx] = new_block

    with open(_SETTINGS_PATH, "w") as f:
        f.writelines(lines)

    _cfg.setdefault("combat", {})[key] = updated
    logger.info(f"Added combat.{key} entry to settings.yaml: {filename}")
    return updated


def add_hostile_ship_template(filename: str) -> list[str]:
    """Append filename to combat.hostile_ship_templates in settings.yaml."""
    return _add_combat_template("hostile_ship_templates", filename)


def add_skull_glyph_template(filename: str) -> list[str]:
    """Append filename to combat.skull_glyph_templates in settings.yaml."""
    return _add_combat_template("skull_glyph_templates", filename)


def add_diamond_glyph_template(filename: str) -> list[str]:
    """Append filename to combat.diamond_glyph_templates in settings.yaml."""
    return _add_combat_template("diamond_glyph_templates", filename)
