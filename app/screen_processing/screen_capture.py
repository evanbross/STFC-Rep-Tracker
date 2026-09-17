# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# LICENSE: Personal Use Only
# This source code is made available for personal, non-commercial use only.
# You may read, study, and run this code for personal purposes.
# You may NOT:
#   - Use this code, in whole or in part, in any commercial product or service
#   - Sell, sublicense, or otherwise monetize this code or derivatives of it
#   - Redistribute this code without explicit written permission from ZombieTech LLC
#
# No warranty is provided, express or implied. Use at your own risk.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import logging
import os
import queue
import threading
import time
from datetime import datetime, UTC
from typing import Any

import cv2
import easyocr
import numpy as np
import pyautogui
import pygetwindow as gw

from app.app_config import capture_cfg

# pygetwindow returns Win32Window on Windows. Typed as Any since stubs vary by platform.
_Window = Any

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SNIPPETS_DIR = os.path.join(
    _PROJECT_ROOT, capture_cfg("snippets_dir", default="app/screen_snippets")
)
_BUTTON_MATCH_THRESHOLD = capture_cfg("button_match_threshold", default=0.85)


def get_snippets_dir() -> str:
    """Return the absolute path to the configured snippets directory."""
    return _SNIPPETS_DIR

_ocr_reader = None
_ocr_reader_lock = threading.Lock()

# --- Template image cache ---
# Maps absolute template path -> loaded BGR numpy array.
# Populated lazily on first use; entries never expire because snippet files
# don't change while the app is running.
_template_cache: dict = {}


def _load_template(template_path: str) -> np.ndarray | None:
    """Return the template image for template_path, using the in-memory cache.

    Falls back to cv2.imread on every call when performance.template_cache is
    false (useful if you are actively replacing snippet files mid-run).
    Returns None if the file cannot be read.
    """
    if not capture_cfg("performance", "template_cache", default=True):
        return cv2.imread(template_path)
    img = _template_cache.get(template_path)
    if img is None:
        img = cv2.imread(template_path)
        if img is not None:
            _template_cache[template_path] = img
    return img


# --- Write-behind screenshot thread ---
# When capture_mode == "memory" and write_behind == true, captured frames are
# pushed here and saved to disk asynchronously so the capture path stays fast.
_write_queue: queue.Queue | None = None
_write_queue_lock = threading.Lock()


def _write_worker(q: queue.Queue) -> None:
    """Background daemon: pop (img_bgr, filepath) pairs from q and write them."""
    while True:
        item = q.get()
        if item is None:
            break
        img_bgr, filepath = item
        try:
            cv2.imwrite(filepath, img_bgr)
        except Exception as e:
            logger.warning(f"write-behind: failed to save {filepath}: {e}")
        finally:
            q.task_done()


def _get_write_queue() -> queue.Queue:
    """Return the write-behind queue, starting the worker thread on first call."""
    global _write_queue
    if _write_queue is None:
        with _write_queue_lock:
            if _write_queue is None:
                max_size = capture_cfg(
                    "performance", "write_behind_queue_size", default=20
                )
                q: queue.Queue = queue.Queue(maxsize=int(max_size))
                t = threading.Thread(
                    target=_write_worker,
                    args=(q,),
                    daemon=True,
                    name="screenshot-write-behind",
                )
                t.start()
                _write_queue = q
    return _write_queue


# Special-key VK code map for keys that can't be derived from ord().
_VK_SPECIAL = {
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "esc": 0x1B,
    "escape": 0x1B,
    "enter": 0x0D,
    "return": 0x0D,
    "space": 0x20,
    "tab": 0x09,
    "backspace": 0x08,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
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


def match_template(
    filename: str,
    img: np.ndarray,
    crop_h_frac: float = 1.0,
) -> tuple[np.ndarray, float, tuple[int, int]] | None:
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

    template = _load_template(template_path)
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


def find_all_template_matches(
    filename: str,
    img,
    threshold: float | None = None,
) -> list[tuple[int, int, int, int]]:
    """Return (x, y, w, h) for every non-overlapping match of filename in img.

    Iteratively finds the best match, records it, then zeroes out a region
    around it so the next iteration finds the next-best distinct location.
    Results are sorted top-to-bottom by y coordinate.

    Raises FileNotFoundError if the template file does not exist on disk.
    Returns an empty list if the image cannot be loaded.
    """
    if threshold is None:
        threshold = _BUTTON_MATCH_THRESHOLD

    template_path = os.path.normpath(os.path.join(_SNIPPETS_DIR, filename))
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template image not found: {template_path}")

    template = _load_template(template_path)
    if template is None:
        return []

    th, tw = template.shape[:2]
    score_map = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    matches: list[tuple[int, int, int, int]] = []

    while True:
        _, max_val, _, max_loc = cv2.minMaxLoc(score_map)
        if max_val < threshold:
            break
        x, y = max_loc
        matches.append((x, y, tw, th))
        # Suppress the matched region so the next call finds a different peak.
        # Blank a window 1.5× the template size centred on the match.
        x1 = max(0, x - tw // 2)
        y1 = max(0, y - th // 2)
        x2 = min(score_map.shape[1], x + tw + tw // 2)
        y2 = min(score_map.shape[0], y + th + th // 2)
        score_map[y1:y2, x1:x2] = 0.0

    return sorted(matches, key=lambda m: m[1])


def is_template_visible(filename: str, img: np.ndarray) -> bool:
    """Return True if the template image is found in img above the match threshold."""
    if not filename:
        return False
    try:
        match = match_template(filename, img)
    except FileNotFoundError:
        return False
    if not match:
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
    button_filenames: str | list[str],
    img: np.ndarray,
    screen_offset: tuple[int, int] = (0, 0),
    on_found: Any = None,
    crop_h_frac: float = 1.0,
    threshold: float | None = None,
) -> tuple[np.ndarray, float, tuple[int, int]] | None:
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
    button_filenames: str | list[str],
    img: np.ndarray,
    screen_offset: tuple[int, int] = (0, 0),
    on_found: Any = None,
    crop_h_frac: float = 1.0,
    threshold: float | None = None,
) -> bool:
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


# ai: claude-sonnet-4-6 | 2026-06-26
def click_template_match_at(
    filename: str,
    img: np.ndarray,
    screen_offset: tuple[int, int] = (0, 0),
    index: int = 0,
    threshold: float | None = None,
) -> bool:
    """Click the match at position index (sorted top-to-bottom by y coordinate).

    index=0 clicks the topmost match; index=-1 clicks the bottommost.
    Returns True if a match was found and clicked, False if no matches exist or
    the template file is missing.

    Uses exact template-size suppression (not the 2x used by find_all_template_matches)
    so closely-spaced buttons are each detected as separate matches.
    """
    if threshold is None:
        threshold = _BUTTON_MATCH_THRESHOLD

    template_path = os.path.normpath(os.path.join(_SNIPPETS_DIR, filename))
    if not os.path.isfile(template_path):
        logger.error(f"Snippet file missing: {template_path}")
        return False

    template = _load_template(template_path)
    if template is None:
        return False

    th, tw = template.shape[:2]
    score_map = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)

    # Collect all peaks with exact template-size suppression so buttons that are
    # spaced less than 2x the template height apart are still found individually.
    matches: list[tuple[int, int, int, int]] = []
    wmap = score_map.copy()
    while True:
        _, max_val, _, max_loc = cv2.minMaxLoc(wmap)
        if max_val < threshold:
            break
        x, y = max_loc
        matches.append((x, y, tw, th))
        wmap[y: min(y + th, wmap.shape[0]), x: min(x + tw, wmap.shape[1])] = 0.0

    if not matches:
        return False

    matches.sort(key=lambda m: m[1])  # top-to-bottom by y
    x, y, w, h = matches[index]
    center_x = screen_offset[0] + x + w // 2
    center_y = screen_offset[1] + y + h // 2
    logger.debug(
        "Clicking %s match[%d] at (%d, %d) — %d total match(es)",
        filename, index, center_x, center_y, len(matches),
    )
    pyautogui.click(center_x, center_y)
    return True


def wait_for_template(
    filename: str,
    sc: "ScreenCapture",
    window: _Window,
    max_retries: int | None = None,
    delay: float | None = None,
) -> np.ndarray | None:
    """Poll until filename is visible. Returns the image it was found in, or None.

    Captures a fresh screenshot on each attempt. If the template does not appear
    within max_retries attempts, logs a warning and returns None.
    """
    if max_retries is None:
        max_retries = capture_cfg("screen_wait_retries", default=8)
    if delay is None:
        delay = capture_cfg("screen_wait_delay", default=0.25)
    for _ in range(max_retries):
        img = sc.capture(window, delay=delay)
        if img is not None and is_template_visible(filename, img):
            return img
    logger.warning(f"'{filename}' not detected after {max_retries} attempts")
    return None


def wait_for_any_template(
    filenames: list[str],
    sc: "ScreenCapture",
    window: _Window,
    max_retries: int | None = None,
    delay: float | None = None,
) -> tuple[str, np.ndarray] | tuple[None, None]:
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
        img = sc.capture(window, delay=delay)
        if img is None:
            continue
        for filename in filenames:
            if is_template_visible(filename, img):
                return filename, img
    logger.warning(f"None of {filenames!r} detected after {max_retries} attempts")
    return None, None


def wait_and_click(
    filename: str,
    sc: "ScreenCapture",
    window: _Window,
    screen_offset: tuple[int, int] = (0, 0),
    max_retries: int | None = None,
    delay: float | None = None,
) -> bool:
    """Wait for filename to appear then click it. Returns True if clicked."""
    img = wait_for_template(filename, sc, window, max_retries=max_retries, delay=delay)
    if img is None:
        return False
    return click_button_if_visible(filename, img, screen_offset)


def wait_and_click_any(
    filenames: list[str],
    sc: "ScreenCapture",
    window: _Window,
    screen_offset: tuple[int, int] = (0, 0),
    max_retries: int | None = None,
    delay: float | None = None,
) -> str | None:
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


def get_reader() -> easyocr.Reader:
    global _ocr_reader
    if _ocr_reader is None:
        with _ocr_reader_lock:
            if _ocr_reader is None:
                _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


class ScreenCapture:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
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

        Combines several techniques to reliably steal focus from a background
        Flask thread regardless of which app currently owns the foreground:
          1. Restore if minimized.
          2. ALT key trick — simulating VK_MENU convinces Windows the calling
             thread has had recent input, unlocking SetForegroundWindow.
          3. SetWindowPos TOPMOST → NOTOPMOST forces the window to the top of
             the Z-order independently of focus-stealing rules.
          4. BringWindowToTop + SetForegroundWindow for the actual focus change.
        """
        import ctypes
        import win32con
        import win32gui

        if not window:
            raise Exception("activate_window: Window is None")

        hwnd = window._hWnd
        _SWP_NOMOVE = 0x0002
        _SWP_NOSIZE = 0x0001
        _SWP_FLAGS = _SWP_NOMOVE | _SWP_NOSIZE

        if win32gui.IsIconic(hwnd):
            logger.info(f"Restoring minimized window: {window.title}")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.5)

        # ALT key trick — must sleep briefly after so Windows processes the event
        # before SetForegroundWindow is called.
        ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(
            win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0
        )
        time.sleep(0.05)

        # Force window to top of Z-order via TOPMOST, then revert so it behaves normally.
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, _SWP_FLAGS)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, _SWP_FLAGS)

        win32gui.BringWindowToTop(hwnd)

        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            logger.warning(f"SetForegroundWindow failed: {e}")
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)

        logger.debug(f"Activated window: {window.title}")
        # Give Windows time to complete the focus transition before we start
        # capturing screenshots or sending input.
        time.sleep(1.0)

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
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")

        if delay:
            time.sleep(delay)
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        screenshot.save(filepath)
        logger.debug(f"Screenshot saved to {filepath}")
        return filepath

    def capture_window_np(self, window, delay=None, activate=False) -> np.ndarray:
        """Capture the window to a BGR numpy array without a synchronous disk write.

        If performance.write_behind is true the frame is also pushed onto the
        write-behind queue so a PNG copy lands in screenshots_dir asynchronously —
        useful for post-mortem review without adding latency to the polling loop.
        """
        if activate:
            self.activate_window(window)
        left, top, width, height = window.left, window.top, window.width, window.height
        if delay:
            time.sleep(delay)
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        logger.debug("Captured window to numpy array (in-memory)")

        if capture_cfg("performance", "write_behind", default=False):
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S_%f")
            filepath = os.path.join(self.output_dir, f"capture_{timestamp}.png")
            try:
                _get_write_queue().put_nowait((img_bgr.copy(), filepath))
                logger.debug(f"Queued write-behind: {filepath}")
            except queue.Full:
                logger.debug("write-behind queue full — frame dropped")

        return img_bgr

    def capture(self, window, delay=None, activate=False) -> np.ndarray | None:
        """Capture the window and return a BGR numpy array.

        Dispatches to capture_window_np (memory mode) or capture_window + imread
        (disk mode) depending on the performance.capture_mode setting.
        Use this in all polling and recognition code so the setting takes effect
        uniformly without changing call sites.
        """
        if capture_cfg("performance", "capture_mode", default="disk") == "memory":
            return self.capture_window_np(window, delay=delay, activate=activate)
        img_path = self.capture_window(window, delay=delay, activate=activate)
        return cv2.imread(img_path)

    def find_image_on_screen(self, template_filename, region=None, threshold=0.8):
        """Search for template_filename in a screenshot and return its center (x, y), or None."""
        try:
            screenshot = pyautogui.screenshot(region=region)
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

            template_path = os.path.join(self.snippets_dir, template_filename)
            if not os.path.exists(template_path):
                logger.error(f"Template image not found: {template_path}")
                return None

            template = _load_template(template_path)
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
                "Red X 1.jpg",
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
            img = self.capture(window)
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
