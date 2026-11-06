# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""One automation at a time (N-S1): an overlapping capture request gets 409.

The capture blueprint imports Windows-only packages, so this module is skipped
where they are missing. Orchestrators are replaced with fakes: nothing here
touches the game window or the database.
"""
import threading

import pytest
from flask import Flask
from flask.testing import FlaskClient

pytest.importorskip("pyautogui", reason="capture blueprint needs the Windows automation packages")

from app.views import capture_screen_view  # noqa: E402  (after the importorskip guard)

_WAIT_SECONDS = 10


class _BlockingGifts:
    """Stands in for GiftsOrchestrator (built with no args); capture_gifts() waits until released."""

    started = threading.Event()
    release = threading.Event()

    def capture_gifts(self) -> dict:
        _BlockingGifts.started.set()
        if not _BlockingGifts.release.wait(_WAIT_SECONDS):
            raise TimeoutError("test never released the fake capture")
        return {"claimed": 1}


class _ExplodingGifts:
    """Fails inside the capture itself, after construction succeeded."""

    calls = 0

    def capture_gifts(self) -> dict:
        _ExplodingGifts.calls += 1
        raise RuntimeError("window vanished")


@pytest.fixture(name="capture_client")
def fixture_capture_client() -> FlaskClient:
    app = Flask("capture_lock_test")
    app.config["DATABASE"] = object()
    app.register_blueprint(capture_screen_view.capture_bp, url_prefix="/api/capture-screen")
    return app.test_client()


def test_overlapping_capture_is_409(capture_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_screen_view, "GiftsOrchestrator", _BlockingGifts)
    _BlockingGifts.started.clear()
    _BlockingGifts.release.clear()
    first: dict = {}

    def run_first() -> None:
        first["response"] = capture_client.post("/api/capture-screen/gifts")

    worker = threading.Thread(target=run_first)
    worker.start()
    try:
        assert _BlockingGifts.started.wait(_WAIT_SECONDS)

        second = capture_client.post("/api/capture-screen/gifts")
        identify = capture_client.post("/api/capture-screen/identify-faction")

        assert second.status_code == 409
        assert second.get_json() == {"error": capture_screen_view.AUTOMATION_BUSY_MESSAGE, "busy": True}
        assert identify.status_code == 409
    finally:
        _BlockingGifts.release.set()
        worker.join(_WAIT_SECONDS)

    assert first["response"].status_code == 200


def test_lock_is_released_after_a_failure(capture_client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_screen_view, "GiftsOrchestrator", _ExplodingGifts)
    _ExplodingGifts.calls = 0

    assert capture_client.post("/api/capture-screen/gifts").status_code == 500
    # A held lock would turn this second attempt into a 409 before reaching the fake.
    assert capture_client.post("/api/capture-screen/gifts").status_code == 500
    assert _ExplodingGifts.calls == 2
