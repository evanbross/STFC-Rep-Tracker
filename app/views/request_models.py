# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Pydantic models for every JSON request body the API accepts.

Kept free of Windows-only imports so the capture routes' models can be tested
without pyautogui/pywin32. Models use Pydantic's default (lax) mode, so numeric
strings such as "3" are accepted, as the old int(...) calls did. Unknown keys
are ignored (the Factions form sends an `id` alias, for example).
"""
import math
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, model_validator

from app.app_config import TemplateKind
from app.database.reputations_dao import ReputationsDAO
from app.database.target_types_dao import TargetPreference

_PG_BIGINT_MIN = -(2**63)
_PG_BIGINT_MAX = 2**63 - 1

BigInt = Annotated[int, Field(ge=_PG_BIGINT_MIN, le=_PG_BIGINT_MAX)]
"""Integer that fits a PostgreSQL BIGINT column."""

# ai: claude-opus-5-5 | 2026-11-17
# Largest epoch-millisecond value datetime can represent (year 9999).
_MAX_EPOCH_MS = 253_402_300_799_000
# How far ahead of the server clock an import timestamp may be: the browser's
# clock (and so a file's lastModified) can run a little fast.
_CLOCK_SKEW = timedelta(minutes=5)


def _blank_to_none(value: Any) -> Any:
    """Treat an empty or whitespace-only string from a form field as 'not set'."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _truncate_float(value: Any) -> Any:
    """Accept finite floats for pixel coordinates by truncating, as int() did."""
    if isinstance(value, float) and math.isfinite(value):
        return int(value)
    return value


OptionalInt = Annotated[int | None, BeforeValidator(_blank_to_none)]
PixelCoord = Annotated[int, BeforeValidator(_truncate_float), Field(ge=0)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonBlankStr = Annotated[str, Field(min_length=1)]
OptionalStr = Annotated[str | None, BeforeValidator(_blank_to_none)]  # ai: claude-opus-5-5 | 2026-11-06


class RequestModel(BaseModel):
    """Shared settings: trim string whitespace, ignore unknown keys."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


# ai: claude-opus-5-5 | 2026-11-06
class StatusEntriesQuery(RequestModel):
    """Query string of GET /api/status_entries/ (and /all). `days` keeps only recent entries."""

    faction_name: str | None = None
    limit: int | None = Field(default=None, ge=0)
    offset: int | None = Field(default=None, ge=0)
    sort: str | None = None
    days: int | None = Field(default=None, ge=1, le=36500)


class FactionIn(RequestModel):
    """Body of POST /api/factions/ and PUT /api/factions/<code>."""

    name: NonBlankStr
    code: NonBlankStr
    color: str | None = None
    reputation_table_name: OptionalStr = None
    on_chart: int = 0
    display_order: OptionalInt = None
    reputation_dao_name: OptionalStr = None
    snippet_selected_button: str | None = None
    snippet_unselected: str | None = None
    # ai: claude-opus-5-5 | 2026-11-17 — the resource row a Spock's Club export stores this faction's reputation in
    spocks_resource_id: Annotated[
        Annotated[int, Field(ge=0, le=_PG_BIGINT_MAX)] | None, BeforeValidator(_blank_to_none)
    ] = None

    # ai: claude-opus-5-5 | 2026-11-06
    @model_validator(mode="after")
    def _known_reputation_type(self) -> "FactionIn":
        """The reputation table must be one a *_reputations_dao.py file implements (R5).

        The DAO name follows from the table, so it is filled in when omitted
        and must match when sent.
        """
        if self.reputation_table_name is None:
            if self.reputation_dao_name is not None:
                raise ValueError("reputation_dao_name needs a reputation_table_name")
            return self
        dao_class = ReputationsDAO.available_implementations().get(self.reputation_table_name)
        if dao_class is None:
            known = ", ".join(ReputationsDAO.available_implementations())
            raise ValueError(f"Unknown reputation_table_name; expected one of: {known}")
        if self.reputation_dao_name not in (None, dao_class.__name__):
            raise ValueError(f"reputation_dao_name for this table must be {dao_class.__name__}")
        self.reputation_dao_name = dao_class.__name__
        return self


class StatusEntryIn(RequestModel):
    """Body of POST /api/status_entries/."""

    faction: NonBlankStr
    value: BigInt


# ai: claude-opus-5-5 | 2026-11-17
class SpocksClubPreviewForm(RequestModel):
    """Text fields of POST /api/spocks-club/preview (the export itself is the `file` part).

    last_modified is the browser's File.lastModified (ms since the epoch), used as
    the reading time when the filename carries no export time.
    """

    last_modified: Annotated[
        Annotated[int, Field(ge=0, le=_MAX_EPOCH_MS)] | None, BeforeValidator(_blank_to_none)
    ] = None


class SpocksClubReadingIn(RequestModel):
    faction_code: NonBlankStr
    value: BigInt


class SpocksClubImportIn(RequestModel):
    """Body of POST /api/spocks-club/import: the previewed readings, all saved at exported_at."""

    exported_at: AwareDatetime
    readings: list[SpocksClubReadingIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_reading_per_faction_and_not_future(self) -> "SpocksClubImportIn":
        codes = [reading.faction_code for reading in self.readings]
        if len(codes) != len(set(codes)):
            raise ValueError("Each faction may appear only once")
        if self.exported_at > datetime.now(UTC) + _CLOCK_SKEW:
            raise ValueError("exported_at is in the future")
        return self


class ReputationRowPatch(RequestModel):
    """Body of PUT /api/reputations/by-table/<table>/<id>; only sent fields change."""

    name: NonBlankStr | None = None
    low_limit: BigInt | None = None
    high_limit: BigInt | None = None
    messages_count: BigInt | None = None
    credit_amount: BigInt | None = None


class TerritorySystemIn(RequestModel):
    """Body of POST /api/territory/systems and PUT /api/territory/systems/<id>."""

    name: NonBlankStr
    # Strict: the UI sends a number; "1" was rejected before and still is.
    day_of_week: Annotated[StrictInt, Field(ge=0, le=6)]
    event_time: Annotated[str, Field(pattern=r"^([01]?\d|2[0-3]):[0-5]\d$")]


class CalendarEventIn(RequestModel):
    """Optional body of POST /api/territory/systems/<id>/calendar-event."""

    calendar_id: NonBlankStr = "primary"


class TargetPreferenceIn(RequestModel):
    """Body of PUT /api/target-types/<id>."""

    preference: TargetPreference
    display_name: str | None = None


class RefreshTargetsIn(RequestModel):
    """Body of POST /api/capture-screen/system-targets/refresh."""

    system_name: NonBlankStr
    known_candidates: list[dict[str, Any]] = Field(default_factory=list)


class AttackIn(RequestModel):
    """Body of POST /api/capture-screen/system-targets/attack."""

    click_x: PixelCoord
    click_y: PixelCoord
    vx: FiniteFloat = 0.0
    vy: FiniteFloat = 0.0
    scanned_at: FiniteFloat | None = None


class TemplateCropIn(RequestModel):
    """Body of POST /api/capture-screen/hostile-template/save."""

    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]
    w: Annotated[int, Field(gt=0)]
    h: Annotated[int, Field(gt=0)]
    kind: TemplateKind = "hostile_ship"
