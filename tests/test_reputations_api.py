# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Contract tests for /api/reputations against a real Postgres schema."""
import pytest
from flask.testing import FlaskClient

from app.database.database import Database
from app.database.reputations_dao import ReputationsDAO
from tests.api_helpers import FKR_TABLE, create_fkr_faction

pytestmark = pytest.mark.db


@pytest.fixture(name="fkr_client")
def fixture_fkr_client(client: FlaskClient, db: Database) -> FlaskClient:
    create_fkr_faction(client, db, "FED", "Federation")
    return client


def test_tiers_by_table(fkr_client: FlaskClient) -> None:
    response = fkr_client.get(f"/api/reputations/by-table/{FKR_TABLE}")

    assert response.status_code == 200
    tiers = response.get_json()
    assert [t["low_limit"] for t in tiers] == sorted(t["low_limit"] for t in tiers)
    neutral = next(t for t in tiers if t["name"] == "Neutral")
    assert (neutral["low_limit"], neutral["high_limit"]) == (-499, 499)


def test_unknown_table_is_404(fkr_client: FlaskClient) -> None:
    assert fkr_client.get("/api/reputations/by-table/not_a_table").status_code == 404
    assert fkr_client.put("/api/reputations/by-table/not_a_table/1", json={"low_limit": 1}).status_code == 404


def test_all_grouped(fkr_client: FlaskClient) -> None:
    groups = fkr_client.get("/api/reputations/all").get_json()

    assert FKR_TABLE in {g["table_name"] for g in groups}


def test_update_row_round_trip(fkr_client: FlaskClient) -> None:
    tiers = fkr_client.get(f"/api/reputations/by-table/{FKR_TABLE}").get_json()
    neutral = next(t for t in tiers if t["name"] == "Neutral")
    url = f"/api/reputations/by-table/{FKR_TABLE}/{neutral['id']}"
    try:
        response = fkr_client.put(url, json={"high_limit": 498})

        assert response.status_code == 200
        updated = fkr_client.get(f"/api/reputations/by-table/{FKR_TABLE}").get_json()
        assert next(t for t in updated if t["id"] == neutral["id"])["high_limit"] == 498
    finally:
        # Tier tables persist across tests (they are seed data), so restore the row.
        fkr_client.put(url, json={"high_limit": neutral["high_limit"]})


# ai: claude-opus-5-5 | 2026-11-06
def test_update_reads_columns_of_the_active_schema(fkr_client: FlaskClient, db: Database) -> None:
    """The PUT handler must inspect the table it writes, not a same-named one in 'public'.

    The column exists only in the test schema's copy, so a lookup pinned to
    'public' (a branch copied from main, or an empty one) cannot see it.
    """
    tiers = fkr_client.get(f"/api/reputations/by-table/{FKR_TABLE}").get_json()
    with db.connect() as conn, conn.cursor() as cursor:
        cursor.execute(f'ALTER TABLE "{FKR_TABLE}" ADD COLUMN messages_count BIGINT')
    try:
        response = fkr_client.put(f"/api/reputations/by-table/{FKR_TABLE}/{tiers[0]['id']}", json={"messages_count": 7})

        assert response.status_code == 200, response.get_json()
    finally:
        with db.connect() as conn, conn.cursor() as cursor:
            cursor.execute(f'ALTER TABLE "{FKR_TABLE}" DROP COLUMN messages_count')


# ai: claude-opus-5-5 | 2026-11-06
def test_read_uses_columns_of_the_active_schema(fkr_client: FlaskClient, db: Database) -> None:
    """ReputationsDAO picks its SELECT from the columns of the table it reads, not 'public'.

    Tier rows are cached, so the cache is dropped after the out-of-band ALTER
    (a restart does the same); the reload is what inspects the columns.
    """
    dao = ReputationsDAO.get_dao_by_table_name(FKR_TABLE)
    with db.connect() as conn, conn.cursor() as cursor:
        cursor.execute(f'ALTER TABLE "{FKR_TABLE}" RENAME COLUMN high_limit TO high_limit_hidden')
    dao.invalidate_tiers()
    try:
        response = fkr_client.get(f"/api/reputations/by-table/{FKR_TABLE}")

        assert response.status_code == 200, response.get_json()
        assert {tier["high_limit"] for tier in response.get_json()} == {None}
    finally:
        with db.connect() as conn, conn.cursor() as cursor:
            cursor.execute(f'ALTER TABLE "{FKR_TABLE}" RENAME COLUMN high_limit_hidden TO high_limit')
        dao.invalidate_tiers()


def test_update_row_without_fields_is_400(fkr_client: FlaskClient) -> None:
    response = fkr_client.put(f"/api/reputations/by-table/{FKR_TABLE}/1", json={"bogus": 1})

    assert response.status_code == 400


# ai: claude-opus-5-5 | 2026-11-06
def test_update_unknown_row_is_404(fkr_client: FlaskClient) -> None:
    response = fkr_client.put(f"/api/reputations/by-table/{FKR_TABLE}/999999", json={"high_limit": 1})

    assert response.status_code == 404


def test_update_row_rejects_non_integer_limit(fkr_client: FlaskClient) -> None:
    response = fkr_client.put(f"/api/reputations/by-table/{FKR_TABLE}/1", json={"low_limit": "lots"})

    assert response.status_code == 400
