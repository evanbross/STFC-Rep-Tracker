# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Typed application settings read from the environment (R1).

main.py calls load_dotenv() first, so .env values arrive here as ordinary
environment variables. Validation runs once, at startup, and a production
profile without a real SECRET_KEY refuses to start. Error messages never
include the rejected values, since they sit next to database passwords.
"""
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-secret-key-change-in-production"

# Values shipped in examples and compose files; never acceptable in production.
PLACEHOLDER_SECRET_KEYS: frozenset[str] = frozenset({
    DEV_SECRET_KEY,
    "change-me-in-production",
    "changeme",
    "secret",
})
MIN_PRODUCTION_SECRET_LENGTH = 16

FlaskEnv = Literal["development", "production", "testing"]


class AppSettings(BaseSettings):
    """Every environment variable the backend reads, with its type and default."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore", hide_input_in_errors=True)

    flask_env: FlaskEnv = "development"
    secret_key: str = ""
    database_url_pooled: str = ""
    database_url_direct: str = ""
    database_url: str = ""          # legacy single-URL fallback for DATABASE_URL_POOLED
    caddy_app_name: str = "stfc"
    cors_origins: str = ""          # comma-separated; empty means the built-in local defaults
    port: int = Field(default=7300, ge=1, le=65535)
    disable_capture: bool = False
    # ai: claude-opus-5-5 | 2026-11-19
    # Shared secret the community mod sends in its stfc-sync-token header. Empty
    # means the endpoint accepts any caller, which is fine only while it's reachable
    # from this machine alone; set it before exposing the app anywhere else.
    community_mod_token: str = ""
    # ai: claude-opus-5-5 | 2026-11-19
    # Random per-start value the launcher passes and /api/health echoes, so the
    # launcher's readiness check can't be answered by some other process on the port.
    launch_id: str = ""

    @field_validator("disable_capture", mode="before")
    @classmethod
    def _blank_is_false(cls, value: Any) -> Any:
        """DISABLE_CAPTURE= (set but empty) means 'not disabled', as before."""
        return False if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _production_needs_real_secret(self) -> "AppSettings":
        if self.flask_env != "production":
            return self
        key = self.secret_key.strip()
        if key.lower() in PLACEHOLDER_SECRET_KEYS or len(key) < MIN_PRODUCTION_SECRET_LENGTH:
            raise ValueError(
                "FLASK_ENV=production needs SECRET_KEY set to a random value of at least "
                f"{MIN_PRODUCTION_SECRET_LENGTH} characters (not a placeholder). Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self

    @property
    def app_database_url(self) -> str:
        """The URL the app's connection uses: the pooled endpoint, else DATABASE_URL."""
        return self.database_url_pooled or self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip():
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return ["http://localhost:5173", "http://localhost:7300", f"http://{self.caddy_app_name}.localhost"]

    def missing_database_vars(self) -> list[str]:
        """Names of the required database variables that are unset."""
        required = {"DATABASE_URL_POOLED": self.database_url_pooled, "DATABASE_URL_DIRECT": self.database_url_direct}
        return [name for name, value in required.items() if not value]

    def flask_config(self) -> dict[str, Any]:
        """The values main.create_app() loads into flask_app.config."""
        return {
            "SECRET_KEY": self.secret_key or DEV_SECRET_KEY,
            "DATABASE_URL": self.app_database_url,
            "CORS_ORIGINS": self.cors_origin_list,
            "DEBUG": self.flask_env == "development",
            "TESTING": self.flask_env == "testing",
            "COMMUNITY_MOD_TOKEN": self.community_mod_token.strip(),  # ai: claude-opus-5-5 | 2026-11-19
            "LAUNCH_ID": self.launch_id,  # ai: claude-opus-5-5 | 2026-11-19
        }


class SettingsError(RuntimeError):
    """Startup settings are invalid; the message names fields, never values."""


def load_settings() -> AppSettings:
    """Read and validate settings from the environment."""
    try:
        return AppSettings()
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'settings'}: {err['msg']}"
            for err in exc.errors(include_url=False, include_input=False)
        )
        raise SettingsError(f"Invalid settings: {problems}") from None
