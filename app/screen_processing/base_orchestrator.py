# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Shared base for the capture orchestrators (N-O5)."""
from typing import Any

from app.screen_processing.screen_capture import ScreenCapture


class BaseOrchestrator:
    """Holds the ScreenCapture singleton and finds the game window.

    Subclasses raise the exceptions in capture_errors on failure and return
    only success payloads; capture_screen_view._run_capture turns the
    exceptions into status codes.
    """

    def __init__(self) -> None:
        self.sc = ScreenCapture()

    def _activate(self) -> Any:
        """Bring the STFC window to the front and return it.

        Raises GameWindowNotFound if the game isn't running.
        """
        return self.sc.get_and_activate_window()
