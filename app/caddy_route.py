# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-19
"""This backend's http://<name>.localhost route in the shared dev Caddy.

The backend registers itself once it has bound its port, so the route always
points at the process actually serving, however it was started (the launcher,
PyCharm, `python main.py`). zt-common is an optional dev dependency: the
installed app doesn't ship it, and then the app is reached on localhost:<port>.
"""
import logging

try:
    from zt_common import caddy_registry
except ImportError:
    caddy_registry = None

logger = logging.getLogger(__name__)


class CaddyRoute:
    """Registers name.localhost -> this port, keeps it registered, and removes it on stop()."""

    def __init__(self, name: str, port: int) -> None:
        self.name = name
        self.port = port
        self._registered = False
        self._reconciler = None

    def start(self) -> None:
        if caddy_registry is None:
            logger.info("zt-common isn't installed; serving on localhost:%d only", self.port)
            return
        self._register()
        # Caddy keeps routes in memory, so a Caddy restart drops them, and a
        # Caddy that starts after this app never had one. The reconciler puts
        # the route back in both cases. "app-<name>" is the id register() uses.
        self._reconciler = caddy_registry.RouteReconciler([f"app-{self.name}"], self._register)
        self._reconciler.start()

    def stop(self) -> None:
        """Remove the route. Runs only on a clean exit: the launcher stops the
        backend with TerminateProcess, so it removes the route itself afterwards."""
        if self._reconciler is not None:
            self._reconciler.stop()  # first, so it can't re-add the route
        if caddy_registry is not None:
            caddy_registry.deregister(self.name)
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    @property
    def url(self) -> str:
        """Where to open the app: the Caddy name when registered, else the port."""
        return f"http://{self.name}.localhost" if self._registered else f"http://localhost:{self.port}"

    def _register(self) -> None:
        self._registered = caddy_registry.register(self.name, self.port)
