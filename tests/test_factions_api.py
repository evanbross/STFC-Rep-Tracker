# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Contract tests for /api/factions against a real Postgres schema."""
import pytest
from flask.testing import FlaskClient

from app.database import factions_dao as factions_dao_module
from app.database.database import Database
from tests.api_helpers import FKR_TABLE, create_faction, create_fkr_faction, insert_entries

pytestmark = pytest.mark.db


def test_create_and_list(client: FlaskClient) -> None:
    created = create_faction(client, "FED", "Federation")

    assert created["code"] == "FED"
    assert created["id"] == "FED"
    listed = client.get("/api/factions/").get_json()
    assert [f["code"] for f in listed] == ["FED"]
    assert listed[0]["selected_snippets"] == []


def test_create_requires_name_and_code(client: FlaskClient) -> None:
    response = client.post("/api/factions/", json={"name": "No Code"})

    assert response.status_code == 400


def test_rename_code_cascades_to_status_entries(client: FlaskClient) -> None:
    create_faction(client, "ROM", "Romulan")
    assert client.post("/api/status_entries/", json={"faction": "Romulan", "value": 42}).status_code == 201

    response = client.put("/api/factions/ROM", json={"code": "RSE", "name": "Romulan"})

    assert response.status_code == 200
    entries = client.get("/api/status_entries/Romulan").get_json()
    assert [e["faction_code"] for e in entries] == ["RSE"]


def test_update_unknown_faction_is_404(client: FlaskClient) -> None:
    response = client.put("/api/factions/NOPE", json={"code": "NOPE", "name": "Nobody"})

    assert response.status_code == 404


def test_duplicate_create_is_409(client: FlaskClient) -> None:
    create_faction(client, "KLI", "Klingon")

    response = client.post("/api/factions/", json={"code": "KLI", "name": "Klingon"})

    assert response.status_code == 409


def test_duplicate_update_is_409(client: FlaskClient) -> None:
    create_faction(client, "KLI", "Klingon")
    create_faction(client, "ROM", "Romulan", display_order=2)

    response = client.put("/api/factions/ROM", json={"code": "KLI", "name": "Romulan"})

    assert response.status_code == 409


def test_selected_snippets_empty_for_new_faction(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    response = client.get("/api/factions/FED/selected-snippets")

    assert response.status_code == 200
    assert response.get_json() == []


@pytest.mark.usefixtures("fixed_avg_window")
def test_summary_numbers(client: FlaskClient, db: Database) -> None:
    create_fkr_faction(client, "FED", "Federation")
    # 1000 → 2000 → 4000 over 20 minutes: last step +2000 in 10 min (200/min),
    # averaged over the window +3000 in 20 min (150/min).
    insert_entries(db, "FED", {0: 1000, 10: 2000, 20: 4000})

    [summary] = client.get("/api/factions/summary").get_json()

    assert summary["current_value"] == 4000
    assert summary["last_delta"] == 2000
    assert summary["entry_count"] == 3
    assert summary["rep_level"] == "Tolerated"            # FKR tier 500..4999
    status = summary["status"]
    assert status["raw_value_delta_per_minute"] == pytest.approx(200.0)
    assert status["avg_value_delta_per_minute"] == pytest.approx(150.0)
    assert status["next_rep_level"] == "Neighbor"
    assert status["goal_value"] == 5000
    assert status["minutes_to_goal"] == pytest.approx(6.66)   # (4999 - 4000) / 150


# ai: claude-opus-5-5 | 2026-11-06
@pytest.mark.usefixtures("fixed_avg_window")
def test_summary_sees_tier_edit_without_restart(client: FlaskClient, db: Database) -> None:
    """Tier rows are cached in memory; a tier PUT must refresh what the summary reads."""
    create_fkr_faction(client, "FED", "Federation")
    insert_entries(db, "FED", {0: 1000, 10: 2000, 20: 4000})
    tiers = client.get(f"/api/reputations/by-table/{FKR_TABLE}").get_json()
    tolerated = next(t for t in tiers if t["name"] == "Tolerated")
    url = f"/api/reputations/by-table/{FKR_TABLE}/{tolerated['id']}"
    try:
        assert client.put(url, json={"high_limit": 4150}).status_code == 200

        [summary] = client.get("/api/factions/summary").get_json()

        assert summary["status"]["minutes_to_goal"] == pytest.approx(1.0)   # (4150 - 4000) / 150
    finally:
        client.put(url, json={"high_limit": tolerated["high_limit"]})


# ai: claude-opus-5-5 | 2026-11-06
def test_summary_limits_average_window_per_faction(client: FlaskClient, db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each faction averages over its own newest N entries, while entry_count covers all of them."""
    monkeypatch.setattr(factions_dao_module, "capture_cfg", lambda *keys, default=None: 2)
    create_faction(client, "AAA", "Alpha", display_order=1)
    create_faction(client, "BBB", "Bravo", display_order=2)
    insert_entries(db, "AAA", {0: 0, 10: 100, 20: 400})       # newest two: +300 in 10 min
    insert_entries(db, "BBB", {0: 0, 5: 50})

    alpha, bravo = client.get("/api/factions/summary?sort=display_order").get_json()

    assert (alpha["entry_count"], alpha["current_value"]) == (3, 400)
    assert alpha["status"]["avg_value_delta_per_minute"] == pytest.approx(30.0)
    assert (bravo["entry_count"], bravo["current_value"], bravo["last_delta"]) == (2, 50, 50)


def test_summary_without_entries(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    [summary] = client.get("/api/factions/summary").get_json()

    assert summary["current_value"] == 0
    assert summary["last_updated"] is None
    assert summary["rep_level"] == "Unknown"


def test_summary_sort_descending(client: FlaskClient, db: Database) -> None:
    create_faction(client, "AAA", "Alpha", display_order=1)
    create_faction(client, "BBB", "Bravo", display_order=2)
    insert_entries(db, "AAA", {0: 10})
    insert_entries(db, "BBB", {0: 99})

    summary = client.get("/api/factions/summary?sort=-current_value").get_json()

    assert [s["code"] for s in summary] == ["BBB", "AAA"]


# ai: claude-opus-5-5 | 2026-11-06
@pytest.mark.parametrize(("sent", "stored"), [("", None), ("3", 3), (4, 4), (None, None)])
def test_display_order_accepts_form_values(client: FlaskClient, sent: object, stored: int | None) -> None:
    """The Factions form sends display_order as raw input text ('' when blank)."""
    response = client.post("/api/factions/", json={"code": "FED", "name": "Federation", "display_order": sent})

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["display_order"] == stored


def test_invalid_body_lists_fields_without_echoing_input(client: FlaskClient) -> None:
    response = client.post("/api/factions/", json={"code": "FED", "name": "Federation", "on_chart": "secret-ish"})

    assert response.status_code == 400
    body = response.get_json()
    assert [f["field"] for f in body["fields"]] == ["on_chart"]
    assert "secret-ish" not in response.get_data(as_text=True)


def test_unexpected_error_is_500_without_details(
    client: FlaskClient, db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_args: object) -> None:
        raise RuntimeError("password=hunter2 at /srv/internal/path")

    monkeypatch.setattr(db.factions, "add_faction", explode)

    response = client.post("/api/factions/", json={"code": "FED", "name": "Federation"})

    assert response.status_code == 500
    assert response.get_json() == {"error": "Unexpected server error"}


# ai: claude-opus-5-5 | 2026-11-06
def test_reputation_type_change_applies_without_restart(client: FlaskClient, db: Database) -> None:
    """R5: a faction created, then switched to another tier table, resolves its DAO immediately."""
    create_faction(client, "NEW", "Newcomer")
    insert_entries(db, "NEW", {0: 100, 10: 300})
    assert client.get("/api/factions/summary").get_json()[0]["rep_level"] == "Unknown"

    body = {"code": "NEW", "name": "Newcomer", "reputation_table_name": "augment_reputations"}
    assert client.put("/api/factions/NEW", json=body).status_code == 200

    [summary] = client.get("/api/factions/summary").get_json()
    assert summary["rep_level"] == "Servant"                 # Augment tier 250..2499


# ai: claude-opus-5-5 | 2026-11-06
def test_dao_name_is_filled_from_the_table(client: FlaskClient) -> None:
    created = create_faction(client, "AUG", "Augment", reputation_table_name="augment_reputations")

    assert created["reputation_dao_name"] == "AugmentReputationsDAO"


# ai: claude-opus-5-5 | 2026-11-06
@pytest.mark.parametrize(
    "fields",
    [
        {"reputation_table_name": "no_such_reputations"},
        {"reputation_table_name": "fkr_reputations", "reputation_dao_name": "AugmentReputationsDAO"},
        {"reputation_dao_name": "FKRReputationsDAO"},
        {"reputation_table_name": "factions"},              # a real table, but not a tier implementation
    ],
)
def test_unknown_or_mismatched_reputation_type_is_400(client: FlaskClient, fields: dict) -> None:
    response = client.post("/api/factions/", json={"code": "BAD", "name": "Bad", **fields})

    assert response.status_code == 400
    assert response.get_json()["fields"]


# ai: claude-opus-5-5 | 2026-11-06
def test_blank_reputation_type_from_the_form_means_none(client: FlaskClient) -> None:
    response = client.post(
        "/api/factions/", json={"code": "NON", "name": "None", "reputation_table_name": "", "reputation_dao_name": ""}
    )

    assert response.status_code == 201
    assert response.get_json()["reputation_table_name"] is None


# ai: claude-opus-5-5 | 2026-11-06
def test_missing_unselected_snippet_gets_the_default_name(client: FlaskClient) -> None:
    """The startup UPDATE that used to backfill this now applies on write."""
    assert create_faction(client, "FED", "Federation")["snippet_unselected"] == "RepButtonFed.jpg"


# ai: claude-opus-5-5 | 2026-11-06
def test_reputation_types_endpoint_lists_every_implementation(client: FlaskClient) -> None:
    types = client.get("/api/reputations/types").get_json()

    assert {"table_name": "fkr_reputations", "dao_name": "FKRReputationsDAO"} in types
    assert len(types) == len({t["table_name"] for t in types}) >= 8
