# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Tests for the settings.yaml combat-template writer, against a temp file."""
from pathlib import Path

import pytest
import yaml

from app import app_config

_SETTINGS = """\
stfc_config:
  combat:
    # Hostile ship icons — this comment must survive a rewrite.
    hostile_ship_templates:
      - a.png
    skull_glyph_templates: []
    max_track_distance_px: 250
"""


@pytest.fixture(name="settings_file")
def fixture_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point app_config at a temp settings.yaml and load it into the in-memory cache."""
    path = tmp_path / "settings.yaml"
    path.write_text(_SETTINGS, encoding="utf-8")
    monkeypatch.setattr(app_config, "_SETTINGS_PATH", str(path))
    monkeypatch.setattr(app_config, "_cfg", yaml.safe_load(_SETTINGS)["stfc_config"])
    return path


def test_add_template_appends_and_keeps_comments(settings_file: Path) -> None:
    result = app_config.add_hostile_ship_template("b.png")

    assert result == ["a.png", "b.png"]
    text = settings_file.read_text(encoding="utf-8")
    assert "# Hostile ship icons — this comment must survive a rewrite." in text
    reloaded = yaml.safe_load(text)["stfc_config"]["combat"]
    assert reloaded["hostile_ship_templates"] == ["a.png", "b.png"]
    assert reloaded["max_track_distance_px"] == 250
    assert app_config.capture_cfg("combat", "hostile_ship_templates") == ["a.png", "b.png"]


def test_add_template_is_idempotent(settings_file: Path) -> None:
    before = settings_file.read_text(encoding="utf-8")

    assert app_config.add_hostile_ship_template("a.png") == ["a.png"]
    assert settings_file.read_text(encoding="utf-8") == before


def test_add_template_replaces_inline_empty_list(settings_file: Path) -> None:
    """settings.yaml.example ships keys as `key: []`; the writer must handle that form."""
    assert app_config.add_skull_glyph_template("skull.png") == ["skull.png"]

    combat = yaml.safe_load(settings_file.read_text(encoding="utf-8"))["stfc_config"]["combat"]
    assert combat["skull_glyph_templates"] == ["skull.png"]
    assert combat["hostile_ship_templates"] == ["a.png"]


def test_add_template_missing_key_raises(settings_file: Path) -> None:
    with pytest.raises(RuntimeError, match="diamond_glyph_templates key not found"):
        app_config.add_diamond_glyph_template("diamond.png")
