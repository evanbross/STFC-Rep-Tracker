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
    with pytest.raises(app_config.SettingsFileError, match="diamond_glyph_templates key not found"):
        app_config.add_diamond_glyph_template("diamond.png")


# ai: claude-opus-5-5 | 2026-11-06
def _use_settings(path: Path, text: str | bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write a settings file (bytes keep exact line endings) and point app_config at it."""
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(app_config, "_SETTINGS_PATH", str(path))
    monkeypatch.setattr(app_config, "_cfg", {})


def test_crlf_and_utf8_survive_a_rewrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = _SETTINGS.replace("— this", "× this").replace("\n", "\r\n").encode("utf-8")
    path = tmp_path / "settings.yaml"
    _use_settings(path, original, monkeypatch)

    app_config.add_hostile_ship_template("b.png")

    raw = path.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    assert "× this comment".encode("utf-8") in raw


def test_hand_edits_made_while_running_are_kept(settings_file: Path) -> None:
    """The cache was loaded with [a.png]; the file now also has c.png."""
    settings_file.write_text(_SETTINGS.replace("      - a.png\n", "      - a.png\n      - c.png\n"), encoding="utf-8")

    assert app_config.add_hostile_ship_template("b.png") == ["a.png", "c.png", "b.png"]


def test_same_key_outside_combat_is_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = "stfc_config:\n  other:\n    hostile_ship_templates: keep-me\n" + _SETTINGS.split("stfc_config:\n", 1)[1]
    path = tmp_path / "settings.yaml"
    _use_settings(path, text, monkeypatch)

    app_config.add_hostile_ship_template("b.png")

    reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))["stfc_config"]
    assert reloaded["other"]["hostile_ship_templates"] == "keep-me"
    assert reloaded["combat"]["hostile_ship_templates"] == ["a.png", "b.png"]


def test_unusual_layout_is_refused_without_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A comment between list items would make the line rewrite duplicate entries."""
    text = _SETTINGS.replace("      - a.png\n", "      - a.png\n      # note\n      - z.png\n")
    path = tmp_path / "settings.yaml"
    _use_settings(path, text, monkeypatch)

    with pytest.raises(app_config.SettingsFileError, match="not written"):
        app_config.add_hostile_ship_template("b.png")
    assert path.read_text(encoding="utf-8") == text


def test_failed_replace_keeps_original_and_cleans_up(settings_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = settings_file.read_text(encoding="utf-8")

    def refuse(_src: str, _dst: str) -> None:
        raise PermissionError("file in use")

    monkeypatch.setattr(app_config.os, "replace", refuse)

    with pytest.raises(PermissionError):
        app_config.add_hostile_ship_template("b.png")
    assert settings_file.read_text(encoding="utf-8") == before
    assert [p.name for p in settings_file.parent.iterdir()] == ["settings.yaml"]
    assert app_config.capture_cfg("combat", "hostile_ship_templates") == ["a.png"]


def test_unparseable_settings_file_is_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "settings.yaml"
    _use_settings(path, "stfc_config:\n  combat: [unclosed\n", monkeypatch)

    with pytest.raises(app_config.SettingsFileError, match="could not be loaded"):
        app_config.load_settings_file()


def test_missing_settings_file_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_config, "_SETTINGS_PATH", str(tmp_path / "absent.yaml"))
    monkeypatch.setattr(app_config, "_cfg", {})

    app_config.load_settings_file()

    assert app_config.capture_cfg("button_match_threshold", default=0.85) == 0.85


def test_settings_are_read_as_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "settings.yaml"
    _use_settings(path, "stfc_config:\n  label: 'Ship × 2 — Borg'\n", monkeypatch)

    app_config.load_settings_file()

    assert app_config.capture_cfg("label") == "Ship × 2 — Borg"
