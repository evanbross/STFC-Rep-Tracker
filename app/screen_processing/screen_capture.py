import logging
import os
import threading
import time
from datetime import datetime

import cv2
import easyocr
import numpy as np
import pyautogui
import pygetwindow as gw

from app.app_config import capture_cfg

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SNIPPETS_DIR = os.path.join(
    _PROJECT_ROOT, capture_cfg("snippets_dir", default="app/screen_snippets")
)
_BUTTON_MATCH_THRESHOLD = capture_cfg("button_match_threshold", default=0.85)

_ocr_reader = None
_ocr_reader_lock = threading.Lock()

# Special-key VK code map for keys that can't be derived from ord().
_VK_SPECIAL = {
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    'esc': 0x1B, 'escape': 0x1B,
    'enter': 0x0D, 'return': 0x0D,
    'space': 0x20,
    'tab': 0x09,
    'backspace': 0x08,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
}
_KEYEVENTF_KEYUP = 0x0002


def _send_key(key):
    """Send a keydown+keyup pair using low-level keybd_event.

    Works with games that ignore pyautogui's high-level SendInput/Unicode approach.
    Single character keys (letters, digits) are converted via ord(); special keys
    are looked up in _VK_SPECIAL.
    """
    import ctypes
    key_lower = key.lower()
    if key_lower in _VK_SPECIAL:
        vk = _VK_SPECIAL[key_lower]
    elif len(key) == 1:
        vk = ord(key.upper())
    else:
        logger.warning(f"_send_key: unknown key '{key}', falling back to pyautogui")
        pyautogui.press(key)
        return
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def match_template(filename, img, crop_h_frac=1.0):
    """Run template matching for filename against img.

    Returns (template, max_val, max_loc), or None if the template image could not be loaded.
    Raises FileNotFoundError if the snippet file does not exist.

    crop_h_frac: if < 1.0, only the top fraction of the template height is used for
    matching. The full (uncropped) template is still returned so callers can compute
    click positions based on the real button size. Use this for snippets whose bottom
    portion contains text that changes over time (e.g. reputation tier labels).
    """
    template_path = os.path.normpath(os.path.join(_SNIPPETS_DIR, filename))
    if not os.path.isfile(template_path):
        msg = f"Template image not found: {template_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    template = cv2.imread(template_path)
    if template is None:
        return None

    match_tmpl = template
    if crop_h_frac < 1.0:
        crop_h = max(1, int(template.shape[0] * crop_h_frac))
        match_tmpl = template[:crop_h, :]
    result = cv2.matchTemplate(img, match_tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return (
        template,
        max_val,
        max_loc,
    )  # always return full template for size/click calcs


def is_template_visible(filename, img):
    """Return True if the template image is found in img above the match threshold."""
    if not filename:
        return False
    if not (match := match_template(filename, img)):
        return False
    _, max_val, _ = match
    return max_val >= _BUTTON_MATCH_THRESHOLD


def show_reticle(x, y, duration_ms=5000, radius=20):
    """Flash a crosshair at absolute screen position (x, y) for debug purposes."""
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


def is_button_visible(
    button_filenames,
    img,
    screen_offset=(0, 0),
    on_found=None,
    crop_h_frac=1.0,
    threshold=None,
):
    """Return (template, max_val, max_loc) if any button in button_filenames is visible in img, else None.

    button_filenames may be a single filename string or a list of filenames.
    Each is tried in order; the first match above threshold is returned.
    Logs a distinct message for missing snippet files vs. a file that exists but isn't on screen.
    """
    if threshold is None:
        threshold = _BUTTON_MATCH_THRESHOLD
    if isinstance(button_filenames, str):
        button_filenames = [button_filenames]
    for filename in button_filenames:
        template_path = os.path.normpath(os.path.join(_SNIPPETS_DIR, filename))
        if not os.path.isfile(template_path):
            logger.error(f"Snippet file missing: {template_path}")
            continue
        match = match_template(filename, img, crop_h_frac=crop_h_frac)
        if not match:
            continue
        template, max_val, max_loc = match
        if max_val >= threshold:
            if on_found:
                on_found()
            return match
        logger.debug(
            f"'{filename}' exists but not visible on screen (score: {max_val:.2f}, threshold: {threshold:.2f})"
        )
    return None


def click_button_if_visible(
    button_filenames,
    img,
    screen_offset=(0, 0),
    on_found=None,
    crop_h_frac=1.0,
    threshold=None,
):
    """Click the button if its template is visible in img. Returns True if clicked.

    button_filenames may be a single filename string or a list of filenames.
    on_found: optional callable invoked with (center_x, center_y) after the click.
    crop_h_frac: fraction of template height used for matching; full height used for
    click position. Useful for faction buttons whose tier label changes over time.
    threshold: match confidence required; defaults to _BUTTON_MATCH_THRESHOLD.
    """
    if not (
        match := is_button_visible(
            button_filenames,
            img,
            screen_offset,
            crop_h_frac=crop_h_frac,
            threshold=threshold,
        )
    ):
        return False
    template, max_val, max_loc = match

    th, tw = template.shape[:2]
    center_x = screen_offset[0] + max_loc[0] + tw // 2
    center_y = screen_offset[1] + max_loc[1] + th // 2

    logger.debug(
        f"Clicking {button_filenames} button at {center_x}, {center_y}, match % {max_val:.2f}"
    )
    pyautogui.click(center_x, center_y)
    if on_found:
        on_found(center_x, center_y)
    return True


def wait_for_template(filename, sc, window, max_retries=None, delay=None):
    """Poll until filename is visible. Returns the image it was found in, or None.

    Captures a fresh screenshot on each attempt. If the template does not appear
    within max_retries attempts, logs a warning and returns None.
    """
    if max_retries is None:
        max_retries = capture_cfg("screen_wait_retries", default=8)
    if delay is None:
        delay = capture_cfg("screen_wait_delay", default=0.25)
    for _ in range(max_retries):
        img_path = sc.capture_window(window, delay=delay)
        img = cv2.imread(img_path)
        if img is not None and is_template_visible(filename, img):
            return img
    logger.warning(f"'{filename}' not detected after {max_retries} attempts")
    return None


def wait_for_any_template(filenames, sc, window, max_retries=None, delay=None):
    """Poll until any template in filenames is visible.

    Returns (matched_filename, img) for the first template found, or (None, None)
    if none appear within max_retries attempts.
    """
    logger.debug(f"Waiting for any of: {filenames!r}")
    if max_retries is None:
        max_retries = capture_cfg("screen_wait_retries", default=8)
    if delay is None:
        delay = capture_cfg("screen_wait_delay", default=0.25)
    for _ in range(max_retries):
        img_path = sc.capture_window(window, delay=delay)
        img = cv2.imread(img_path)
        if img is None:
            continue
        for filename in filenames:
            if is_template_visible(filename, img):
                return filename, img
    logger.warning(f"None of {filenames!r} detected after {max_retries} attempts")
    return None, None


def wait_and_click(
    filename, sc, window, screen_offset=(0, 0), max_retries=None, delay=None
):
    """Wait for filename to appear then click it. Returns True if clicked."""
    img = wait_for_template(filename, sc, window, max_retries=max_retries, delay=delay)
    if img is None:
        return False
    return click_button_if_visible(filename, img, screen_offset)


def wait_and_click_any(
    filenames, sc, window, screen_offset=(0, 0), max_retries=None, delay=None
):
    """Wait for any template in filenames to appear, then click the first one visible.

    Returns the filename that was clicked, or None if none appeared within the retry limit.
    """
    matched, img = wait_for_any_template(
        filenames, sc, window, max_retries=max_retries, delay=delay
    )
    if matched is None:
        return None
    click_button_if_visible(matched, img, screen_offset)
    return matched


def get_reader():
    global _ocr_reader
    if _ocr_reader is None:
        with _ocr_reader_lock:
            if _ocr_reader is None:
                _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


class ScreenCapture:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.output_dir = capture_cfg("screenshots_dir", default="Screenshots")
        self.snippets_dir = capture_cfg("snippets_dir", default="app/screen_snippets")
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
        except Exception as e:
            logger.error(f"Failed to create output directory {self.output_dir}: {e}")

        self.possible_titles = capture_cfg(
            "window_titles", default=["Star Trek Fleet Command", "STFC"]
        )

    def get_stfc_window(self):
        """Find and return the STFC window, or None if not found."""
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
        """Bring the window to the foreground.

        Uses the ALT key trick to bypass Windows focus-stealing prevention, which
        otherwise blocks SetForegroundWindow when called from a background thread
        (e.g. a Flask request handler where the browser holds foreground focus).
        """
        import ctypes
        import win32con
        import win32gui

        if not window:
            raise Exception("activate_window: Window is None")

        hwnd = window._hWnd

        if win32gui.IsIconic(hwnd):
            logger.info(f"Restoring minimized window: {window.title}")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)

        # Briefly simulate ALT keydown+up. This makes Windows believe the calling
        # thread has UI rights, allowing SetForegroundWindow to succeed from any thread.
        ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            logger.warning(
                f"SetForegroundWindow failed, falling back to SwitchToThisWindow: {e}"
            )
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)

        logger.debug(f"Activated window: {window.title}")
        time.sleep(0.25)

    def get_and_activate_window(self):
        """Find the STFC window and bring it to the foreground.

        Returns the window object. Raises RuntimeError if not found.
        """
        window = self.get_stfc_window()
        if not window:
            raise RuntimeError("STFC window not found")
        logger.info(f"Found STFC window: {window.title}")
        self.activate_window(window)
        return window

    def capture_window(self, window, delay=None, activate=False):
        """Capture the window region and return the saved filepath.

        activate: bring the window to the foreground before capturing (includes a
        1s sleep). Only needed on the first capture; leave False during polling
        loops where the window is already in focus.
        """
        if activate:
            self.activate_window(window)

        left, top, width, height = window.left, window.top, window.width, window.height
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")

        if delay:
            time.sleep(delay)
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        screenshot.save(filepath)
        logger.debug(f"Screenshot saved to {filepath}")
        return filepath

    # def capture_window_mss(self, window):
    #     """Capture the window using mss (faster than pyautogui, handles multi-monitor)."""
    #     import mss
    #
    #     left, top, width, height = window.left, window.top, window.width, window.height
    #     timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    #     filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")
    #
    #     monitor = {"left": left, "top": top, "width": width, "height": height}
    #     with mss.mss() as sct:
    #         img = sct.grab(monitor)
    #         img_np = np.array(img)
    #         img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
    #         cv2.imwrite(filepath, img_bgr)
    #
    #     logger.info(f"Screenshot (mss) saved to {filepath}")
    #     return filepath

    # def capture_window_dxcam(self, window):
    #     """Capture the window using dxcam (DirectX Desktop Duplication API)."""
    #     import dxcam
    #
    #     left, top, width, height = window.left, window.top, window.width, window.height
    #     timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    #     filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")
    #
    #     region = (left, top, left + width, top + height)
    #     camera = dxcam.create(output_color="BGR")
    #     try:
    #         frame = camera.grab(region=region)
    #         if frame is None:
    #             logger.warning(
    #                 "dxcam returned None — window may be occluded or off-screen"
    #             )
    #             return None
    #         cv2.imwrite(filepath, frame)
    #     finally:
    #         del camera
    #
    #     logger.info(f"Screenshot (dxcam) saved to {filepath}")
    #     return filepath

    def find_image_on_screen(self, template_filename, region=None, threshold=0.8):
        """Search for template_filename in a screenshot and return its center (x, y), or None."""
        try:
            screenshot = pyautogui.screenshot(region=region)
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

            template_path = os.path.join(self.snippets_dir, template_filename)
            if not os.path.exists(template_path):
                logger.error(f"Template image not found: {template_path}")
                return None

            template = cv2.imread(template_path)
            if template is None:
                logger.error(f"Failed to load template image: {template_path}")
                return None

            res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                logger.info(
                    f"Found match for {template_filename} with confidence {max_val:.2f}"
                )
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
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
            logger.error(f"{e}", exc_info=True)
            return None

    def click_image(self, template_filename, region=None, threshold=0.8):
        """Locate template_filename on screen and click it. Returns True if clicked."""
        coords = self.find_image_on_screen(template_filename, region, threshold)
        if coords:
            logger.info(f"Clicking {template_filename} at {coords}")
            pyautogui.click(coords[0], coords[1])
            return True
        return False

    def click_center_and_press(self, window, key):
        """Click the centre of the window then send a keypress."""
        center_x = window.left + window.width // 2
        center_y = window.top + window.height // 2
        self.activate_window(window)
        pyautogui.click(center_x, center_y)
        logger.debug(f"Clicked window centre ({center_x}, {center_y})")
        time.sleep(0.1)
        _send_key(key)
        logger.debug(f"Pressed {key}")
        time.sleep(0.5)

    def press_key(self, window, key):
        """Send a keypress to the STFC window."""
        self.activate_window(window)
        _send_key(key)
        logger.debug(f"Sent {key} keypress to STFC window")
        time.sleep(0.5)

    # def navigate_to_home_screen_key(self, window):
    #     """Send the F2 keypress to the STFC window to navigate to the home screen."""
    #     self.activate_window(window)
    #     pyautogui.press("f2")
    #     logger.debug("Sent F2 keypress to STFC window")
    #     time.sleep(0.5)

    # def navigate_to_home_screen(
    #             self,
    #             window,
    #             target_templates=None,
    #             nav_buttons=None,
    #             busy_templates=None,
    #             max_retries=None,
    #             wait_after_click=None,
    #             delay=0,
    #     ):
    #         #return self.navigate_to_home_screen_key(window)
    #         return self.navigate_to_home_screen_graphics(window,
    #                                                      target_templates,
    #                                                      nav_buttons,
    #                                                      busy_templates,
    #                                                      max_retries,
    #                                                      wait_after_click,
    #                                                      delay)

    def navigate_to_home_screen(
        self,
        window,
        target_templates=None,
        nav_buttons=None,
        busy_templates=None,
        max_retries=None,
        wait_after_click=None,
        delay=0,
    ):
        """Loop until a target template is visible, clicking nav buttons each iteration.

        Checks target_templates first (success), then busy_templates (wait and retry),
        then clicks the first visible nav button. Raises RuntimeError if the target is
        not reached within max_retries attempts.
        """
        press_key = capture_cfg("navigation", "press_key", default="f4")

        screen_offset = (window.left, window.top)
        if target_templates is None:
            target_templates = [
                "Home Screen Buttons 1.jpg",
                "Home Screen Buttons 2.jpg",
                "Home Screen Buttons 3.jpg",
                "Home Screen Buttons 4.jpg",
            ]
        if nav_buttons is None:
            nav_buttons = [
                "TopLeftBackArrow.jpg",
                "Nav Left Arrow Mission Screen.jpg",
                "collect.jpg",
                "Done.jpg",
            ]
        busy_templates = busy_templates or ["STFC busy screen.jpg"]
        if max_retries is None:
            max_retries = capture_cfg("navigation", "max_retries", default=8)
        if wait_after_click is None:
            wait_after_click = capture_cfg(
                "navigation", "wait_after_click", default=1.0
            )

        for attempt in range(1, max_retries + 1):
            img_path = self.capture_window(window)
            img = cv2.imread(img_path)
            if img is None:
                logger.warning(
                    f"could not read screenshot (attempt {attempt}/{max_retries})"
                )
                time.sleep(0.5)
                continue

            for template in target_templates:
                if is_template_visible(template, img):
                    logger.info(
                        f"reached target ({template}) after {attempt} attempt(s)"
                    )
                    if delay:
                        time.sleep(delay)
                    return img

            logger.info(f"not on home screen (attempt {attempt}/{max_retries})")

            for template in busy_templates:
                if is_template_visible(template, img):
                    logger.info(f"busy screen detected ({template}), waiting...")
                    time.sleep(capture_cfg("navigation", "busy_wait", default=1.5))
                    break
            else:
                for button in nav_buttons:
                    if click_button_if_visible(button, img, screen_offset):
                        logger.info(f"clicked {button}, waiting {wait_after_click}s")
                        time.sleep(wait_after_click)
                        break
                else:
                    logger.warning(
                        f"no known navigation buttons visible (attempt {attempt}/{max_retries})"
                    )

        raise RuntimeError(f"target screen not reached after {max_retries} attempts")
