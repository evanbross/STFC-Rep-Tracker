import logging
import os
import time
from datetime import datetime

import cv2
import easyocr
import numpy as np
import pyautogui
import pygetwindow as gw

logger = logging.getLogger(__name__)

_SNIPPETS_DIR = os.path.join(os.path.dirname(__file__), "..", "screen_snippets")
_BUTTON_MATCH_THRESHOLD = 0.85

_ocr_reader = None


def match_template(filename, img):
    """Returns (template, max_val, max_loc) or None if the file can't be loaded."""
    template_path = os.path.normpath(os.path.join(_SNIPPETS_DIR, filename))
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template image not found: {template_path}")
    template = cv2.imread(template_path)
    if template is None:
        return None
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return template, max_val, max_loc


def is_template_visible(filename, img):
    """Return True if the template image is found in img above the match threshold."""
    if not (match := match_template(filename, img)):
        return False
    _, max_val, _ = match
    return max_val >= _BUTTON_MATCH_THRESHOLD


def show_reticle(x, y, duration_ms=5000, radius=20):
    """Briefly flash a crosshair reticle at absolute screen position (x, y)."""
    import threading
    import tkinter as tk

    def _run():
        root = tk.Tk()
        root.overrideredirect(True)
        root.wm_attributes("-topmost", True)
        root.wm_attributes("-transparentcolor", "black")
        root.configure(bg="black")
        size = radius * 2 + 10
        offset = size // 2
        root.geometry(f"{size}x{size}+{x - offset}+{y - offset}")
        canvas = tk.Canvas(
            root, width=size, height=size, bg="black", highlightthickness=0
        )
        canvas.pack()
        cx = cy = size // 2
        canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius, outline="red", width=2
        )
        canvas.create_line(cx - radius, cy, cx - 4, cy, fill="red", width=2)
        canvas.create_line(cx + 4, cy, cx + radius, cy, fill="red", width=2)
        canvas.create_line(cx, cy - radius, cx, cy - 4, fill="red", width=2)
        canvas.create_line(cx, cy + 4, cx, cy + radius, fill="red", width=2)
        root.after(duration_ms, root.destroy)
        root.mainloop()

    threading.Thread(target=_run, daemon=True).start()


def is_button_visible(button_filename, img, screen_offset=(0, 0), on_found=None):
    """Returns (template, max_val, max_loc) if the button is visible in img, else None."""
    if not (match := match_template(button_filename, img)):
        return None

    template, max_val, max_loc = match
    if max_val < _BUTTON_MATCH_THRESHOLD:
        return None

    if on_found:
        on_found()
    return match


def click_button_if_visible(button_filename, img, screen_offset=(0, 0), on_found=None):
    """If the button template image is visible in img, click it. Returns True if clicked.

    on_found: optional callable invoked with (center_x, center_y) after the click.
    """
    if not (match := is_button_visible(button_filename, img, screen_offset)):
        return False
    template, max_val, max_loc = match

    th, tw = template.shape[:2]
    center_x = screen_offset[0] + max_loc[0] + tw // 2
    center_y = screen_offset[1] + max_loc[1] + th // 2

    logger.info(
        f"Clicking {button_filename} button at {center_x}, {center_y}, match % {max_val:.2f}"
    )
    # _show_reticle(center_x, center_y)
    pyautogui.click(center_x, center_y)
    if on_found:
        on_found(center_x, center_y)
    return True


def get_reader():
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


class ScreenCapture:
    def __init__(self, output_dir="Screenshots", snippets_dir="app/screen_snippets"):
        self.output_dir = output_dir
        self.snippets_dir = snippets_dir
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
        except Exception as e:
            logger.error(f"Failed to create output directory {self.output_dir}: {e}")

        # Relative coordinates (0.0 to 1.0) for buttons within the STFC window
        # These may need adjustment depending on the game's UI layout
        self.factions_button_rel = (0.04, 0.35)  # Typical Factions icon in sidebar
        self.federation_button_rel = (0.22, 0.05)  # Top item in faction list

        # Window title search
        self.possible_titles = ["Star Trek Fleet Command", "STFC"]

    def get_stfc_window(self):
        """Finds and returns the STFC window, or None if not found."""
        try:
            for title in self.possible_titles:
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    logger.info(f"Found STFC window: {title}")
                    return windows[0]
        except Exception as e:
            logger.error(f"Error while searching for STFC window: {e}")
        return None

    def activate_window(self, window):
        """Brings the window to the front."""
        import win32api
        import win32con
        import win32gui
        import win32process

        if not window:
            raise Exception("activate_window: Window is None")

        hwnd = window._hWnd

        if win32gui.IsIconic(hwnd):
            logger.info(f"activate_window: Restoring minimized window: {window.title}")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)

        # Windows blocks focus changes from background processes unless the calling
        # thread is attached to the current foreground thread's input queue.
        fg_hwnd = win32gui.GetForegroundWindow()
        fg_thread = win32process.GetWindowThreadProcessId(fg_hwnd)[0]
        app_thread = win32api.GetCurrentThreadId()

        if fg_thread != app_thread:
            win32process.AttachThreadInput(fg_thread, app_thread, True)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            win32process.AttachThreadInput(fg_thread, app_thread, False)
        else:
            win32gui.SetForegroundWindow(hwnd)

        logger.info(f"activate_window: Activated window: {window.title}")
        time.sleep(1.0)

    def get_and_activate_window(self):
        """Find the STFC window and bring it to the foreground.

        Returns the window object on success.
        Raises RuntimeError if the window cannot be found or activated.
        """
        window = self.get_stfc_window()
        if not window:
            raise RuntimeError("STFC window not found")
        logger.info(f"get_and_activate_window: Found STFC window: {window.title}")
        self.activate_window(window)
        return window

    def is_faction_store_open(self, window_region):
        """Checks if the faction store is already open using a header snippet."""
        result = (
            self.find_image_on_screen("Faction Store Header.jpg", region=window_region)
            is not None
        )
        logger.info(f"Faction Store is {'open' if result else 'closed'}")
        return result

    def navigate_to_faction_store(self, window):
        """Navigates to the faction store from the main screen."""
        left, top, width, height = window.left, window.top, window.width, window.height
        window_region = (left, top, width, height)

        if self.is_faction_store_open(window_region):
            logger.info("Faction store already open.")
            return True

        logger.info("Navigating to faction store...")
        # 1. Click on Factions button
        if not self.click_image("FactionsButton.png", region=window_region):
            fx, fy = self.factions_button_rel
            f_abs_x = left + int(width * fx)
            f_abs_y = top + int(height * fy)
            logger.info(
                f"Clicking Factions button (fallback) at ({f_abs_x}, {f_abs_y})"
            )
            pyautogui.click(f_abs_x, f_abs_y)

        time.sleep(2.0)  # Wait for navigation

        # Verify it opened
        if self.is_faction_store_open(window_region):
            return True

        logger.warning("Failed to verify Faction Store is open.")
        return False

    def select_faction_row(self, faction_index, window, total_factions=10):
        """Clicks on a faction row based on its index (0-based)."""
        left, top, width, height = window.left, window.top, window.width, window.height

        # The faction list is on the left.
        num_factions = total_factions
        row_height_rel = 1.0 / num_factions

        # Click in the middle of the row, left side
        target_rel_x = 0.22  # roughly horizontal center of the left panel
        target_rel_y = (faction_index + 0.5) * row_height_rel

        abs_x = left + int(width * target_rel_x)
        abs_y = top + int(height * target_rel_y)

        logger.info(
            f"Selecting faction at index {faction_index} (coords: {abs_x}, {abs_y})"
        )
        pyautogui.click(abs_x, abs_y)
        time.sleep(1.0)  # Wait for UI update

    def capture_window(self, window):
        """Captures the window region and returns the filepath."""
        left, top, width, height = window.left, window.top, window.width, window.height
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")

        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        screenshot.save(filepath)
        logger.debug(f"Screenshot saved to {filepath}")
        return filepath

    def capture_window_mss(self, window):
        """
        Captures the window region using mss.
        mss is faster than pyautogui and handles multi-monitor setups correctly,
        but requires the window to be visible (not covered by other windows).
        """
        import mss

        left, top, width, height = window.left, window.top, window.width, window.height
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")

        monitor = {"left": left, "top": top, "width": width, "height": height}
        with mss.mss() as sct:
            img = sct.grab(monitor)
            img_np = np.array(img)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
            cv2.imwrite(filepath, img_bgr)

        logger.info(f"Screenshot (mss) saved to {filepath}")
        return filepath

    def capture_window_dxcam(self, window):
        """
        Captures the window region using dxcam (DirectX Desktop Duplication API).
        Very fast and works with GPU-rendered/DirectX content, but requires the
        window to be visible and on screen (not minimized or fully occluded).
        """
        import dxcam

        left, top, width, height = window.left, window.top, window.width, window.height
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")

        region = (left, top, left + width, top + height)
        camera = dxcam.create(output_color="BGR")
        try:
            frame = camera.grab(region=region)
            if frame is None:
                logger.warning(
                    "dxcam returned None — window may be occluded or off-screen"
                )
                return None
            cv2.imwrite(filepath, frame)
        finally:
            del camera

        logger.info(f"Screenshot (dxcam) saved to {filepath}")
        return filepath

    def capture_window_hidden(self, window):
        """
        Captures the window using the Win32 PrintWindow API.
        Works even when the window is occluded or partially off-screen.
        Requires pywin32 (pip install pywin32).
        """
        import win32gui
        import win32ui
        from ctypes import windll

        # PW_RENDERFULLCONTENT (0x2) captures hardware-accelerated / DX content
        PW_CLIENTONLY = 0x1
        PW_RENDERFULLCONTENT = 0x2

        hwnd = window._hWnd
        left, top, width, height = window.left, window.top, window.width, window.height

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        result = windll.user32.PrintWindow(
            hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
        )
        if not result:
            logger.warning("PrintWindow returned 0 — image may be blank")

        bmp_str = save_bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmp_str, dtype=np.uint8).reshape(height, width, 4)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")
        cv2.imwrite(filepath, img_bgr)
        logger.info(f"Screenshot (PrintWindow) saved to {filepath}")
        return filepath

    def find_image_on_screen(self, template_filename, region=None, threshold=0.8):
        """
        Takes a screenshot (of a region if specified), searches for the template image using OpenCV,
        and returns the (x, y) center coordinates of the best match if it exceeds the threshold.
        """
        try:
            # 1. Capture the screenshot
            screenshot = pyautogui.screenshot(region=region)
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

            # 2. Load the template
            template_path = os.path.join(self.snippets_dir, template_filename)
            if not os.path.exists(template_path):
                logger.error(f"Template image not found: {template_path}")
                return None

            template = cv2.imread(template_path)
            if template is None:
                logger.error(f"Failed to load template image: {template_path}")
                return None

            # 3. Perform template matching
            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                logger.info(
                    f"Found match for {template_filename} with confidence {max_val:.2f}"
                )

                # Get coordinates relative to the screenshot/region
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2

                # Adjust if region was used
                if region:
                    center_x += region[0]
                    center_y += region[1]

                return (center_x, center_y)
            else:
                logger.info(
                    f"Could not find {template_filename} on screen (max confidence: {max_val:.2f})"
                )
                return None
        except Exception as e:
            logger.error(f"Error in find_image_on_screen: {e}", exc_info=True)
            return None

    def click_image(self, template_filename, region=None, threshold=0.8):
        """
        Locates an image on screen and clicks it.
        """
        coords = self.find_image_on_screen(template_filename, region, threshold)
        if coords:
            logger.info(f"Clicking {template_filename} at {coords}")
            pyautogui.click(coords[0], coords[1])
            return True
        return False
