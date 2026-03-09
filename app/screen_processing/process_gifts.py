import logging

from app.screen_processing.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class GiftsOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()

    def capture_gifts(self):
        """
        Activate the STFC window and capture the Gifts screen.
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