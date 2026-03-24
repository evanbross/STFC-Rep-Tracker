import logging
import time

import cv2

from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    wait_and_click,
    wait_and_click_any,
    wait_for_any_template,
    wait_for_template,
)

logger = logging.getLogger(__name__)


class AwayTeamOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()

    def capture_away_team(self):
        """Navigate to the Away Team screen and collect all available reports and rewards.

        Flow:
          1. If not already on the Away Teams page: navigate to home screen,
             click the Mission button, then click the Away Teams tab.
          2. Click REPORT, wait for COLLECT to appear, click COLLECT, wait for screen
             to return, then repeat until no more REPORT buttons are visible.
          3. For each available slot: click START, click AUTO, click START to launch a new expedition.

        Missing snippets (need to be cropped and added to app/screen_snippets/):
          - Mission Button.jpg           — the missions icon on the home screen nav bar
          - Away Teams Tab Selected.jpg  — the Away Teams tab when it is the active tab
          - Away Teams Tab Unselected.jpg — the Away Teams tab when another tab is active
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(f"{e}")
            return {"error": str(e)}

        screen_offset = (window.left, window.top)

        # ── 1. Navigate to Away Teams if not already there ────────────────────
        # Try pressing "C" first — it opens the Missions panel in STFC,
        # then wait until the Away Teams tab appears before proceeding.
        self.sc.press_key(window, "c")
        tabSelectedName = "Away Teams Tab Selected.jpg"
        tabUnselectedName = "Away Teams Tab Unselected.jpg"
        tabImages = [tabSelectedName, tabUnselectedName]

        visibleTab, img = wait_for_any_template(
            [tabSelectedName, tabUnselectedName],
            self.sc,
            window,
        )

        if visibleTab == tabSelectedName:
            # Already on the Away Teams page — nothing to do
            logger.info("already on Away Teams page, skipping navigation")
        elif visibleTab == tabUnselectedName:
            # Missions panel is open but Away Teams tab not selected — just click the tab
            if not click_button_if_visible(
                "Away Teams Tab Unselected.jpg", img, screen_offset
            ):
                logger.error("could not click Away Teams Tab Unselected")
                return {"error": "Away Teams Tab Unselected not clickable"}
            logger.info("clicked Away Teams Tab Unselected")
            time.sleep(0.5)
        else:
            # Not on the missions panel at all — navigate from home
            # ── 1a. Home screen ───────────────────────────────────────────────
            try:
                self.sc.navigate_to_home_screen(window)
            except RuntimeError as e:
                logger.error(f"could not reach home screen: {e}")
                return {"error": str(e)}

            # ── 1b. Mission button ────────────────────────────────────────────
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if not click_button_if_visible(
                ["Mission Button.jpg", "Mission Button 2.jpg"], img, screen_offset
            ):
                logger.error("Mission Button not found")
                return {
                    "error": "Mission Button not found — add Mission Button.jpg to app/screen_snippets/"
                }
            logger.info("clicked Mission Button")
            time.sleep(0.5)

            # ── 1c. Away Teams tab ────────────────────────────────────────────
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if not click_button_if_visible(
                tabImages,
                img,
                screen_offset,
            ):
                logger.error("Away Teams Tab (Un)selected not found")
                return {
                    "error": "Away Teams Tab (Un)selected not found — add Away Teams Tab Unselected.jpg to app/screen_snippets/"
                }
            logger.info("clicked Away Teams Tab")
            time.sleep(0.5)

        # ── 2. REPORT → COLLECT cycle ─────────────────────────────────────────
        reports_clicked = 0
        collected = 0
        while True:
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is None:
                break
            if not click_button_if_visible("Away Teams Report.jpg", img, screen_offset):
                break
            reports_clicked += 1
            logger.info(f"clicked REPORT ({reports_clicked})")

            if wait_and_click("collect.jpg", self.sc, window, screen_offset):
                collected += 1
                logger.info(f"clicked COLLECT ({collected})")

            # Wait for screen to return to the away team list; allow extra time for
            # the collect animation to finish before checking for more REPORT buttons.
            if wait_for_template("Away Teams Tab Selected.jpg", self.sc, window, max_retries=20) is None:
                logger.warning("Away Teams tab not redetected after COLLECT, stopping report cycle")
                break
            time.sleep(0.5)  # let the list fully settle after the tab reappears

        logger.info(f"{reports_clicked} report(s), {collected} collected")

        # ── 3. Start new expeditions: START → AUTO → START ───────────────────
        expeditions_started = 0
        while True:
            # Wait for the Away Teams list to be showing before checking for buttons.
            if wait_for_template("Away Teams List Indicator.jpg", self.sc, window, max_retries=20) is None:
                logger.warning("Away Teams list not detected, stopping")
                break

            # Give the list a moment to fully render all buttons before capturing.
            time.sleep(0.5)
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is None:
                break

            if not click_button_if_visible(
                "Away Teams Start Blue.jpg", img, screen_offset
            ):
                logger.info("no blue START button found — all expeditions started")
                break
            logger.info("clicked START (opening expedition setup)")

            if not wait_and_click(
                "Away Teams Auto.jpg", self.sc, window, screen_offset
            ):
                logger.warning("AUTO button not detected, stopping")
                break
            logger.info("clicked AUTO")

            if not wait_and_click_any(
                ["Away Teams Start Green.jpg", "Away Teams Start Charts.jpg"],
                self.sc,
                window,
                screen_offset,
            ):
                logger.warning("Green START button not detected, stopping")
                break
            logger.info("clicked START (confirming expedition)")

            expeditions_started += 1
            # Give the game time to play the expedition-launch animation and
            # return to the Away Teams list before the next poll cycle.
            time.sleep(2.0)

        logger.info(
            f"done — reports={reports_clicked}, collected={collected}, expeditions_started={expeditions_started}"
        )  # noqa: E501
        return {
            "reports_clicked": reports_clicked,
            "collected": collected,
            "expeditions_started": expeditions_started,
        }
