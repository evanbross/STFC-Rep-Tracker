# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Windows process bootstrap shared by launcher.py and main.py (N-O2).

Elevation checks, relaunch-as-admin, and named-mutex single-instance locks.
A leaf module (stdlib only), so the launcher can import it without pulling in
Flask or the database layer.
"""
import ctypes
import os
import sys

_ERROR_ALREADY_EXISTS = 183


def is_admin() -> bool:
    """True if this process is elevated. False off Windows or if the check itself fails."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        # AttributeError: no ctypes.windll (not Windows). OSError: the shell32 call failed.
        return False


class SingleInstanceLock:
    """A named Windows mutex held for the life of the process.

    ``acquire()`` returns False if another process already holds the name.
    If the mutex can't be created at all, it fails open (returns True), so a
    broken API never blocks startup.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._handle: int | None = None

    def acquire(self) -> bool:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            return True
        self._handle = handle
        return kernel32.GetLastError() != _ERROR_ALREADY_EXISTS

    def release(self) -> None:
        """Close this process's handle; the mutex disappears with its last handle."""
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def relaunch_as_admin(lock: SingleInstanceLock | None = None) -> None:
    """Start this script again elevated (UAC prompt), forwarding argv, then exit.

    Pass the lock this process holds, if any: it is released before the
    elevated child starts, so the child never finds it still held by this
    exiting parent (N-P4).
    """
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    if lock is not None:
        lock.release()
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    sys.exit(0)
