# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Expected capture failures, mapped to HTTP status by type (N-O5).

Orchestrators raise these instead of returning ``{"error": ...}`` dicts, and
``capture_screen_view._run_capture`` maps the class to a status code, so
rewording a message can never change a status. Messages are written for the
user (they explain what to fix in the game or in settings.yaml) and must never
carry exception text from a library. Leaf module.
"""


class CaptureError(RuntimeError):
    """The game wasn't in a state the capture could work with (HTTP 500)."""

    status_code: int = 500


class CaptureTargetNotFound(CaptureError):
    """A button, dialog, or screen the capture needed was not on screen (HTTP 404)."""

    status_code = 404


class GameWindowNotFound(CaptureTargetNotFound):
    """No STFC window is open (HTTP 404)."""

    def __init__(self, message: str = "STFC window not found") -> None:
        super().__init__(message)


class CaptureRequestError(CaptureError):
    """The request can't be served as asked, e.g. a crop before any screenshot (HTTP 400)."""

    status_code = 400
