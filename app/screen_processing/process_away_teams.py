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

    def _get_activated_window(self):
        """Return (window, None) on success or (None, error_dict) on failure."""
        try:
            return self.sc.get_and_activate_window(), None
        except RuntimeError as e:
            logger.error(str(e))
            return None, {"error": str(e)}

    def _navigate_to_away_teams(self, window, screen_offset):
        """Navigate to the Away Teams tab. Returns an error dict on failure, else None."""
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
            logger.info("already on Away Teams page, skipping navigation")
        elif visibleTab == tabUnselectedName:
            if not click_button_if_visible("Away Teams Tab Unselected.jpg", img, screen_offset):
                logger.error("could not click Away Teams Tab Unselected")
                return {"error": "Away Teams Tab Unselected not clickable"}
            logger.info("clicked Away Teams Tab Unselected")
            time.sleep(0.5)
        else:
            try:
                self.sc.navigate_to_home_screen(window)
            except RuntimeError as e:
                logger.error(f"could not reach home screen: {e}")
                return {"error": str(e)}

            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if not click_button_if_visible(
                ["Mission Button.jpg", "Mission Button 2.jpg"], img, screen_offset
            ):
                logger.error("Mission Button not found")
                return {"error": "Mission Button not found — add Mission Button.jpg to app/screen_snippets/"}
            logger.info("clicked Mission Button")
            time.sleep(0.5)

            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if not click_button_if_visible(tabImages, img, screen_offset):
                logger.error("Away Teams Tab (Un)selected not found")
                return {"error": "Away Teams Tab (Un)selected not found — add Away Teams Tab Unselected.jpg to app/screen_snippets/"}
            logger.info("clicked Away Teams Tab")
            time.sleep(0.5)

        return None

    def _collect_reports(self, window, screen_offset):
        """Click REPORT → COLLECT for all completed missions. Returns (reports_clicked, collected)."""
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

            if wait_for_template("Away Teams Tab Selected.jpg", self.sc, window, max_retries=20) is None:
                logger.warning("Away Teams tab not redetected after COLLECT, stopping report cycle")
                break
            time.sleep(0.5)

        logger.info(f"{reports_clicked} report(s), {collected} collected")
        return reports_clicked, collected

    def _start_expeditions(self, window, screen_offset):
        """Start new expeditions via START → AUTO → START. Returns expeditions_started count."""
        expeditions_started = 0
        while True:
            if wait_for_template("Away Teams List Indicator.jpg", self.sc, window, max_retries=20) is None:
                logger.warning("Away Teams list not detected, stopping")
                break

            time.sleep(0.5)
            img_path = self.sc.capture_window(window)
            img = cv2.imread(img_path)
            if img is None:
                break

            if not click_button_if_visible("Away Teams Start Blue.jpg", img, screen_offset):
                logger.info("no blue START button found — all expeditions started")
                break
            logger.info("clicked START (opening expedition setup)")

            if not wait_and_click("Away Teams Auto.jpg", self.sc, window, screen_offset):
                logger.warning("AUTO button not detected, stopping")
                break
            logger.info("clicked AUTO")

            if not wait_and_click_any(
                ["Away Teams Start Green.jpg", "Away Teams Start Charts.jpg"],
                self.sc, window, screen_offset,
            ):
                logger.warning("Green START button not detected, stopping")
                break
            logger.info("clicked START (confirming expedition)")

            expeditions_started += 1
            time.sleep(2.0)

        return expeditions_started

    def capture_away_team_collect(self):
        """Navigate to Away Teams and collect all completed missions (REPORT → COLLECT only).
        Does not start new expeditions.
        """
        window, err = self._get_activated_window()
        if err:
            return err

        screen_offset = (window.left, window.top)

        err = self._navigate_to_away_teams(window, screen_offset)
        if err:
            return err

        reports_clicked, collected = self._collect_reports(window, screen_offset)

        logger.info(f"done (collect only) — reports={reports_clicked}, collected={collected}")
        return {
            "reports_clicked": reports_clicked,
            "collected": collected,
            "expeditions_started": 0,
        }

    def capture_away_team(self):
        """Navigate to Away Teams, collect all completed missions, then start new expeditions."""
        window, err = self._get_activated_window()
        if err:
            return err

        screen_offset = (window.left, window.top)

        err = self._navigate_to_away_teams(window, screen_offset)
        if err:
            return err

        reports_clicked, collected = self._collect_reports(window, screen_offset)
        expeditions_started = self._start_expeditions(window, screen_offset)

        logger.info(
            f"done — reports={reports_clicked}, collected={collected}, expeditions_started={expeditions_started}"
        )
        return {
            "reports_clicked": reports_clicked,
            "collected": collected,
            "expeditions_started": expeditions_started,
        }
