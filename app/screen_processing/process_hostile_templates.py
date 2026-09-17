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
# ai: claude-sonnet-5 | 2026-09-17
from __future__ import annotations

import base64
import logging
import os
from typing import TYPE_CHECKING

import cv2
import numpy as np
from werkzeug.utils import secure_filename

from app.app_config import add_hostile_ship_template
from app.screen_processing.process_system_targets import detect_system_name
from app.screen_processing.screen_capture import ScreenCapture, get_snippets_dir

if TYPE_CHECKING:
    from app.database.database import Database

logger = logging.getLogger(__name__)

# Holds the most recent capture_screen() frame so save_template() can crop it.
# Module-level (not an instance attribute) because each request builds a new
# HostileTemplateOrchestrator — see capture_screen_view.py's _run_capture.
# Single-operator app, so no locking: the browser drives capture and save
# strictly sequentially.
_last_capture: dict = {"img": None, "system_name": None}


class HostileTemplateOrchestrator:
    """Lets the user bootstrap/extend combat.hostile_ship_templates from the
    running app instead of hand-editing settings.yaml and snippet files.

    _find_ship_icons() (process_system_targets.py) can only detect hostile
    ships once at least one template already exists, so there's no way to
    auto-crop a new one from scratch. Instead: capture_screen() grabs a fresh
    screenshot for the user to draw a box on in the browser (over a ship
    they've just selected in-game), and save_template() crops that box out
    and registers it as a new template.
    """

    def __init__(self, db: "Database") -> None:
        self.sc = ScreenCapture()
        self.db = db

    # ai: claude-sonnet-5 | 2026-09-17
    def capture_screen(self) -> dict:
        """Activate the game window, capture it, and return it as a base64 PNG.

        Also OCRs the current system name (cosmetic only, used for the
        saved filename and the "Add for <system>" button label) — unlike
        scan_targets(), a failed OCR here isn't fatal.
        """
        try:
            window = self.sc.get_and_activate_window()
        except RuntimeError as e:
            logger.error(str(e))
            return {"error": str(e)}

        img = self.sc.capture(window, activate=False)
        if img is None:
            return {"error": "Could not capture system screen"}

        system_name = detect_system_name(img)
        _last_capture["img"] = img
        _last_capture["system_name"] = system_name

        ok, buf = cv2.imencode(".png", img)
        if not ok:
            return {"error": "Failed to encode screenshot"}

        img_h, img_w = img.shape[:2]
        return {
            "success": True,
            "system_name": system_name,
            "image_base64": base64.b64encode(buf).decode("ascii"),
            "width": img_w,
            "height": img_h,
        }

    # ai: claude-sonnet-5 | 2026-09-17
    def save_template(self, x: int, y: int, w: int, h: int) -> dict:
        """Crop (x, y, w, h) — image-local pixel coords into the last
        capture_screen() frame — and register it as a new hostile ship
        template. Can be called multiple times against the same capture to
        save several ship types seen in one screenshot.
        """
        img: np.ndarray | None = _last_capture["img"]
        if img is None:
            return {"error": "No screenshot captured yet — capture the screen first"}

        img_h, img_w = img.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(img_w, x + w), min(img_h, y + h)
        if x2 <= x1 or y2 <= y1:
            return {"error": "Crop region is empty"}
        crop = img[y1:y2, x1:x2]

        snippets_dir = get_snippets_dir()
        system_label = secure_filename(_last_capture["system_name"] or "Unknown") or "Unknown"
        n = 1
        while True:
            filename = f"Hostile-{system_label}-{n}.png"
            if not os.path.exists(os.path.join(snippets_dir, filename)):
                break
            n += 1

        cv2.imwrite(os.path.join(snippets_dir, filename), crop)
        updated = add_hostile_ship_template(filename)
        logger.info(f"Saved new hostile ship template: {filename}")
        return {"success": True, "filename": filename, "hostile_ship_templates": updated}
