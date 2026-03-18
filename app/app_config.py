"""Loads settings from settings.yaml at the project root.

Usage:
    from app.app_config import capture_cfg

    threshold = capture_cfg("button_match_threshold")
    titles    = capture_cfg("window_titles")
    retries   = capture_cfg("navigation", "max_retries")
"""
import logging
import os

import yaml

logger = logging.getLogger(__name__)

_SETTINGS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "settings.yaml")
)

_cfg: dict = {}


def _load():
    global _cfg
    try:
        with open(_SETTINGS_PATH) as f:
            data = yaml.safe_load(f) or {}
        _cfg = data.get("stfc_config", {})
        logger.debug(f"loaded from {_SETTINGS_PATH}")
    except FileNotFoundError:
        logger.warning(f"{_SETTINGS_PATH} not found — using defaults")
    except Exception as e:
        logger.error(f"failed to load settings: {e}")


_load()


def capture_cfg(*keys, default=None):
    """Look up a value from the stfc_config section by one or more nested keys.

    Examples:
        capture_cfg("button_match_threshold")       -> 0.85
        capture_cfg("navigation", "max_retries")    -> 8
        capture_cfg("factions", "snippet_threshold") -> 0.70
    """
    node = _cfg
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key, default)
        if node is default:
            return default
    return node
