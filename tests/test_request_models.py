# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Pure tests for request-body models, including the capture routes that need Windows to run."""
import pytest
from pydantic import ValidationError

from app.database.target_types_dao import TARGET_PREFERENCES
from app.views.request_models import (
    AttackIn,
    RequestModel,
    RefreshTargetsIn,
    StatusEntryIn,
    TargetPreferenceIn,
    TemplateCropIn,
    TerritorySystemIn,
)


def test_attack_truncates_finite_float_coordinates() -> None:
    body = AttackIn.model_validate({"click_x": 512.9, "click_y": "40", "scanned_at": 1.5})

    assert (body.click_x, body.click_y, body.vx, body.scanned_at) == (512, 40, 0.0, 1.5)


@pytest.mark.parametrize(
    "payload",
    [
        {"click_y": 1},                                   # missing click_x
        {"click_x": -1, "click_y": 1},                    # off-screen
        {"click_x": float("nan"), "click_y": 1},
        {"click_x": 1, "click_y": 1, "vx": float("inf")},
        {"click_x": "left", "click_y": 1},
    ],
)
def test_attack_rejects_bad_input(payload: dict) -> None:
    with pytest.raises(ValidationError):
        AttackIn.model_validate(payload)


def test_template_crop_defaults_and_kinds() -> None:
    assert TemplateCropIn.model_validate({"x": 0, "y": 0, "w": 5, "h": 5}).kind == "hostile_ship"
    with pytest.raises(ValidationError):
        TemplateCropIn.model_validate({"x": 0, "y": 0, "w": 5, "h": 5, "kind": "planet"})
    with pytest.raises(ValidationError):
        TemplateCropIn.model_validate({"x": 0, "y": 0, "w": 0, "h": 5})


def test_refresh_requires_system_name() -> None:
    assert RefreshTargetsIn.model_validate({"system_name": " Sol "}).system_name == "Sol"
    with pytest.raises(ValidationError):
        RefreshTargetsIn.model_validate({"system_name": "   "})


def test_status_value_must_fit_bigint() -> None:
    assert StatusEntryIn.model_validate({"faction": "Fed", "value": "2400000000"}).value == 2_400_000_000
    with pytest.raises(ValidationError):
        StatusEntryIn.model_validate({"faction": "Fed", "value": 2**63})


@pytest.mark.parametrize("event_time", ["07:05", "7:05", "23:59"])
def test_territory_time_accepts(event_time: str) -> None:
    body = TerritorySystemIn.model_validate({"name": "Risa", "day_of_week": 1, "event_time": event_time})

    assert body.event_time == event_time


@pytest.mark.parametrize("event_time", ["24:00", "12:60", "noon", "12:00:00"])
def test_territory_time_rejects(event_time: str) -> None:
    with pytest.raises(ValidationError):
        TerritorySystemIn.model_validate({"name": "Risa", "day_of_week": 1, "event_time": event_time})


def test_preference_values_come_from_the_dao() -> None:
    for preference in TARGET_PREFERENCES:
        assert TargetPreferenceIn.model_validate({"preference": preference}).preference == preference


# ai: claude-opus-5-5 | 2026-11-18
@pytest.mark.parametrize("model", RequestModel.__subclasses__(), ids=lambda m: m.__name__)
def test_every_request_model_rejects_unknown_keys(model: type[RequestModel]) -> None:
    with pytest.raises(ValidationError) as caught:
        model.model_validate({"not_a_field": 1})

    assert {"type": "extra_forbidden", "loc": ("not_a_field",)} in [
        {"type": err["type"], "loc": err["loc"]} for err in caught.value.errors()
    ]
