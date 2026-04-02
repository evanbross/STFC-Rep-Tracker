import logging

from app.screen_processing.screen_capture import (
    ScreenCapture,
    click_button_if_visible,
    wait_and_click_any,
)

logger = logging.getLogger(__name__)


class TerritoryCaptureOrchestrator:
    def __init__(self, db):
        self.sc = ScreenCapture()

    def navigate_to_territory_capture(self):
        """Navigate to home, click Alliance, then click Territory.

        Returns a dict with {"success": True} or {"error": message}.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(str(e))
            return {"error": str(e)}

        screen_offset = (window.left, window.top)

        try:
            self.sc.navigate_to_home_screen(window)
        except RuntimeError as e:
            logger.error(f"Could not reach home screen: {e}")
            return {"error": str(e)}

        img = self.sc.capture(window)
        if not click_button_if_visible(
            ["Alliance Button 1.jpg", "Alliance Button 2.jpg"], img, screen_offset
        ):
            logger.error("Alliance Button not found on home screen")
            return {
                "error": "Alliance Buttons not found — add Alliance Button.jpg to app/screen_snippets/"
            }
        logger.info("clicked Alliance Button")

        if not wait_and_click_any(
            ["Territory Button 1.jpg", "Territory Button 2.jpg"],
            self.sc,
            window,
            screen_offset,
        ):
            logger.error("Territory Button not found after clicking Alliance")
            return {
                "error": "Territory Button not found — add Territory Button.jpg to app/screen_snippets/"
            }
        logger.info("clicked Territory Button")

        return {"success": True}
