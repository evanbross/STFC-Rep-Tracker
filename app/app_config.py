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
import contextlib
import copy
import logging
import os
import re
import sys
import tempfile
import threading
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
_SETTINGS_ENCODING = "utf-8"

_cfg: dict = {}

# ai: claude-opus-5-5 | 2026-11-06
# Serializes read-modify-write of settings.yaml across request threads.
_settings_write_lock = threading.Lock()


class SettingsFileError(RuntimeError):
    """settings.yaml exists but cannot be read, parsed, or safely edited."""


# ai: claude-opus-5-5 | 2026-11-06
def load_settings_file() -> None:
    """(Re)load settings.yaml into the in-memory cache read by capture_cfg().

    A missing file means "use code defaults" (Docker mounts it optionally).
    A file that exists but cannot be parsed is fatal: silently falling back to
    default thresholds would make every capture misbehave with no visible cause.
    """
    global _cfg
    try:
        with open(_SETTINGS_PATH, encoding=_SETTINGS_ENCODING) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"{_SETTINGS_PATH} not found — using defaults")
        return
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise SettingsFileError(
            f"{_SETTINGS_PATH} could not be loaded ({exc}). Fix it, or restore it from settings.yaml.example."
        ) from exc
    if not isinstance(data, dict):
        raise SettingsFileError(f"{_SETTINGS_PATH} must contain a mapping with a 'stfc_config' section")
    _cfg = data.get("stfc_config") or {}
    logger.debug(f"loaded from {_SETTINGS_PATH}")


load_settings_file()


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


# ai: claude-opus-5-5 | 2026-11-06
def _add_combat_template(key: str, filename: str) -> list[str]:
    """Append filename to combat.<key> (a template-filename list) in
    settings.yaml and return the updated list. No-op (returns the existing
    list) if filename is already present.

    Rewrites only that one block in place, line-by-line, rather than
    round-tripping the whole file through yaml.safe_dump — that would strip
    every comment in settings.yaml, which is documentation the user relies
    on. The list is re-read from the file under a lock (so entries added by
    hand while the app runs are kept), the edited text is re-parsed and must
    differ from the original only in that list, and the file is replaced
    atomically. Also updates the in-memory _cfg so capture_cfg() reflects the
    change immediately, without a backend restart.
    """
    with _settings_write_lock:
        with open(_SETTINGS_PATH, encoding=_SETTINGS_ENCODING, newline="") as f:
            original_text = f.read()
        original = yaml.safe_load(original_text) or {}
        combat = (original.get("stfc_config") or {}).get("combat") or {}
        if key not in combat:
            raise SettingsFileError(f"combat.{key} key not found in settings.yaml")
        current: list[str] = combat[key] or []
        if filename in current:
            _cfg.setdefault("combat", {})[key] = current
            return current
        updated = [*current, filename]

        new_text = _replace_combat_list(original_text, key, updated)
        _verify_single_list_change(original, new_text, key, updated)
        _atomic_write(_SETTINGS_PATH, new_text)

    _cfg.setdefault("combat", {})[key] = updated
    logger.info(f"Added combat.{key} entry to settings.yaml: {filename}")
    return updated


# ai: claude-opus-5-5 | 2026-11-06
def _replace_combat_list(text: str, key: str, items: list[str]) -> str:
    """Rewrite the `<key>:` list inside the `combat:` block, keeping the file's line endings."""
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)

    combat_idx, combat_indent = None, -1
    for i, line in enumerate(lines):
        match = re.match(r"^( *)combat:\s*(#.*)?$", line.rstrip("\r\n"))
        if match:
            combat_idx, combat_indent = i, len(match.group(1))
            break
    if combat_idx is None:
        raise SettingsFileError("combat: section not found in settings.yaml")

    key_idx, indent = None, ""
    for i in range(combat_idx + 1, len(lines)):
        stripped = lines[i].strip()
        line_indent = len(lines[i]) - len(lines[i].lstrip(" "))
        if stripped and not stripped.startswith("#") and line_indent <= combat_indent:
            break  # left the combat: block
        match = re.match(rf"^( +){re.escape(key)}:", lines[i])
        if match and len(match.group(1)) > combat_indent:
            key_idx, indent = i, match.group(1)
            break
    if key_idx is None:
        raise SettingsFileError(f"combat.{key} key not found in settings.yaml")

    item_prefix = f"{indent}  - "
    end_idx = key_idx + 1
    while end_idx < len(lines) and lines[end_idx].startswith(item_prefix):
        end_idx += 1

    lines[key_idx:end_idx] = [f"{indent}{key}:{eol}", *(f"{item_prefix}{name}{eol}" for name in items)]
    return "".join(lines)


# ai: claude-opus-5-5 | 2026-11-06
def _verify_single_list_change(original: dict, new_text: str, key: str, items: list[str]) -> None:
    """Refuse the write unless the new text parses to the original with only combat.<key> changed."""
    expected = copy.deepcopy(original)
    expected["stfc_config"]["combat"][key] = items
    try:
        actual = yaml.safe_load(new_text)
    except yaml.YAMLError as exc:
        raise SettingsFileError(f"edited settings.yaml would not parse; not written ({exc})") from exc
    if actual != expected:
        raise SettingsFileError(
            f"editing combat.{key} would change other settings (unusual layout?); settings.yaml not written"
        )


# ai: claude-opus-5-5 | 2026-11-06
def _atomic_write(path: str, text: str) -> None:
    """Write text to a temp file beside path, fsync it, then swap it in with os.replace().

    A crash mid-write leaves the old file intact instead of a truncated one.
    """
    fd, tmp_path = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=os.path.dirname(path) or ".")
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding=_SETTINGS_ENCODING, newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        replaced = True
    finally:
        if not replaced:
            with contextlib.suppress(FileNotFoundError):
                os.remove(tmp_path)


def add_hostile_ship_template(filename: str) -> list[str]:
    """Append filename to combat.hostile_ship_templates in settings.yaml."""
    return _add_combat_template("hostile_ship_templates", filename)


def add_skull_glyph_template(filename: str) -> list[str]:
    """Append filename to combat.skull_glyph_templates in settings.yaml."""
    return _add_combat_template("skull_glyph_templates", filename)


def add_diamond_glyph_template(filename: str) -> list[str]:
    """Append filename to combat.diamond_glyph_templates in settings.yaml."""
    return _add_combat_template("diamond_glyph_templates", filename)
