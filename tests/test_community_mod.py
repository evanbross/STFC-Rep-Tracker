# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Community-mod capture endpoint (R3): size cap, JSON Lines output, safe concurrent appends.

Runs the blueprint on a bare Flask app (no DB) with the capture file in tmp_path,
so nothing here can touch the real community-data files.
"""
import io
import json
import threading
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import EnvironBuilder

from app.views import community_mod_view

_URL = "/api/community-mod/"
_LIMIT = 200


@pytest.fixture(name="capture_file")
def fixture_capture_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "community-data.jsonl"
    monkeypatch.setattr(community_mod_view, "_CAPTURE_FILE", str(path))
    monkeypatch.setattr(community_mod_view, "max_payload_size", lambda: _LIMIT)
    return path


@pytest.fixture(name="mod_client")
def fixture_mod_client(capture_file: Path) -> FlaskClient:
    app = Flask("community_mod_test")
    app.register_blueprint(community_mod_view.community_mod_bp, url_prefix="/api/community-mod")
    return app.test_client()


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _chunked_post(client: FlaskClient, body: bytes) -> int:
    """POST without Content-Length, as a chunked upload arrives at the WSGI layer."""
    builder = EnvironBuilder(
        path=_URL, method="POST", input_stream=io.BytesIO(body), content_type="application/json",
        headers={"Transfer-Encoding": "chunked"},
        environ_overrides={"wsgi.input_terminated": True},
    )
    assert builder.content_length is None
    return client.open(builder).status_code


# ai: claude-opus-5-5 | 2026-11-06
@pytest.mark.parametrize("secret_header", ["Authorization", "Stfc-Sync-Token"])
def test_payload_is_one_json_line_without_secrets(
    mod_client: FlaskClient, capture_file: Path, secret_header: str
) -> None:
    response = mod_client.post(_URL, json=[{"rid": 1, "amount": 5}], headers={secret_header: "secret-value"})

    assert response.status_code == 200
    [record] = _lines(capture_file)
    assert record["payload"] == [{"rid": 1, "amount": 5}]
    assert {k.lower() for k in record["headers"]}.isdisjoint({secret_header.lower()})
    assert "secret-value" not in capture_file.read_text(encoding="utf-8")


def test_each_capture_is_its_own_line(mod_client: FlaskClient, capture_file: Path) -> None:
    for n in range(3):
        assert mod_client.post(_URL, json={"n": n}).status_code == 200

    assert [r["payload"]["n"] for r in _lines(capture_file)] == [0, 1, 2]


def test_declared_oversize_is_413(mod_client: FlaskClient, capture_file: Path) -> None:
    response = mod_client.post(_URL, json={"blob": "x" * _LIMIT})

    assert response.status_code == 413
    assert not capture_file.exists()


def test_chunked_oversize_is_413(mod_client: FlaskClient, capture_file: Path) -> None:
    """Regression for R3: without Content-Length the old check was skipped entirely."""
    assert _chunked_post(mod_client, json.dumps({"blob": "x" * _LIMIT}).encode()) == 413
    assert not capture_file.exists()


def test_chunked_within_limit_is_captured(mod_client: FlaskClient, capture_file: Path) -> None:
    assert _chunked_post(mod_client, b'{"small": true}') == 200
    assert _lines(capture_file)[0]["payload"] == {"small": True}


@pytest.mark.parametrize(
    ("data", "content_type"),
    [('{"a": 1}', "text/plain"), ("{not json", "application/json"), (b"\xff\xfe", "application/json")],
)
def test_non_json_is_400(mod_client: FlaskClient, capture_file: Path, data: str | bytes, content_type: str) -> None:
    assert mod_client.post(_URL, data=data, content_type=content_type).status_code == 400
    assert not capture_file.exists()


def test_concurrent_appends_stay_whole_lines(capture_file: Path) -> None:
    big = "y" * 50_000   # larger than one OS write buffer, to give interleaving a chance

    def worker(n: int) -> None:
        community_mod_view.append_capture({"n": n, "blob": big})

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(r["n"] for r in _lines(capture_file)) == list(range(16))
