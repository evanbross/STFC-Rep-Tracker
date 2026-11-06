# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""_run_capture maps exception types to status codes, never message text (N-O5).

Orchestrators are replaced with fakes that raise, so nothing here touches the
game window or the database. The capture blueprint imports Windows-only
packages, so this module is skipped where they are missing.
"""
import pytest
from flask import Flask
from flask.testing import FlaskClient

pytest.importorskip("pyautogui", reason="capture blueprint needs the Windows automation packages")

from app.domain_errors import NotFoundError  # noqa: E402  (after the importorskip guard)
from app.screen_processing.capture_errors import (  # noqa: E402
    CaptureError,
    CaptureRequestError,
    CaptureTargetNotFound,
    GameWindowNotFound,
)
from app.screen_processing.process_event_rewards import EventRewardsOrchestrator  # noqa: E402
from app.views import capture_screen_view  # noqa: E402
from app.views.validation import register_error_handlers  # noqa: E402


class _RaisingGifts:
    """Stands in for GiftsOrchestrator; capture_gifts() raises whatever the test sets."""

    error: BaseException = RuntimeError()

    def capture_gifts(self) -> dict:
        raise _RaisingGifts.error


@pytest.fixture(name="capture_client")
def fixture_capture_client(monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    monkeypatch.setattr(capture_screen_view, "GiftsOrchestrator", _RaisingGifts)
    app = Flask("capture_errors_test")
    app.config["DATABASE"] = object()
    register_error_handlers(app)
    app.register_blueprint(capture_screen_view.capture_bp, url_prefix="/api/capture-screen")
    return app.test_client()


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (GameWindowNotFound(), 404),
        (CaptureTargetNotFound("Gifts button not visible on home screen"), 404),
        # Worded with "not found" on purpose: the old code sniffed that phrase into a 404.
        (CaptureError("Gifts screen not found after 8 attempts"), 500),
        (CaptureRequestError("Crop region is empty"), 400),
        (NotFoundError("Faction 'XYZ' not found"), 404),
    ],
)
def test_expected_errors_keep_their_message_and_status(
    capture_client: FlaskClient, error: Exception, status: int
) -> None:
    _RaisingGifts.error = error

    response = capture_client.post("/api/capture-screen/gifts")

    assert response.status_code == status
    assert response.get_json() == {"error": str(error)}


def test_unexpected_errors_hide_their_text(capture_client: FlaskClient) -> None:
    _RaisingGifts.error = KeyError("C:\\secret\\path not found")

    response = capture_client.post("/api/capture-screen/gifts")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Gifts capture failed"}


def test_placeholder_capture_is_501(capture_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Skip BaseOrchestrator.__init__ so no ScreenCapture (and no window lookup) is built.
    monkeypatch.setattr(capture_screen_view, "EventRewardsOrchestrator", lambda: EventRewardsOrchestrator.__new__(EventRewardsOrchestrator))

    response = capture_client.post("/api/capture-screen/event-rewards")

    assert response.status_code == 501
    assert "not implemented" in response.get_json()["error"]


def test_lock_is_released_after_a_domain_error(capture_client: FlaskClient) -> None:
    _RaisingGifts.error = NotFoundError("gone")

    assert capture_client.post("/api/capture-screen/gifts").status_code == 404
    assert capture_client.post("/api/capture-screen/gifts").status_code == 404
