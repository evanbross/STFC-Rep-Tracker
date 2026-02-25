import pyautogui
import os
import time
from datetime import datetime

class ScreenCapture:
    def __init__(self, output_dir="Screenshots"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def capture_factions_screen(self):
        """
        Attempts to find the STFC window, bring it to front, 
        and take a screenshot.
        """
        # This is a simplified version for now
        # Ideally we'd use pygetwindow to find the specific app
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")
        
        try:
            # Capture the whole primary screen
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            return filepath
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None
