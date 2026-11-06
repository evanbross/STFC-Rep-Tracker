# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging

from app.screen_processing.base_orchestrator import BaseOrchestrator

logger = logging.getLogger(__name__)


# ai: claude-opus-5-5 | 2026-11-06
class EventRewardsOrchestrator(BaseOrchestrator):
    def capture_event_rewards(self) -> dict:
        """Placeholder: navigating to and reading the Event Rewards screen isn't built yet.

        It used to take a screenshot and report success, which looked like a
        working capture. It now fails loudly, and the Dashboard button is disabled.
        """
        raise NotImplementedError("Event Rewards capture is not implemented yet")
