# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-11-06
"""Domain exceptions raised by the data layer and mapped to HTTP status by type.

Routes and the app-level error handlers map these classes, never message text,
so a reworded message cannot change a status code. Messages are written for
the client: they must never carry driver or SQL text. Leaf module.
"""


class DomainError(Exception):
    """Base class for expected, client-safe failures."""


class NotFoundError(DomainError):
    """The addressed record does not exist (HTTP 404)."""


class ConflictError(DomainError):
    """The write would violate a uniqueness rule (HTTP 409)."""
