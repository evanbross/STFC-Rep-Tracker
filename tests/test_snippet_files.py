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
from app.views import factions_view, snippet_files
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
    assert body == {"id": body["id"], "faction_code": "FED", "filename": "Selected-button-FED-1.png",
                    "snippet_type": "button"}
    assert (user / "Selected-button-FED-1.png").read_bytes() == _PNG
    assert not (bundled / "Selected-button-FED-1.png").exists()
    assert _rows(client) == [
        {"id": body["id"], "filename": "Selected-button-FED-1.png", "snippet_type": "button", "uploaded": True}
    ]
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

    def _fail(*_args: object, **_kwargs: object) -> int:
        raise psycopg2.OperationalError("connection lost")

    monkeypatch.setattr(db.selected_snippets, "add_snippet", _fail)

    assert _upload(client).status_code == 500
    assert list(user.iterdir()) == []


# ai: claude-opus-5-5 | 2026-11-18
@pytest.mark.parametrize(
    ("upload_name", "content"),
    [("upload.png", b"just some text"), ("upload.png", b"\xff\xd8\xff\xe0jpeg"), ("upload.jpg", _PNG)],
)
def test_content_that_does_not_match_the_extension_is_400(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None, upload_name: str, content: bytes
) -> None:
    user, _ = split_snippets

    response = client.post(
        _UPLOAD_URL, data={"file": (BytesIO(content), upload_name)}, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert list(user.iterdir()) == []
    assert _rows(client) == []


def test_oversized_upload_is_413_and_writes_nothing(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _ = split_snippets
    monkeypatch.setattr(factions_view, "MAX_SNIPPET_BYTES", len(_PNG) - 1)

    response = _upload(client)

    assert response.status_code == 413
    assert "MB" in response.get_json()["error"]
    assert list(user.iterdir()) == []


@pytest.mark.parametrize(
    ("name", "data", "expected"),
    [
        ("a.png", _PNG, True),
        ("a.PNG", _PNG, True),
        ("a.jpg", b"\xff\xd8\xff\xdb", True),
        ("a.jpeg", b"\xff\xd8\xff\xe1", True),
        ("a.jpg", _PNG, False),
        ("a.png", b"", False),
        ("a.zip", b"PK\x03\x04", False),
    ],
)
def test_content_matches_extension(name: str, data: bytes, expected: bool) -> None:
    assert snippet_files.content_matches_extension(name, data) is expected


# ai: claude-opus-5-5 | 2026-11-18
# ── delete: DELETE /api/factions/selected-snippets/<id> ──────────────────────

def _delete(client: FlaskClient, snippet_id: int) -> TestResponse:
    return client.delete(f"/api/factions/selected-snippets/{snippet_id}")


def test_delete_removes_an_uploaded_file_so_the_name_can_be_reused(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None
) -> None:
    """Before, the file outlived its row and every re-upload of the name was a 409."""
    user, _ = split_snippets
    snippet_id = _upload(client).get_json()["id"]

    response = _delete(client, snippet_id)

    assert response.status_code == 200
    assert response.get_json() == {"deleted": snippet_id, "file_removed": True}
    assert _rows(client) == []
    assert not (user / "upload.png").exists()
    assert _upload(client).status_code == 201
    assert _delete(client, snippet_id).status_code == 404


def test_delete_keeps_a_file_another_row_still_uses(
    client: FlaskClient, db: Database, split_snippets: tuple[Path, Path], fed: None
) -> None:
    user, _ = split_snippets
    snippet_id = _upload(client).get_json()["id"]
    db.selected_snippets.add_snippet("FED", "upload.png", "desc", uploaded=True)

    assert _delete(client, snippet_id).get_json()["file_removed"] is False
    assert (user / "upload.png").is_file()


def test_delete_keeps_a_file_a_faction_column_names(
    client: FlaskClient, split_snippets: tuple[Path, Path], fed: None
) -> None:
    user, _ = split_snippets
    snippet_id = _upload(client).get_json()["id"]
    put = client.put("/api/factions/FED", json={"name": "Federation", "code": "FED", "snippet_unselected": "upload.png"})
    assert put.status_code == 200

    assert _delete(client, snippet_id).get_json()["file_removed"] is False
    assert (user / "upload.png").is_file()


def test_delete_never_removes_a_file_that_was_not_uploaded(
    client: FlaskClient, db: Database, split_snippets: tuple[Path, Path], fed: None
) -> None:
    """Rows from before v6 (some seeded from bundled images) keep their files."""
    user, bundled = split_snippets
    (user / "legacy.png").write_bytes(_PNG)
    legacy_id = db.selected_snippets.add_snippet("FED", "legacy.png", "button")
    bundled_id = db.selected_snippets.add_snippet("FED", "Selected-Desc-FED.png", "desc")

    assert _delete(client, legacy_id).get_json()["file_removed"] is False
    assert _delete(client, bundled_id).get_json()["file_removed"] is False
    assert (user / "legacy.png").is_file()
    assert (bundled / "Selected-Desc-FED.png").is_file()
