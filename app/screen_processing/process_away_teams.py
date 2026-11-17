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
from app.screen_processing.base_orchestrator import BaseOrchestrator
from app.screen_processing.capture_errors import CaptureError, CaptureTargetNotFound
from app.screen_processing.screen_capture import (
    click_button_if_visible,
    click_template_match_at,
    match_template,
    wait_and_click,
    wait_and_click_any,
    wait_for_any_template,
)

logger = logging.getLogger(__name__)


# ai: claude-sonnet-5 | 2026-09-16
def _log_near_misses(filenames, img) -> None:
    """Log each candidate template's match score vs threshold.

    Used when a wait_for_*/click_* call comes back empty, to distinguish "the
    template file is missing", "it's on screen but just under threshold"
    (score close to but below threshold — likely a stale snippet needing a
    fresh crop), and "nothing remotely resembling it is on screen at all"
    (score far below threshold — likely on the wrong page/state entirely).
    """
    threshold = capture_cfg("button_match_threshold", default=0.85)
    for filename in filenames:
        try:
            match = match_template(filename, img)
        except FileNotFoundError:
            logger.warning("%s snippet file is missing", filename)
            continue
        if match:
            logger.info("%s score %.2f (threshold %.2f)", filename, match[1], threshold)


class AwayTeamOrchestrator(BaseOrchestrator):  # ai: claude-opus-5-5 | 2026-11-06
    def _navigate_to_away_teams(self, window, screen_offset) -> None:
        """Navigate to the Away Teams tab. Raises a CaptureError if it can't get there."""
        tab_selected_name = "Away Teams Tab Selected.jpg"
        tab_unselected_name = "Away Teams Tab Unselected.jpg"
        tab_images = [tab_selected_name, tab_unselected_name]

        # ai: claude-sonnet-5 | 2026-08-27
        # Check current screen state before pressing anything. Uses the default
        # screen_wait_retries/delay (not a short-circuited count) so a tab icon
        # that's mid-transition or carrying a notification badge still gets
        # detected instead of falsely triggering the "not on this panel" path.
        visible_tab, img = wait_for_any_template(
            [tab_selected_name, tab_unselected_name],
            self.sc,
            window,
        )

        if visible_tab == tab_selected_name:
            logger.info("already on Away Teams page, skipping navigation")
            return

        if visible_tab == tab_unselected_name:
            if not click_button_if_visible(
                "Away Teams Tab Unselected.jpg", img, screen_offset
            ):
                raise CaptureError("Away Teams Tab Unselected not clickable")  # ai: claude-opus-5-5 | 2026-11-06
            logger.info("clicked Away Teams Tab Unselected")
            time.sleep(0.3)
            return

        # Neither tab template matched — log how close each one came before
        # falling through to the 'T'-key path, so a near-miss (stale snippet)
        # is distinguishable from "nowhere close" (wrong screen entirely).
        fresh = self.sc.capture(window)
        if fresh is not None:
            _log_near_misses(tab_images, fresh)

        # Not on the missions panel at all — try pressing "c" to open it.
        # ai: claude-sonnet-5 | 2026-08-27
        # click_center_and_press (not press_key) clicks the game canvas first to
        # blur any focused in-game text box (e.g. a chat input on system-view
        # screens) — otherwise the "c" keystroke can land in chat instead of
        # triggering the Away Teams hotkey.
        self.sc.click_center_and_press(window, "T")
        visible_tab, img = wait_for_any_template(
            [tab_selected_name, tab_unselected_name],
            self.sc,
            window,
        )

        if visible_tab == tab_selected_name:
            logger.info("Away Teams page opened via 'T' key")
            return

        if visible_tab == tab_unselected_name:
            if not click_button_if_visible(
                "Away Teams Tab Unselected.jpg", img, screen_offset
            ):
                raise CaptureError("Away Teams Tab Unselected not clickable")  # ai: claude-opus-5-5 | 2026-11-06
            logger.info("clicked Away Teams Tab Unselected (after 'c' key)")
            time.sleep(0.3)
            return

        fresh = self.sc.capture(window)
        if fresh is not None:
            _log_near_misses(tab_images, fresh)

        # Last resort: navigate via home screen → Mission Button → Away Teams tab.
        # ai: claude-opus-5-5 | 2026-11-06
        self.sc.navigate_to_home_screen(window)

        img = self.sc.capture(window)
        if not click_button_if_visible(
            ["Mission Button.jpg", "Mission Button 2.jpg"], img, screen_offset
        ):
            raise CaptureTargetNotFound(
                "Mission Button not found — add Mission Button.jpg to app/screen_snippets/"
            )
        logger.info("clicked Mission Button")
        time.sleep(0.5)

        img = self.sc.capture(window)
        if not click_button_if_visible(tab_images, img, screen_offset):
            _log_near_misses(tab_images, img)
            raise CaptureTargetNotFound(  # ai: claude-opus-5-5 | 2026-11-06
                "Away Teams Tab (Un)selected not found — add Away Teams Tab Unselected.jpg to app/screen_snippets/"
            )
        logger.info("clicked Away Teams Tab")
        time.sleep(0.5)

    # Templates that confirm the Away Teams list is fully rendered.
    # "Away Teams List Indicator.jpg" only appears when missions are in-progress;
    # "Away Teams Refresh.jpg" is always present regardless of mission state.
    _LIST_READY_TEMPLATES = ["Away Teams List Indicator.jpg", "Away Teams Refresh.jpg"]
    # ai: claude-opus-5-5 | 2026-11-17
    _NEXT_TEMPLATE = "next.jpg"
    _COLLECT_TEMPLATE = "collect.jpg"
    # Order matters: when both buttons are on screen, NEXT wins, because it collects
    # this mission and opens the next finished one without going back to the list.
    _REPORT_BUTTON_TEMPLATES = [_NEXT_TEMPLATE, _COLLECT_TEMPLATE]

    def _collect_reports(self, window, screen_offset):
        """Click REPORT → COLLECT for all completed missions. Returns (reports_clicked, collected)."""
        reports_clicked = 0
        collected = 0
        while True:
            # Wait for the list to be fully rendered before looking for a REPORT button.
            # "Away Teams Tab Selected.jpg" appears as soon as the nav bar is visible,
            # which is before the list items have loaded — use the list indicator instead.
            matched, _ = wait_for_any_template(
                self._LIST_READY_TEMPLATES, self.sc, window, max_retries=20
            )
            if matched is None:
                logger.warning(
                    "Away Teams list not detected after all retries, stopping collect cycle"
                )
                fresh = self.sc.capture(window)
                if fresh is not None:
                    _log_near_misses(self._LIST_READY_TEMPLATES, fresh)
                break
            logger.debug("Away Teams list ready (matched: %s)", matched)

            img = self.sc.capture(window)
            if img is None:
                logger.warning(
                    "could not capture screenshot in collect loop — stopping"
                )
                break
            # ai: claude-sonnet-4-6 | 2026-06-26
            if not click_template_match_at(
                "Away Teams Report.jpg", img, screen_offset, index=0
            ):
                _log_near_misses(["Away Teams Report.jpg"], img)
                logger.info("no REPORT button visible — collect cycle complete")
                break
            reports_clicked += 1
            logger.info(f"clicked REPORT ({reports_clicked})")

            report_collected = self._collect_open_report(window, screen_offset)
            if report_collected == 0:
                logger.warning(
                    "neither NEXT nor COLLECT found after REPORT click — stopping"
                )
                break
            collected += report_collected
            # Loop back — list indicator wait at the top handles the remaining transition

        logger.info(f"{reports_clicked} report(s), {collected} collected")
        return reports_clicked, collected

    # ai: claude-opus-5-5 | 2026-11-17
    def _collect_open_report(self, window, screen_offset) -> int:
        """Collect from the open report panel, following NEXT through each finished mission.

        The panel shows COLLECT, or a green NEXT that collects this mission and opens the
        next finished one. Keeps clicking NEXT until only COLLECT is left, then clicks it,
        which returns to the list. Returns how many missions were collected (0 if no
        button appeared at all).
        """
        collect_first_delay = capture_cfg(
            "away_teams", "collect_first_delay", default=0.5
        )
        collect_retries = capture_cfg("away_teams", "collect_retries", default=16)
        collect_delay = capture_cfg("away_teams", "collect_delay", default=0.25)
        post_next_delay = capture_cfg("away_teams", "post_next_delay", default=1.0)
        post_collect_delay = capture_cfg(
            "away_teams", "post_collect_delay", default=2.0
        )

        collected = 0
        time.sleep(collect_first_delay)
        while True:
            clicked = wait_and_click_any(
                self._REPORT_BUTTON_TEMPLATES,
                self.sc,
                window,
                screen_offset,
                max_retries=collect_retries,
                delay=collect_delay,
            )
            if clicked is None:
                if collected:
                    # After a NEXT the game may have gone straight back to the list;
                    # the caller's list wait copes with either state.
                    logger.info("no NEXT/COLLECT after NEXT — returning to the list")
                return collected
            collected += 1
            if clicked == self._COLLECT_TEMPLATE:
                logger.info(f"clicked COLLECT ({collected} from this report)")
                time.sleep(post_collect_delay)
                return collected
            logger.info(f"clicked NEXT ({collected} from this report)")
            # Let the next mission's panel replace this one, so the old NEXT button
            # isn't matched (and clicked) again.
            time.sleep(post_next_delay)

    def _start_expeditions(self, window, screen_offset):
        """Start new expeditions via START → AUTO → START. Returns expeditions_started count."""
        expeditions_started = 0
        while True:
            matched, _ = wait_for_any_template(
                self._LIST_READY_TEMPLATES, self.sc, window, max_retries=20
            )
            if matched is None:
                logger.warning("Away Teams list not detected after all retries, stopping")
                fresh = self.sc.capture(window)
                if fresh is not None:
                    _log_near_misses(self._LIST_READY_TEMPLATES, fresh)
                break
            logger.debug("Away Teams list ready (matched: %s)", matched)

            time.sleep(0.5)
            img = self.sc.capture(window)
            if img is None:
                logger.warning(
                    "could not capture screenshot in expedition loop — stopping"
                )
                break

            # ai: claude-sonnet-4-6 | 2026-06-26
            if not click_template_match_at(
                "Away Teams Start Blue.jpg", img, screen_offset, index=-1
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
            time.sleep(2.0)

        return expeditions_started

    def capture_away_team_collect(self):
        """Navigate to Away Teams and collect all completed missions (REPORT → COLLECT only).
        Does not start new expeditions.
        """
        window = self._activate()  # ai: claude-opus-5-5 | 2026-11-06
        screen_offset = (window.left, window.top)
        self._navigate_to_away_teams(window, screen_offset)

        reports_clicked, collected = self._collect_reports(window, screen_offset)

        logger.info(
            f"done (collect only) — reports={reports_clicked}, collected={collected}"
        )
        return {
            "reports_clicked": reports_clicked,
            "collected": collected,
            "expeditions_started": 0,
        }

    def capture_away_team(self):
        """Navigate to Away Teams, collect all completed missions, then start new expeditions."""
        window = self._activate()  # ai: claude-opus-5-5 | 2026-11-06
        screen_offset = (window.left, window.top)
        self._navigate_to_away_teams(window, screen_offset)

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
