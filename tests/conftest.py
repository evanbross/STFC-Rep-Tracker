# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-05
"""Shared pytest fixtures.

Database tests run against a disposable Neon branch named by DATABASE_URL_TEST.
Each pytest session creates its own empty schema in that branch (so the suite
always starts from a fresh schema, even though a Neon branch starts as a copy
of production data), points the app at it via search_path, and drops it at the
end of the run.

Safety: before anything else runs, every production URL variable is overwritten
with either the scoped test URL or an unroutable sentinel. main.py's
load_dotenv() never overrides an existing variable, so the app cannot reach the
live database from inside pytest even if a test imports main by mistake.
"""
import importlib
import os
import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg2
import pytest
from dotenv import dotenv_values
from flask import Flask
from flask.testing import FlaskClient

from app import google_calendar
from app.database import factions_dao as factions_dao_module
from app.database.database import Database

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROD_URL_VARS = ("DATABASE_URL_POOLED", "DATABASE_URL_DIRECT", "DATABASE_URL")
_BLOCKED_URL = "postgresql://blocked-by-pytest.invalid/no_database"
_SCHEMA = f"pytest_{uuid.uuid4().hex[:12]}"

# Reputation tier tables are seed data and must survive between tests, as must
# the migration bookkeeping; everything else is user data, truncated per test.
_SEEDED_TABLE_SUFFIX = "_reputations"
_PRESERVED_TABLES = frozenset({"schema_version", "reputation_seed"})  # ai: claude-opus-5-5 | 2026-11-06


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when DATABASE_URL_TEST is missing or points at the live database."""


def _direct_host(url: str) -> str:
    """Return the Neon direct-endpoint hostname for a pooled or direct URL."""
    host = urlsplit(url).hostname or ""
    return host.replace("-pooler", "")


def _direct_url(url: str, search_path: str | None = None) -> str:
    """Convert a Neon URL to its direct endpoint, optionally pinning search_path.

    The pooled (PgBouncer) endpoint rejects the libpq `options` startup
    parameter, so the scoped test URL must use the direct endpoint.
    """
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    netloc = parts.netloc.replace(hostname, _direct_host(url))
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "options"]
    if search_path:
        query.append(("options", f"-csearch_path={search_path}"))
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), ""))


def _resolve_test_url() -> str | None:
    """Return DATABASE_URL_TEST after checking it is not the live database."""
    dotenv = dotenv_values(PROJECT_ROOT / ".env")
    test_url = os.environ.get("DATABASE_URL_TEST") or dotenv.get("DATABASE_URL_TEST")
    if not test_url:
        return None

    prod_hosts = {
        _direct_host(value)
        for var in _PROD_URL_VARS
        if (value := os.environ.get(var) or dotenv.get(var))
    }
    if _direct_host(test_url) in prod_hosts:
        raise UnsafeTestDatabaseError(
            "DATABASE_URL_TEST points at the same Neon endpoint as the live "
            "database. Create a separate Neon branch for tests."
        )
    return test_url


_TEST_URL = _resolve_test_url()


def pytest_configure(config: pytest.Config) -> None:
    """Fence off the live database before any test module is imported."""
    scoped = _direct_url(_TEST_URL, search_path=_SCHEMA) if _TEST_URL else _BLOCKED_URL
    for var in _PROD_URL_VARS:
        os.environ[var] = scoped
    os.environ["DISABLE_CAPTURE"] = "1"
    os.environ["FLASK_ENV"] = "testing"


@pytest.fixture(name="flask_app", scope="session")
def fixture_flask_app() -> Iterator[Flask]:
    """The real Flask app, wired to a fresh schema in the test Neon branch."""
    if not _TEST_URL:
        pytest.skip("DATABASE_URL_TEST is not set — see .env.example (Neon test branch)")

    admin_url = _direct_url(_TEST_URL)
    with closing(psycopg2.connect(admin_url)) as conn, conn, conn.cursor() as cursor:
        cursor.execute(f'CREATE SCHEMA "{_SCHEMA}"')
    try:
        # ai: claude-opus-5-5 | 2026-11-06
        # The app is built only after pytest_configure has pointed every DB
        # URL at the scoped test schema.
        main = importlib.import_module("main")
        built_app: Flask = main.create_wsgi_app()
        built_app.config["TESTING"] = True
        yield built_app
    finally:
        with closing(psycopg2.connect(admin_url)) as conn, conn, conn.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{_SCHEMA}" CASCADE')


@pytest.fixture(name="db")
def fixture_db(flask_app: Flask, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    """The app's Database, with user-data tables emptied before each test."""
    database: Database = flask_app.config["DATABASE"]
    # Territory endpoints annotate results from Google Calendar when a token
    # exists on disk; tests must never make live Google API calls.
    monkeypatch.setattr(google_calendar, "is_authenticated", lambda: False)

    with database.connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
        )
        tables = [
            r[0] for r in cursor.fetchall()
            if not r[0].endswith(_SEEDED_TABLE_SUFFIX) and r[0] not in _PRESERVED_TABLES
        ]
        if tables:
            quoted = ", ".join(f'"{t}"' for t in tables)
            cursor.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
    yield database


@pytest.fixture(name="client")
def fixture_client(flask_app: Flask, db: Database) -> FlaskClient:
    """Flask test client; depends on db so every API test starts from empty tables."""
    return flask_app.test_client()


# ai: claude-opus-5-5 | 2026-11-06
@pytest.fixture(name="test_branch_url")
def fixture_test_branch_url() -> str:
    """Direct URL of the Neon test branch with no search_path pinned (its public schema
    is a copy of production)."""
    if not _TEST_URL:
        pytest.skip("DATABASE_URL_TEST is not set — see .env.example (Neon test branch)")
    return _direct_url(_TEST_URL)


# ai: claude-opus-5-5 | 2026-11-06
@pytest.fixture(name="scratch_schema")
def fixture_scratch_schema(test_branch_url: str) -> Iterator[str]:
    """URL scoped to a brand-new empty schema, dropped afterwards (for migrating from version 0)."""
    schema = f"pytest_scratch_{uuid.uuid4().hex[:10]}"
    with closing(psycopg2.connect(test_branch_url)) as conn, conn, conn.cursor() as cursor:
        cursor.execute(f'CREATE SCHEMA "{schema}"')
    try:
        yield _direct_url(_TEST_URL, search_path=schema)
    finally:
        with closing(psycopg2.connect(test_branch_url)) as conn, conn, conn.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture(name="fixed_avg_window")
def fixture_fixed_avg_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the summary's averaging window use its code default, not settings.yaml."""
    monkeypatch.setattr(
        factions_dao_module, "capture_cfg", lambda *keys, default=None: default
    )
