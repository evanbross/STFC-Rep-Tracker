# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Startup settings (R1, N-X3): typed env parsing and the production secret rule."""
import pytest

from config import DEV_SECRET_KEY, SettingsError, load_settings

_REAL_KEY = "k3Y-" + "x" * 28
_ENV_VARS = (
    "FLASK_ENV", "SECRET_KEY", "DATABASE_URL_POOLED", "DATABASE_URL_DIRECT", "DATABASE_URL",
    "CADDY_APP_NAME", "CORS_ORIGINS", "PORT", "DISABLE_CAPTURE",
)


@pytest.fixture(name="env")
def fixture_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Start every test from an empty settings environment."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_production_secret_reaches_flask_config(env: pytest.MonkeyPatch) -> None:
    """Regression for R1: the old @property put a descriptor, not the key, in app.config."""
    env.setenv("FLASK_ENV", "production")
    env.setenv("SECRET_KEY", _REAL_KEY)

    config = load_settings().flask_config()

    assert config["SECRET_KEY"] == _REAL_KEY
    assert (config["DEBUG"], config["TESTING"]) == (False, False)


@pytest.mark.parametrize("secret", [None, "", "change-me-in-production", DEV_SECRET_KEY, "Secret", "short-but-real"])
def test_production_rejects_missing_placeholder_or_short_secret(env: pytest.MonkeyPatch, secret: str | None) -> None:
    env.setenv("FLASK_ENV", "production")
    if secret is not None:
        env.setenv("SECRET_KEY", secret)

    with pytest.raises(SettingsError, match="SECRET_KEY"):
        load_settings()


def test_development_falls_back_to_dev_secret(env: pytest.MonkeyPatch) -> None:
    config = load_settings().flask_config()

    assert config["SECRET_KEY"] == DEV_SECRET_KEY
    assert config["DEBUG"] is True


def test_errors_never_include_values(env: pytest.MonkeyPatch) -> None:
    env.setenv("FLASK_ENV", "production")
    env.setenv("SECRET_KEY", "change-me-in-production")
    env.setenv("DATABASE_URL_POOLED", "postgresql://u:pw-SENTINEL@host/db")
    env.setenv("PORT", "port-SENTINEL")

    with pytest.raises(SettingsError) as caught:
        load_settings()

    message = str(caught.value)
    assert "port" in message
    assert "SENTINEL" not in message
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_unknown_flask_env_is_rejected(env: pytest.MonkeyPatch) -> None:
    env.setenv("FLASK_ENV", "staging")

    with pytest.raises(SettingsError, match="flask_env"):
        load_settings()


def test_database_url_prefers_pooled(env: pytest.MonkeyPatch) -> None:
    env.setenv("DATABASE_URL", "postgresql://legacy/db")
    assert load_settings().app_database_url == "postgresql://legacy/db"
    assert load_settings().missing_database_vars() == ["DATABASE_URL_POOLED", "DATABASE_URL_DIRECT"]

    env.setenv("DATABASE_URL_POOLED", "postgresql://pooled/db")
    assert load_settings().app_database_url == "postgresql://pooled/db"


def test_cors_origins_default_and_override(env: pytest.MonkeyPatch) -> None:
    env.setenv("CADDY_APP_NAME", "rep")
    assert load_settings().cors_origin_list == [
        "http://localhost:5173", "http://localhost:7300", "http://rep.localhost",
    ]

    env.setenv("CORS_ORIGINS", " http://a.test , ,http://b.test")
    assert load_settings().cors_origin_list == ["http://a.test", "http://b.test"]


@pytest.mark.parametrize(("raw", "expected"), [("", False), ("true", True), ("1", True), ("no", False)])
def test_disable_capture_parsing(env: pytest.MonkeyPatch, raw: str, expected: bool) -> None:
    env.setenv("DISABLE_CAPTURE", raw)

    assert load_settings().disable_capture is expected
