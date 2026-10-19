# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
import time

from app.app_config import capture_cfg
from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    is_template_visible,
    wait_and_click,
    wait_for_any_template,
    wait_for_template,
)

logger = logging.getLogger(__name__)

_HEADER = "Gifts Header 1.jpg"
_TAB_SELECTED = "Gifts Tab Selected 1.jpg"
_TAB_UNSELECTED = "Gifts Tab Unselected 1.jpg"
_CLAIM_ALL = "Gifts Claim All 1.jpg"
_CLAIM_ONE = "Gifts Claim 1.jpg"
_DONE = "Done.jpg"


class GiftsOrchestrator:
    def __init__(self) -> None:
        self.sc = ScreenCapture()

    def capture_gifts(self):
        """Navigate to the Gifts screen and claim all available gifts.

        Navigation:
          - If the Gifts header is already visible, skip navigation entirely.
          - Otherwise: if the tab is visible click it, else go home → Gifts button.

        Claim loop:
          - While a Claim All button is visible, click it.
          - Wait (with first_delay) for the Done button, then click it.
          - Wait for the gifts list to reload (tab selected OR next Claim All).
          - Repeat until no more Claim All buttons appear.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(str(e))
            return {"error": str(e)}

        screen_offset: tuple[int, int] = (window.left, window.top)
        loop_delay: float = capture_cfg("gifts", "loop_delay", default=0.25)
        claim_first_delay: float = capture_cfg("gifts", "claim_first_delay", default=0.5)
        claim_done_retries: int = capture_cfg("gifts", "claim_done_retries", default=16)
        claim_done_delay: float = capture_cfg("gifts", "claim_done_delay", default=0.25)
        reload_first_delay: float = capture_cfg("gifts", "reload_first_delay", default=0.5)
        reload_delay: float = capture_cfg("gifts", "reload_delay", default=0.2)

        # ── Navigate to Gifts screen ──────────────────────────────────────────
        img = self.sc.capture(window)
        if img is not None and is_template_visible(_HEADER, img):
            logger.info("already on Gifts screen (header detected) — skipping navigation")
        else:
            logger.info("navigating to Gifts screen")
            max_nav_attempts: int = capture_cfg("screen_wait_retries", default=8)
            on_gifts_screen = False

            for attempt in range(1, max_nav_attempts + 1):
                img = self.sc.capture(window)
                if img is None:
                    logger.warning(f"could not read screenshot (attempt {attempt}/{max_nav_attempts})")
                    time.sleep(loop_delay)
                    continue

                if is_template_visible(_TAB_SELECTED, img):
                    logger.info(f"Gifts screen confirmed (attempt {attempt})")
                    on_gifts_screen = True
                    break

                if click_button_if_visible(_TAB_UNSELECTED, img, screen_offset):
                    logger.info(f"clicked Gifts Tab Unselected (attempt {attempt})")
                    time.sleep(loop_delay)
                    continue

                # Not on the gifts screen at all — go home and open Gifts
                logger.info(f"Gifts tab not visible, navigating to home screen (attempt {attempt})")
                try:
                    self.sc.navigate_to_home_screen(window)
                except RuntimeError as e:
                    logger.error(f"could not reach home screen: {e}")
                    return {"error": str(e)}

                img = self.sc.capture(window)
                if not click_button_if_visible(["Gifts 1.jpg", "Gifts 2.jpg"], img, screen_offset):
                    logger.error("Gifts button not visible on home screen")
                    return {"error": "Gifts button not visible on home screen"}
                logger.info("clicked Gifts button on home screen")

                visible_tab, _ = wait_for_any_template([_TAB_SELECTED, _TAB_UNSELECTED], self.sc, window)
                if visible_tab is None:
                    logger.warning("Gifts tab did not appear after clicking Gifts button")
                time.sleep(loop_delay)

            if not on_gifts_screen:
                logger.error(f"could not reach Gifts screen after {max_nav_attempts} attempts")
                return {"error": f"Gifts screen not reached after {max_nav_attempts} attempts"}

        # ── Claim all gifts ───────────────────────────────────────────────────
        logger.info("starting claim loop")
        claims: int = 0
        while True:
            img = self.sc.capture(window)
            if img is None:
                logger.warning("could not read screenshot during claim loop, stopping")
                break

            if click_button_if_visible(_CLAIM_ALL, img, screen_offset):
                label = "Claim All"
            elif click_button_if_visible(_CLAIM_ONE, img, screen_offset):
                label = "Claim"
            else:
                logger.info(f"no Claim/Claim All button visible — claim loop complete ({claims} claim(s))")
                break

            claims += 1
            logger.info(f"clicked {label} ({claims})")

            # Wait for the rewards panel to animate open before polling for Done
            time.sleep(claim_first_delay)
            if not wait_and_click(
                _DONE, self.sc, window, screen_offset,
                max_retries=claim_done_retries, delay=claim_done_delay,
            ):
                logger.warning(f"Done button did not appear after {label} — stopping")
                break

            logger.info("clicked Done, waiting for gifts list to reload")
            # First check after a longer initial pause, then shorter subsequent polls
            time.sleep(reload_first_delay)
            visible, _ = wait_for_any_template(
                [_TAB_SELECTED, _CLAIM_ALL, _CLAIM_ONE], self.sc, window,
                delay=reload_delay,
            )
            if visible is None:
                logger.warning("Gifts screen did not reload after Done — stopping")
                break

        logger.info(f"done — claims={claims}")
        return {"success": True, "claims": claims}
