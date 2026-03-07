import logging
import time

import cv2

from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    is_template_visible,
)

logger = logging.getLogger(__name__)


class AwayTeamOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()

    def capture_away_team(self):
        """Navigate to the Away Team screen and collect all available reports and rewards.

        Flow:
          1. Navigate to the home screen.
          2. Click the Mission button to open the missions panel.
          3. Click the Away Team tab.
          4. Click REPORT, wait for COLLECT to appear, click COLLECT, wait for screen
             to return, then repeat until no more REPORT buttons are visible.
          5. For each available slot: click START, click AUTO, click START to launch a new expedition.

        Missing snippets (need to be cropped and added to app/screen_snippets/):
          - Mission Button.jpg  — the missions icon on the home screen nav bar
          - Away Teams Tab 1.jpg / Away Teams Tab 2.jpg  — the Away Teams tab (two visual variants)
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(f"capture_away_team: {e}")
            return {"error": str(e)}

        screen_offset = (window.left, window.top)

        # ── 1. Home screen ────────────────────────────────────────────────────
        try:
            self.sc.navigate_to_home_screen(
                window,
                target_templates=["Home Screen Buttons.jpg"],
                nav_buttons=["TopLeftBackArrow.jpg", "collect.jpg", "Done.jpg"],
                busy_templates=["STFC busy screen.jpg"],
            )
        except RuntimeError as e:
            logger.error(f"capture_away_team: could not reach home screen: {e}")
            return {"error": str(e)}

        # ── 2. Mission button ─────────────────────────────────────────────────
        img_path = self.sc.capture_window(window)
        img = cv2.imread(img_path)
        if not click_button_if_visible("Mission Button.jpg", img, screen_offset):
            logger.error("capture_away_team: Mission Button not found")
            return {
                "error": "Mission Button not found — add Mission Button.jpg to app/screen_snippets/"
            }
        logger.info("capture_away_team: clicked Mission Button")
        time.sleep(0.5)

        # ── 3. Away Team tab ──────────────────────────────────────────────────
        img_path = self.sc.capture_window(window)
        img = cv2.imread(img_path)
        clicked_tab = (
            click_button_if_visible("Away Teams Tab 1.jpg", img, screen_offset)
            or click_button_if_visible("Away Teams Tab 2.jpg", img, screen_offset)
        )
        if not clicked_tab:
            logger.error("capture_away_team: Away Teams Tab not found")
            return {
                "error": "Away Teams Tab not found — add Away Teams Tab 1.jpg / Away Teams Tab 2.jpg to app/screen_snippets/"
            }
        logger.info("capture_away_team: clicked Away Teams Tab")
        time.sleep(0.5)

        # ── 4. REPORT → COLLECT cycle ─────────────────────────────────────────
        reports_clicked = 0
        collected = 0
        while True:
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is None:
                break
            if not click_button_if_visible("AwayTeam Report.jpg", img, screen_offset):
                break
            reports_clicked += 1
            logger.info(f"capture_away_team: clicked REPORT ({reports_clicked})")

            # Wait for COLLECT to appear
            for _ in range(8):
                time.sleep(0.25)
                img_path = self.sc.capture_window(window)
                img = cv2.imread(img_path)
                if img is not None and is_template_visible("collect.jpg", img):
                    break

            # Click COLLECT
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is not None and click_button_if_visible(
                "collect.jpg", img, screen_offset
            ):
                collected += 1
                logger.info(f"capture_away_team: clicked COLLECT ({collected})")

            # Wait for screen to return to the away team list
            for _ in range(8):
                time.sleep(0.25)
                img_path = self.sc.capture_window(window)
                img = cv2.imread(img_path)
                if img is not None and not is_template_visible("collect.jpg", img):
                    break

        logger.info(
            f"capture_away_team: {reports_clicked} report(s), {collected} collected"
        )

        # ── 5. Start new expeditions: START → AUTO → START ───────────────────
        expeditions_started = 0
        while True:
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is None:
                break
            if not click_button_if_visible("Away Team Start.jpg", img, screen_offset):
                break
            logger.info("capture_away_team: clicked START (opening expedition setup)")
            time.sleep(0.5)

            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is not None:
                click_button_if_visible("Away Team Auto.jpg", img, screen_offset)
                logger.info("capture_away_team: clicked AUTO")
                time.sleep(0.5)

            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is not None:
                click_button_if_visible("Away Team Start.jpg", img, screen_offset)
                logger.info("capture_away_team: clicked START (confirming expedition)")
                time.sleep(0.5)

            expeditions_started += 1

        logger.info(
            f"capture_away_team: done — reports={reports_clicked}, collected={collected}, expeditions_started={expeditions_started}"
        )  # noqa: E501
        return {
            "reports_clicked": reports_clicked,
            "collected": collected,
            "expeditions_started": expeditions_started,
        }
