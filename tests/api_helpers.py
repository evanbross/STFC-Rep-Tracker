# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Small helpers shared by the API contract tests."""
from datetime import datetime, timedelta, UTC

from flask.testing import FlaskClient

from app.database.database import Database

FKR_TABLE = "fkr_reputations"
FKR_DAO = "FKRReputationsDAO"


def create_faction(
    client: FlaskClient,
    code: str,
    name: str,
    reputation_table_name: str | None = None,
    reputation_dao_name: str | None = None,
    display_order: int = 1,
) -> dict:
    """POST a faction and return the response JSON, asserting it was created."""
    response = client.post(
        "/api/factions/",
        json={
            "code": code,
            "name": name,
            "color": "#123456",
            "display_order": display_order,
            "reputation_table_name": reputation_table_name,
            "reputation_dao_name": reputation_dao_name,
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()


# ai: claude-opus-5-5 | 2026-11-06
def create_fkr_faction(client: FlaskClient, code: str, name: str) -> dict:
    """Create a faction backed by the FKR tier table.

    No restart or init_database is needed: every reputation implementation is
    registered at startup (R5), so the tier lookup works immediately.
    """
    return create_faction(client, code, name, FKR_TABLE, FKR_DAO)


def insert_entries(db: Database, faction_code: str, values_by_minute: dict[int, int]) -> None:
    """Insert status entries at fixed minute offsets so rate maths is deterministic."""
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    with db.connect() as conn, conn.cursor() as cursor:
        for minute, value in values_by_minute.items():
            cursor.execute(
                "INSERT INTO status_entries (faction_code, timestamp, value) VALUES (%s, %s, %s)",
                (faction_code, (base + timedelta(minutes=minute)).isoformat(), value),
            )
