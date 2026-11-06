# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-sonnet-5 | 2026-09-17
from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, get_args

import cv2
import numpy as np
from werkzeug.utils import secure_filename

from app.app_config import (
    TemplateKind,
    add_diamond_glyph_template,
    add_hostile_ship_template,
    add_skull_glyph_template,
)
from app.screen_processing.process_system_targets import detect_system_name
from app.screen_processing.screen_capture import ScreenCapture
from app.snippet_store import new_snippet_path, snippet_exists

if TYPE_CHECKING:
    from app.database.database import Database

logger = logging.getLogger(__name__)

# Holds the most recent capture_screen() frame so save_template() can crop it.
# Module-level (not an instance attribute) because each request builds a new
# HostileTemplateOrchestrator — see capture_screen_view.py's _run_capture.
# Single-operator app, so no locking: the browser drives capture and save
# strictly sequentially.
_last_capture: dict = {"img": None, "system_name": None}

# What each template "kind" is named on disk and which settings.yaml list it
# registers itself into. Skull/diamond glyphs are a fixed UI element (not
# tied to any one system's art), so unlike hostile ship icons their filename
# doesn't include a system label.
_KIND_CONFIG = {
    "hostile_ship": {"prefix": "Hostile", "per_system": True, "add_fn": add_hostile_ship_template},
    "skull_glyph": {"prefix": "Skull", "per_system": False, "add_fn": add_skull_glyph_template},
    "diamond_glyph": {"prefix": "Diamond", "per_system": False, "add_fn": add_diamond_glyph_template},
}
# ai: claude-opus-5-5 | 2026-11-06
# Request validation accepts exactly the TemplateKind values, so a kind added
# there without a registry entry here (or vice versa) must fail at import.
if set(_KIND_CONFIG) != set(get_args(TemplateKind)):
    raise RuntimeError(f"_KIND_CONFIG {sorted(_KIND_CONFIG)} does not match TemplateKind {get_args(TemplateKind)}")


class HostileTemplateOrchestrator:
    """Lets the user bootstrap/extend the combat template lists — hostile ship
    icons, and the skull/diamond label glyphs — from the running app instead
    of hand-editing settings.yaml and snippet files.

    Detection for all three only works once at least one template of that
    kind already exists (_find_ship_icons()/_detect_label_glyph() in
    process_system_targets.py), so there's no way to auto-crop the first one
    from scratch. Instead: capture_screen() grabs a fresh screenshot for the
    user to draw a box on in the browser (over a ship they've just selected
    in-game, or over a glyph visible in its label), and save_template() crops
    that box out and registers it under the requested kind.
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

    # ai: claude-sonnet-5 | 2026-09-18
    def save_template(self, x: int, y: int, w: int, h: int, kind: str = "hostile_ship") -> dict:
        """Crop (x, y, w, h) — image-local pixel coords into the last
        capture_screen() frame — and register it as a new template of the
        given kind ("hostile_ship", "skull_glyph", or "diamond_glyph"). Can
        be called multiple times against the same capture to save several
        templates (e.g. a couple of ship types, or a ship type plus the
        skull/diamond glyph on its label) seen in one screenshot.
        """
        kind_config = _KIND_CONFIG.get(kind)
        if kind_config is None:
            return {"error": f"Unknown template kind: {kind!r}"}

        img: np.ndarray | None = _last_capture["img"]
        if img is None:
            return {"error": "No screenshot captured yet — capture the screen first"}

        img_h, img_w = img.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(img_w, x + w), min(img_h, y + h)
        if x2 <= x1 or y2 <= y1:
            return {"error": "Crop region is empty"}
        crop = img[y1:y2, x1:x2]

        if kind_config["per_system"]:
            system_label = secure_filename(_last_capture["system_name"] or "Unknown") or "Unknown"
            stem = f"{kind_config['prefix']}-{system_label}"
        else:
            stem = kind_config["prefix"]

        n = 1
        while True:
            filename = f"{stem}-{n}.png"
            if not snippet_exists(filename):  # ai: claude-opus-5-5 | 2026-11-06
                break
            n += 1

        cv2.imwrite(new_snippet_path(filename), crop)  # ai: claude-opus-5-5 | 2026-11-06
        updated = kind_config["add_fn"](filename)
        logger.info(f"Saved new {kind} template: {filename}")
        return {"success": True, "filename": filename, "kind": kind, "templates": updated}
