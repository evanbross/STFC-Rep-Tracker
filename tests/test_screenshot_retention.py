# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""R11: screenshot pruning is signal-driven, keeps the newest files, and stops."""
import os
import time
from pathlib import Path

import pytest

from app.screenshot_retention import ScreenshotPruner, prune_oldest

# Far longer than any test runs, so only a signal can trigger a prune.
_NO_SWEEP = 3600.0


def _make_files(folder: Path, count: int, start: int = 0) -> list[Path]:
    """Create count files with strictly increasing mtimes (oldest first)."""
    paths = []
    base = time.time() - 10_000
    for i in range(start, start + count):
        path = folder / f"capture_{i:03d}.png"
        path.write_bytes(b"x")
        os.utime(path, (base + i, base + i))
        paths.append(path)
    return paths


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _file_names(folder: Path) -> set[str]:
    return {p.name for p in folder.iterdir() if p.is_file()}


def test_prune_keeps_newest_by_mtime(tmp_path):
    paths = _make_files(tmp_path, 5)
    deleted = prune_oldest(str(tmp_path), keep=2)
    assert sorted(deleted) == sorted(str(p) for p in paths[:3])
    assert _file_names(tmp_path) == {paths[3].name, paths[4].name}


def test_prune_under_limit_deletes_nothing(tmp_path):
    _make_files(tmp_path, 3)
    assert prune_oldest(str(tmp_path), keep=3) == []
    assert len(_file_names(tmp_path)) == 3


def test_prune_leaves_subfolders_alone(tmp_path):
    debug = tmp_path / "debug"
    debug.mkdir()
    (debug / "crop.png").write_bytes(b"x")
    _make_files(tmp_path, 3)
    prune_oldest(str(tmp_path), keep=1)
    assert (debug / "crop.png").exists()


def test_prune_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        prune_oldest(str(tmp_path / "nope"), keep=1)


def test_pruner_prunes_on_start(tmp_path):
    _make_files(tmp_path, 4)
    pruner = ScreenshotPruner()
    pruner.start(str(tmp_path), keep=2, sweep_seconds=_NO_SWEEP)
    try:
        assert _wait_until(lambda: len(_file_names(tmp_path)) == 2)
    finally:
        pruner.stop(timeout=5)


def test_pruner_prunes_on_signal_not_timer(tmp_path):
    pruner = ScreenshotPruner()
    pruner.start(str(tmp_path), keep=2, sweep_seconds=_NO_SWEEP)
    try:
        # Let the startup prune (of the empty folder) finish, or it races the file creation.
        time.sleep(0.2)
        newest = _make_files(tmp_path, 4)
        # Without a signal, the long sweep never fires during the test.
        time.sleep(0.2)
        assert len(_file_names(tmp_path)) == 4
        pruner.notify_written()
        assert _wait_until(lambda: _file_names(tmp_path) == {newest[2].name, newest[3].name})
    finally:
        pruner.stop(timeout=5)


def test_pruner_stop_ends_thread(tmp_path):
    pruner = ScreenshotPruner()
    pruner.start(str(tmp_path), keep=2, sweep_seconds=_NO_SWEEP)
    thread = pruner._thread
    pruner.stop(timeout=5)
    assert thread is not None and not thread.is_alive()


def test_pruner_survives_missing_folder(tmp_path):
    folder = tmp_path / "later"
    pruner = ScreenshotPruner()
    pruner.start(str(folder), keep=1, sweep_seconds=_NO_SWEEP)
    try:
        time.sleep(0.1)  # the startup prune fails: folder doesn't exist yet
        folder.mkdir()
        _make_files(folder, 3)
        pruner.notify_written()
        assert _wait_until(lambda: len(_file_names(folder)) == 1)
    finally:
        pruner.stop(timeout=5)
