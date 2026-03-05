import logging

from app.screen_processing.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class AwayTeamOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()

    def capture_away_team(self):
        """
        Activate the STFC window and capture the Away Team screen.
        Navigation logic to be implemented.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(f"capture_away_team: {e}")
            return {"error": str(e)}

        filepath = self.sc.capture_window(window)
        logger.info(f"capture_away_team: Captured screenshot: {filepath}")
        return {"image_path": filepath}