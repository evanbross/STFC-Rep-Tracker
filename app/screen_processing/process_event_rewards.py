# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# LICENSE: Personal Use Only
# This source code is made available for personal, non-commercial use only.
# You may read, study, and run this code for personal purposes.
# You may NOT:
#   - Use this code, in whole or in part, in any commercial product or service
#   - Sell, sublicense, or otherwise monetize this code or derivatives of it
#   - Redistribute this code without explicit written permission from ZombieTech LLC
#
# No warranty is provided, express or implied. Use at your own risk.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging

from app.screen_processing.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class EventRewardsOrchestrator:
    def __init__(self) -> None:
        self.sc = ScreenCapture()

    def capture_event_rewards(self):
        """
        Activate the STFC window and capture the Event Rewards screen.
        Navigation logic to be implemented.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(f"{e}")
            return {"error": str(e)}

        filepath = self.sc.capture_window(window)
        logger.info(f"Captured screenshot: {filepath}")
        return {"image_path": filepath}
