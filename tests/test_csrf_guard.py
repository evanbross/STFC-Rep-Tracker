# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Cross-origin write protection (R2). The guard itself lands in Phase 2."""
import pytest
from flask.testing import FlaskClient

from tests.api_helpers import create_faction

pytestmark = pytest.mark.db


@pytest.mark.xfail(strict=True, reason="R2: no Origin-check before_request guard yet (Phase 2)")
def test_cross_origin_write_is_rejected(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    # A text/plain body is what a hostile page can send without a CORS preflight.
    response = client.post(
        "/api/status_entries/",
        data='{"faction": "Federation", "value": 1}',
        content_type="text/plain",
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403


def test_same_origin_write_is_allowed(client: FlaskClient) -> None:
    create_faction(client, "FED", "Federation")

    response = client.post(
        "/api/status_entries/",
        json={"faction": "Federation", "value": 1},
        headers={"Origin": "http://localhost"},
    )

    assert response.status_code == 201
