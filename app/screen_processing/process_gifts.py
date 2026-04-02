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

_TAB_SELECTED = "Gifts Tab Selected 1.jpg"
_TAB_UNSELECTED = "Gifts Tab Unselected 1.jpg"
_CLAIM_ALL = "Gifts Claim All 1.jpg"
_DONE = "Done.jpg"


class GiftsOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()

    def capture_gifts(self):
        """Navigate to the Gifts screen and claim all available gifts.

        Navigation loop:
          - If the Gifts tab (selected) is visible, proceed immediately.
          - If the Gifts tab (unselected) is visible, click it and wait.
          - Otherwise navigate to the home screen and click the Gifts button.
          - Repeat until the Gifts tab selected state is confirmed.

        Claim loop:
          - While a Claim All button is visible, click it.
          - Wait for and click the Done button after each claim.
          - Repeat until no more Claim All buttons appear.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(f"{e}")
            return {"error": str(e)}

        screen_offset = (window.left, window.top)
        max_nav_attempts = capture_cfg("screen_wait_retries", default=8)
        loop_delay = capture_cfg("gifts", "loop_delay", default=0.25)

        # ── Loop 1: Navigate to Gifts screen ─────────────────────────────────
        logger.info("starting navigation loop to reach Gifts screen")
        on_gifts_screen = False
        for attempt in range(1, max_nav_attempts + 1):
            img = self.sc.capture(window)
            if img is None:
                logger.warning(
                    f"could not read screenshot (attempt {attempt}/{max_nav_attempts})"
                )
                time.sleep(loop_delay)
                continue

            if is_template_visible(_TAB_SELECTED, img):
                logger.info(f"Gifts screen confirmed (attempt {attempt})")
                on_gifts_screen = True
                break

            if click_button_if_visible(_TAB_UNSELECTED, img, screen_offset):
                logger.info(
                    f"clicked Gifts Tab Unselected, waiting for selected state (attempt {attempt})"
                )
                time.sleep(loop_delay)
                continue

            # Not on gifts screen at all — go home and click the Gifts button
            logger.info(
                f"Gifts tab not visible, navigating to home screen (attempt {attempt})"
            )
            try:
                self.sc.navigate_to_home_screen(window)
            except RuntimeError as e:
                logger.error(f"could not reach home screen: {e}")
                return {"error": str(e)}

            img = self.sc.capture(window)
            if not click_button_if_visible(
                ["Gifts 1.jpg", "Gifts 2.jpg"], img, screen_offset
            ):
                logger.error("Gifts button not visible on home screen")
                return {"error": "Gifts button not visible on home screen"}
            logger.info(
                "clicked Gifts button on home screen, waiting for Gifts tab to appear"
            )

            # Wait for the gifts screen to finish loading before the next loop check
            visible_tab, _ = wait_for_any_template(
                [_TAB_SELECTED, _TAB_UNSELECTED], self.sc, window
            )
            if visible_tab is None:
                logger.warning("Gifts tab did not appear after clicking Gifts button")
            time.sleep(loop_delay)

        if not on_gifts_screen:
            logger.error(
                f"could not reach Gifts screen after {max_nav_attempts} attempts"
            )
            return {
                "error": f"Gifts screen not reached after {max_nav_attempts} attempts"
            }

        # ── Loop 2: Claim all gifts ───────────────────────────────────────────
        logger.info("starting claim loop")
        claims = 0
        while True:
            img = self.sc.capture(window)
            if img is None:
                logger.warning("could not read screenshot during claim loop, stopping")
                break

            if not click_button_if_visible(_CLAIM_ALL, img, screen_offset):
                logger.info(
                    f"no Claim All button visible — claim loop complete ({claims} claim(s))"
                )
                break

            claims += 1
            logger.info(f"clicked Claim All ({claims})")

            if not wait_and_click(_DONE, self.sc, window, screen_offset):
                logger.warning("Done button did not appear after Claim All, stopping")
                break

            logger.info("clicked Done, waiting for gifts list to return")
            if wait_for_template(_TAB_SELECTED, self.sc, window) is None:
                logger.warning("Gifts tab did not reappear after Done, stopping")
                break
            time.sleep(loop_delay)

        logger.info(f"done — claims={claims}")
        return {"success": True, "claims": claims}
