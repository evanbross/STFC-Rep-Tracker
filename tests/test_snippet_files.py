# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Snippet image routes serve images only (N-X2), and uploads land in the user folder (N-T5).

Both use temp snippet folders, never the real app/screen_snippets.
"""
from io import BytesIO
from pathlib import Path

import psycopg2
import pytest
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from app import snippet_store
from app.database.database import Database
from app.views import snippet_files
from tests.api_helpers import create_faction

pytestmark = pytest.mark.db

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture(name="snippets")
def fixture_snippets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "snippets"
    (root / "target_samples").mkdir(parents=True)
    (root / "Selected-Desc-FED.png").write_bytes(_PNG)
    (root / "target_samples" / "Sol_scout.png").write_bytes(_PNG)
    (root / "favicon.zip").write_bytes(b"PK\x03\x04")
    (tmp_path / "outside.png").write_bytes(_PNG)
    monkeypatch.setattr(snippet_store, "_configured_dir", lambda: str(root))
    return root


@pytest.mark.parametrize(
    "url",
    ["/api/factions/snippet-image/Selected-Desc-FED.png", "/api/target-types/sample-image/target_samples/Sol_scout.png"],
)
def test_images_are_served(client: FlaskClient, snippets: Path, url: str) -> None:
    response = client.get(url)

    assert response.status_code == 200
    assert response.data == _PNG


@pytest.mark.parametrize(
    "url",
    [
        "/api/factions/snippet-image/favicon.zip",
        "/api/target-types/sample-image/favicon.zip",
        "/api/factions/snippet-image/../outside.png",
        "/api/factions/snippet-image/missing.png",
    ],
)
def test_non_images_and_escapes_are_404(client: FlaskClient, snippets: Path, url: str) -> None:
    assert client.get(url).status_code == 404


@pytest.mark.parametrize(("name", "expected"), [("a.PNG", True), ("a.jpeg", True), ("a.zip", False), ("png", False)])
def test_is_snippet_image(name: str, expected: bool) -> None:
    assert snippet_files.is_snippet_image(name) is expected


# ai: claude-opus-5-5 | 2026-11-10
# ── upload: POST /api/factions/<code>/selected-snippets (N-T5) ────────────────

_UPLOAD_URL = "/api/factions/FED/selected-snippets"


@pytest.fixture(name="split_snippets")
def fixture_split_snippets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Frozen-build layout: uploads must land in the user folder, never the bundled one."""
    user, bundled = tmp_path / "user", tmp_path / "bundled"
    user.mkdir()
    bundled.mkdir()
    (bundled / "Selected-Desc-FED.png").write_bytes(_PNG)
    monkeypatch.setattr(snippet_store, "user_snippets_dir", lambda: str(user))
    monkeypatch.setattr(snippet_store, "bundled_snippets_dir", lambda: str(bundled))
    return user, bundled


@pytest.fixture(name="fed")
def fixture_fed(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")


def _upload(client: FlaskClient, url: str = _UPLOAD_URL, upload_name: str = "upload.png", **form: str) -> TestResponse:
    data: dict[str, object] = {"file": (BytesIO(_PNG), upload_name), **form}
    return client.post(url, data=data, content_type="multipart/form-data")


def _rows(client: FlaskClient) -> list[dict]:
    return client.get(_UPLOAD_URL).get_json()


def test_upload_saves_to_the_user_folder_and_registers_it(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None
) -> None:
    user, bundled = split_snippets

    response = _upload(client, filename="Selected-button-FED-1.png", snippet_type="button")

    assert response.status_code == 201
    body = response.get_json()
    assert body == {"id": body["id"], "faction_id": "FED", "filename": "Selected-button-FED-1.png",
                    "snippet_type": "button"}
    assert (user / "Selected-button-FED-1.png").read_bytes() == _PNG
    assert not (bundled / "Selected-button-FED-1.png").exists()
    assert _rows(client) == [{"id": body["id"], "filename": "Selected-button-FED-1.png", "snippet_type": "button"}]
    assert client.get("/api/factions/snippet-image/Selected-button-FED-1.png").data == _PNG


def test_upload_falls_back_to_the_file_name_and_null_type(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None
) -> None:
    user, _ = split_snippets

    response = _upload(client, upload_name="from-disk.png")

    assert response.status_code == 201
    assert response.get_json()["snippet_type"] is None
    assert (user / "from-disk.png").is_file()


def test_upload_name_cannot_escape_the_user_folder(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None
) -> None:
    user, _ = split_snippets

    response = _upload(client, filename="../../escaped.png")

    assert response.status_code == 201
    assert response.get_json()["filename"] == "escaped.png"
    assert (user / "escaped.png").is_file()
    assert not (user.parent / "escaped.png").exists()


@pytest.mark.parametrize("name", ["Selected-Desc-FED.png", "upload.png"])
def test_name_already_used_is_a_conflict(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None, name: str
) -> None:
    """Covers both folders: a bundled name would otherwise be shadowed by the upload."""
    user, _ = split_snippets
    (user / "upload.png").write_bytes(b"original")

    response = _upload(client, filename=name)

    assert response.status_code == 409
    assert (user / "upload.png").read_bytes() == b"original"
    assert not (user / "Selected-Desc-FED.png").exists()
    assert _rows(client) == []


@pytest.mark.parametrize(
    ("form", "upload_name"),
    [
        ({"filename": "notes.txt"}, "upload.png"),
        ({"snippet_type": "banner"}, "upload.png"),
        ({}, "noextension"),
    ],
)
def test_bad_uploads_are_400_and_write_nothing(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None, form: dict[str, str], upload_name: str
) -> None:
    user, _ = split_snippets

    response = _upload(client, upload_name=upload_name, **form)

    assert response.status_code == 400
    assert list(user.iterdir()) == []
    assert _rows(client) == []


def test_missing_file_is_400(client: FlaskClient, split_snippets: tuple[Path, Path], fed: None) -> None:
    response = client.post(_UPLOAD_URL, data={"filename": "x.png"}, content_type="multipart/form-data")

    assert response.status_code == 400


def test_unknown_faction_is_404_and_writes_nothing(client: FlaskClient, split_snippets: tuple[Path, Path]) -> None:
    user, _ = split_snippets

    response = _upload(client, url="/api/factions/NOPE/selected-snippets")

    assert response.status_code == 404
    assert list(user.iterdir()) == []


def test_failed_insert_removes_the_saved_file(
    client: FlaskClient, db: Database, split_snippets: tuple[Path, Path], fed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the cleanup, the orphaned file turns every retry into a 409."""
    user, _ = split_snippets

    def _fail(*_args: object) -> int:
        raise psycopg2.OperationalError("connection lost")

    monkeypatch.setattr(db.selected_snippets, "add_snippet", _fail)

    assert _upload(client).status_code == 500
    assert list(user.iterdir()) == []


def test_delete_removes_the_row_but_keeps_the_file(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None
) -> None:
    """The Factions page promises "The image file is kept." on delete."""
    user, _ = split_snippets
    snippet_id = _upload(client).get_json()["id"]

    assert client.delete(f"/api/factions/selected-snippets/{snippet_id}").status_code == 200
    assert client.delete(f"/api/factions/selected-snippets/{snippet_id}").status_code == 404
    assert _rows(client) == []
    assert (user / "upload.png").is_file()
