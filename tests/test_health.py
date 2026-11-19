# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-19
"""/api/health, the backend's own Caddy route, and the launcher's readiness wait.

No database: the health blueprint runs on a bare Flask app, and Caddy is a fake
standing in for zt_common.caddy_registry.
"""
from collections.abc import Callable

import pytest
from flask import Flask

import launcher
from app import caddy_route
from app.caddy_route import CaddyRoute
from app.views.health_view import health_bp


class FakeReconciler:
    def __init__(self, route_ids: list[str], register: Callable[[], object]) -> None:
        self.route_ids = route_ids
        self.register = register
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakeCaddy:
    """The parts of zt_common.caddy_registry that CaddyRoute uses."""

    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable
        self.routes: dict[str, int] = {}
        self.reconcilers: list[FakeReconciler] = []

    def register(self, name: str, port: int) -> bool:
        if self.reachable:
            self.routes[name] = port
        return self.reachable

    def deregister(self, name: str) -> None:
        self.routes.pop(name, None)

    def RouteReconciler(self, route_ids: list[str], register: Callable[[], object]) -> FakeReconciler:  # noqa: N802
        reconciler = FakeReconciler(route_ids, register)
        self.reconcilers.append(reconciler)
        return reconciler


def _health_client(**config: object):
    app = Flask("health_test")
    app.config.update(config)
    app.register_blueprint(health_bp, url_prefix="/api/health")
    return app.test_client()


def test_health_without_a_launch_or_route_reports_the_request_host() -> None:
    body = _health_client().get("/api/health").get_json()

    assert body == {"status": "ok", "launch_id": None, "url": "http://localhost", "caddy_app_name": None}


def test_health_echoes_the_launch_id_and_the_registered_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(caddy_route, "caddy_registry", FakeCaddy(reachable=True))
    route = CaddyRoute("stfc", 7301)
    route.start()

    body = _health_client(LAUNCH_ID="abc", CADDY_ROUTE=route).get("/api/health").get_json()

    assert body == {"status": "ok", "launch_id": "abc", "url": "http://stfc.localhost", "caddy_app_name": "stfc"}


def test_route_registers_reconciles_and_deregisters(monkeypatch: pytest.MonkeyPatch) -> None:
    caddy = FakeCaddy(reachable=True)
    monkeypatch.setattr(caddy_route, "caddy_registry", caddy)
    route = CaddyRoute("stfc", 7301)

    route.start()
    assert caddy.routes == {"stfc": 7301}
    [reconciler] = caddy.reconcilers
    assert reconciler.started and reconciler.route_ids == ["app-stfc"]

    route.stop()
    assert reconciler.stopped
    assert caddy.routes == {}
    assert route.url == "http://localhost:7301"


def test_route_falls_back_to_the_port_when_caddy_is_down_then_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    caddy = FakeCaddy(reachable=False)
    monkeypatch.setattr(caddy_route, "caddy_registry", caddy)
    route = CaddyRoute("stfc", 7301)

    route.start()
    assert (route.registered, route.url) == (False, "http://localhost:7301")

    caddy.reachable = True
    caddy.reconcilers[0].register()  # what the reconciler does once Caddy is back
    assert (route.registered, route.url) == (True, "http://stfc.localhost")


def test_route_without_zt_common_serves_on_the_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(caddy_route, "caddy_registry", None)
    route = CaddyRoute("stfc", 7301)

    route.start()
    route.stop()

    assert route.url == "http://localhost:7301"


class FakeProcess:
    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code


def test_launcher_waits_for_its_own_launch_id(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([None, {"launch_id": "someone-else"}, {"launch_id": "mine", "url": "http://stfc.localhost"}])
    monkeypatch.setattr(launcher, "read_health", lambda port: next(answers))
    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: None)

    health = launcher.wait_for_health(7301, "mine", FakeProcess())

    assert health == {"launch_id": "mine", "url": "http://stfc.localhost"}


def test_launcher_stops_waiting_when_the_backend_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher, "read_health", lambda port: pytest.fail("probed a dead backend"))

    assert launcher.wait_for_health(7301, "mine", FakeProcess(exit_code=1)) is None
