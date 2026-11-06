# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""app.paths, app.snippet_store and app.win_process (N-O1, N-O2). No database needed."""
import os
import sys
import uuid
from pathlib import Path

import pytest

from app import paths, snippet_store
from app.win_process import SingleInstanceLock

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _same(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


# ── paths ─────────────────────────────────────────────────────────────────────

def test_source_run_uses_project_root_for_both() -> None:
    assert not paths.is_frozen()
    assert _same(paths.runtime_dir(), _PROJECT_ROOT)
    assert _same(paths.resource_dir(), _PROJECT_ROOT)
    assert _same(paths.settings_path(), _PROJECT_ROOT / "settings.yaml")


def test_frozen_run_splits_runtime_and_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe_dir, bundle = tmp_path / "install", tmp_path / "install" / "_internal"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "STFCRepTracker.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert _same(paths.runtime_dir(), exe_dir)
    assert _same(paths.resource_dir(), bundle)
    assert _same(paths.runtime_path("settings.yaml"), exe_dir / "settings.yaml")
    assert _same(paths.resource_path("logging.yaml"), bundle / "logging.yaml")


def test_absolute_paths_pass_through(tmp_path: Path) -> None:
    assert _same(paths.runtime_path(str(tmp_path)), tmp_path)


# ── snippet_store ─────────────────────────────────────────────────────────────

@pytest.fixture(name="split_snippets")
def fixture_split_snippets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A frozen-style layout: separate user and bundled snippet folders."""
    user, bundled = tmp_path / "user", tmp_path / "bundled"
    user.mkdir()
    bundled.mkdir()
    monkeypatch.setattr(snippet_store, "user_snippets_dir", lambda: str(user))
    monkeypatch.setattr(snippet_store, "bundled_snippets_dir", lambda: str(bundled))
    return user, bundled


def test_lookup_prefers_user_then_falls_back_to_bundled(split_snippets: tuple[Path, Path]) -> None:
    user, bundled = split_snippets
    (bundled / "Shared.png").write_bytes(b"bundled")
    (user / "Shared.png").write_bytes(b"user")
    (bundled / "OnlyBundled.png").write_bytes(b"bundled")

    assert _same(snippet_store.find_snippet("Shared.png"), user / "Shared.png")
    assert _same(snippet_store.find_snippet("OnlyBundled.png"), bundled / "OnlyBundled.png")
    assert snippet_store.find_snippet("Missing.png") is None


def test_new_snippets_go_to_the_user_folder(split_snippets: tuple[Path, Path]) -> None:
    user, _ = split_snippets

    path = snippet_store.new_snippet_path("target_samples/Sol_scout.png")

    assert _same(path, user / "target_samples" / "Sol_scout.png")
    assert (user / "target_samples").is_dir()


@pytest.mark.parametrize("name", ["../escape.png", "a/../../escape.png"])
def test_escaping_names_are_rejected(split_snippets: tuple[Path, Path], name: str) -> None:
    user, _ = split_snippets
    (user.parent / "escape.png").write_bytes(b"x")

    assert snippet_store.find_snippet(name) is None
    with pytest.raises(ValueError):
        snippet_store.new_snippet_path(name)


def test_source_checkout_has_one_snippet_folder() -> None:
    assert snippet_store.snippet_dirs() == [snippet_store.user_snippets_dir()]


# ── win_process ───────────────────────────────────────────────────────────────

@pytest.mark.skipif(sys.platform != "win32", reason="named mutexes are Windows-only")
def test_single_instance_lock_refuses_a_second_holder() -> None:
    name = f"Local\\STFCRepTrackerTest-{uuid.uuid4()}"
    first, second, third = SingleInstanceLock(name), SingleInstanceLock(name), SingleInstanceLock(name)

    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    second.release()
    assert third.acquire() is True
    third.release()
