# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Keeps the screenshots folder from growing without bound (R11).

Screenshot writers call ``notify_written()`` after each save. That only sets an
Event, so the capture path never pays for a directory listing. The pruner
thread wakes on the signal and deletes the oldest files beyond ``keep``. A slow
timed sweep is a backstop for files written by something that doesn't signal
(a hand copy, an older build).

Leaf module: no project imports, so main.py can start it without pulling in
the capture stack, and screen_capture.py can signal it without a cycle.
"""
import logging
import os
import threading

logger = logging.getLogger(__name__)

DEFAULT_KEEP = 30
DEFAULT_SWEEP_SECONDS = 1800.0


# ai: claude-opus-5-5 | 2026-11-06
def prune_oldest(folder: str, keep: int) -> list[str]:
    """Delete the oldest regular files in folder beyond the newest `keep`.

    Subfolders (e.g. ``debug/``) are left alone. Returns the deleted paths.
    A file that vanishes between listing and deleting is skipped.
    """
    with os.scandir(folder) as entries:
        files = [entry for entry in entries if entry.is_file()]
    if len(files) <= keep:
        return []
    files.sort(key=lambda entry: entry.stat().st_mtime)
    deleted: list[str] = []
    for entry in files[:len(files) - keep]:
        try:
            os.remove(entry.path)
        except FileNotFoundError:
            continue
        deleted.append(entry.path)
    return deleted


# ai: claude-opus-5-5 | 2026-11-06
class ScreenshotPruner:
    """Background thread that prunes a folder when signalled, plus a timed backstop."""

    def __init__(self) -> None:
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(
        self,
        folder: str,
        keep: int = DEFAULT_KEEP,
        sweep_seconds: float = DEFAULT_SWEEP_SECONDS,
    ) -> None:
        """Start the pruner thread. Calling it again while running does nothing."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            # Prune once at startup: files from the last run count too.
            self._wake.set()
            self._thread = threading.Thread(
                target=self._run,
                args=(folder, keep, sweep_seconds),
                name="screenshot-pruner",
                daemon=True,
            )
            self._thread.start()

    def notify_written(self) -> None:
        """Signal that a screenshot was just written. Cheap; safe from any thread."""
        self._wake.set()

    def stop(self, timeout: float | None = None) -> None:
        """Stop the thread and wait up to `timeout` seconds for it to exit."""
        self._stop.set()
        self._wake.set()
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _run(self, folder: str, keep: int, sweep_seconds: float) -> None:
        while not self._stop.is_set():
            # Returns early on a signal; otherwise this is the backstop sweep.
            self._wake.wait(timeout=sweep_seconds)
            if self._stop.is_set():
                break
            # Clear before pruning, so a write during the prune triggers another pass.
            self._wake.clear()
            try:
                for path in prune_oldest(folder, keep):
                    logger.debug("Screenshots cleanup: deleted %s", path)
            except OSError:
                # Worker-thread boundary: a missing folder or locked file must
                # not kill the thread; the next signal or sweep retries.
                logger.exception("Screenshots cleanup failed for %s", folder)


_pruner = ScreenshotPruner()


# ai: claude-opus-5-5 | 2026-11-06
def start(folder: str, keep: int = DEFAULT_KEEP, sweep_seconds: float = DEFAULT_SWEEP_SECONDS) -> None:
    """Start the process-wide pruner (main.py calls this once at startup)."""
    _pruner.start(folder, keep, sweep_seconds)


# ai: claude-opus-5-5 | 2026-11-06
def notify_written() -> None:
    """Tell the process-wide pruner a screenshot was written. No-op if it isn't running."""
    _pruner.notify_written()


# ai: claude-opus-5-5 | 2026-11-06
def stop(timeout: float | None = None) -> None:
    """Stop the process-wide pruner."""
    _pruner.stop(timeout)
