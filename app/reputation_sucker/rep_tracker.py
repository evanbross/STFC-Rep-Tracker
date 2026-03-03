import logging
import time

from app.database.status_entries_dao import StatusEntriesDAO
from app.reputation_sucker.image_to_rep import analyze_screenshot
from app.reputation_sucker.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class RepTrackerOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()
        self.stat_dao = StatusEntriesDAO(db)
        self.factions_dao = db.factions

    def capture_and_analyze(self):
        """
        Capture the current STFC window and analyze it for a single faction/points.
        """
        window = self.sc.get_stfc_window()
        if not window:
            logger.error("capture_and_analyze: STFC window not found.")
            return {"error": "STFC window not found"}
        logger.info(f"capture_and_analyze: Found STFC window: {window.title}")

        try:
            self.sc.activate_window(window)
            logger.error("capture_and_analyze: Success activating STFC window.")
        except Exception as e:
            logger.error(f"capture_and_analyze: Failed to activate STFC window: {e}")
            return {"error": "Could not activate STFC window"}

        try:
            filepath = self.sc.capture_window(window)
            logger.info(f"capture_and_analyze: Captured screenshot: {filepath}")
        except Exception as e:
            logger.error(f"capture_and_analyze: Failed to capture screen: {e}")
            return {"error": "Failed to capture screen"}

        # factions = self.factions_dao.get_all_factions()
        # faction_names = [f["name"] for f in factions]
        faction_names = self.factions_dao.get_faction_names()
        logger.info(f"capture_and_analyze: Faction names: {faction_names}")

        faction, points = analyze_screenshot(window, filepath, faction_names)

        return {"faction": faction, "points": points, "image_path": filepath}

    def track_all_factions(self):
        """
        Orchestrates the process of:
        1. Finding STFC window.
        2. Navigating to Faction Store.
        3. Iterating through each faction and capturing its reputation.
        4. Saving to database.
        """
        window = self.sc.get_stfc_window()
        if not window:
            logger.error("track_all_factions: STFC window not found.")
            return {"error": "STFC window not found"}

        if not self.sc.activate_window(window):
            logger.error("track_all_factions: Could not activate STFC window.")
            return {"error": "Could not activate STFC window"}

        if not self.sc.navigate_to_faction_store(window):
            logger.error("track_all_factions: Could not navigate to Faction Store.")
            return {"error": "Could not navigate to Faction Store"}

        # Load factions dynamically from database
        factions = self.factions_dao.get_all_factions()
        faction_names = [f["name"] for f in factions]
        total = len(faction_names)

        results = []
        for i, faction_name in enumerate(faction_names):
            logger.info(f"track_all_factions: Processing faction: {faction_name}")

            # Select the faction
            self.sc.select_faction_row(i, window, total_factions=total)

            # Capture and analyze
            filepath = self.sc.capture_window(window)
            detected_faction, points = analyze_screenshot(filepath, faction_names)

            if points is not None:
                # Use FACTION_NAMES[i] instead of detected_faction if they don't match,
                # but log it. Usually detected_faction should match.
                if detected_faction != faction_name:
                    logger.warning(
                        f"track_all_factions: Detected faction ({detected_faction}) does not match expected ({faction_name})"
                    )

                try:
                    entry = self.stat_dao.add_status_entry(faction_name, points)
                    results.append(
                        {
                            "faction": faction_name,
                            "points": points,
                            "status": "success",
                            "entry": entry,
                        }
                    )
                    logger.info(
                        f"track_all_factions: Successfully saved {faction_name}: {points}"
                    )
                except Exception as e:
                    results.append(
                        {
                            "faction": faction_name,
                            "points": points,
                            "status": "failed",
                            "error": str(e),
                        }
                    )
                    logger.error(
                        f"track_all_factions: Failed to save {faction_name} to database: {e}"
                    )
            else:
                results.append(
                    {
                        "faction": faction_name,
                        "status": "failed",
                        "error": "Could not extract points from screenshot",
                    }
                )
                logger.error(
                    f"track_all_factions: Could not extract points for {faction_name}"
                )

            # Small delay between factions
            time.sleep(0.5)

        return results
