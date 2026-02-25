import pyautogui
import pygetwindow as gw
import os
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScreenCapture:
    def __init__(self, output_dir="Screenshots"):
        self.output_dir = output_dir
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
        except Exception as e:
            logger.error(f"Failed to create output directory {self.output_dir}: {e}")
        
        # Relative coordinates (0.0 to 1.0) for buttons within the STFC window
        # These may need adjustment depending on the game's UI layout
        self.factions_button_rel = (0.04, 0.35)  # Typical Factions icon in sidebar
        self.federation_button_rel = (0.22, 0.05) # Top item in faction list

    def capture_factions_screen(self):
        """
        Attempts to find the STFC window, bring it to front, 
        navigate to the Federation faction screen,
        and take a screenshot of just that window.
        """
        # Possible window titles for STFC
        possible_titles = ["Star Trek Fleet Command", "STFC"]
        
        target_window = None
        try:
            for title in possible_titles:
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    # Assuming the first match is the correct one
                    target_window = windows[0]
                    break
        except Exception as e:
            logger.error(f"Error while searching for STFC window: {e}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")
        
        try:
            if target_window:
                logger.info(f"STFC window found: {target_window.title}")
                # Bring window to front
                try:
                    if target_window.isMinimized:
                        target_window.restore()
                    target_window.activate()
                except Exception as e:
                    logger.warning(f"Could not activate STFC window: {e}")

                # Give it a moment to come to focus
                time.sleep(1.0)
                
                left, top, width, height = target_window.left, target_window.top, target_window.width, target_window.height
                
                # Check for zero size window
                if width <= 0 or height <= 0:
                    raise ValueError(f"Invalid window dimensions: {width}x{height}")

                # 1. Click on Factions button
                fx, fy = self.factions_button_rel
                f_abs_x = left + int(width * fx)
                f_abs_y = top + int(height * fy)
                logger.info(f"Clicking Factions button at ({f_abs_x}, {f_abs_y})")
                pyautogui.click(f_abs_x, f_abs_y)
                time.sleep(1.5) # Wait for navigation
                
                # 2. Click on Federation button
                fed_x, fed_y = self.federation_button_rel
                fed_abs_x = left + int(width * fed_x)
                fed_abs_y = top + int(height * fed_y)
                logger.info(f"Clicking Federation button at ({fed_abs_x}, {fed_abs_y})")
                pyautogui.click(fed_abs_x, fed_abs_y)
                time.sleep(1.5) # Wait for screen to update
                
                # Capture the window region
                screenshot = pyautogui.screenshot(region=(left, top, width, height))
            else:
                logger.warning("STFC window not found. Capturing whole screen as fallback.")
                screenshot = pyautogui.screenshot()
            
            screenshot.save(filepath)
            logger.info(f"Screenshot saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error during screen capture or navigation: {e}", exc_info=True)
            return None
