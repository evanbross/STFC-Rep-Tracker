# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
"""Extract highlighted-faction snippets from existing screenshots.

For each screenshot in the Screenshots/ folder that shows the faction store,
uses RepButton template matching to locate each faction's row, then
identifies the selected faction (the one whose button doesn't match its
unselected template) and saves a cropped snippet of the highlighted row.

Snippets are saved as SelectedRow{Code}.jpg in app/screen_snippets/.

Usage:
    python extract_snippets.py
"""
import os
import sqlite3

import cv2
import numpy as np

SCREENSHOTS_DIR = "Screenshots"
SNIPPETS_DIR = os.path.join("app", "screen_snippets")
DB_PATH = "stfc_rep_tracker.db"

# x range for the full-width faction button area (fraction of image width)
PANEL_X_START_FRAC = 0.0
PANEL_X_END_FRAC = 0.095

# Match threshold — buttons below this are considered "selected state" (different appearance)
SELECTED_THRESHOLD = 0.90

# Minimum confidence required to trust a button's position
POSITION_THRESHOLD = 0.85


def get_factions():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name, code FROM factions ORDER BY display_order"
    ).fetchall()
    conn.close()
    return [{"name": r[0], "code": r[1]} for r in rows]


def find_faction_positions(img, factions, snippets_dir):
    """Locate each faction button via template matching.

    Returns a list parallel to factions: each entry is
    (y_center, match_score) or None if the template isn't on disk.
    Entries where match_score < SELECTED_THRESHOLD are likely selected-state.
    """
    positions = []
    for f in factions:
        code = f["code"].capitalize()
        path = os.path.join(snippets_dir, f"RepButton{code}.jpg")
        tmpl = cv2.imread(path)
        if tmpl is None:
            positions.append(None)
            continue
        res = cv2.matchTemplate(img, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        th = tmpl.shape[0]
        y_center = max_loc[1] + th // 2
        positions.append((y_center, max_val))
    return positions


def interpolate_y(positions, target_idx, factions):
    """Estimate y_center for target_idx by linear interpolation from neighbours."""
    # Collect well-matched neighbours (above and below threshold, but high confidence)
    known = [
        (i, p[0])
        for i, p in enumerate(positions)
        if p is not None and p[1] >= POSITION_THRESHOLD
    ]
    if len(known) < 2:
        return None

    # Use spacing between adjacent known rows
    spacings = [known[j + 1][1] - known[j][1] for j in range(len(known) - 1)]
    avg_spacing = sum(spacings) / len(spacings)

    # Use the closest known point and project
    nearest = min(known, key=lambda kp: abs(kp[0] - target_idx))
    nearest_idx, nearest_y = nearest
    return int(nearest_y + (target_idx - nearest_idx) * avg_spacing)


def is_faction_store(img, snippets_dir):
    """Return True if the Faction Store header is visible in the image."""
    header_path = os.path.join(snippets_dir, "Faction Store Header.jpg")
    header = cv2.imread(header_path)
    if header is None:
        return True  # can't check — assume it's fine
    res = cv2.matchTemplate(img, header, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val >= 0.80


def main():
    factions = get_factions()
    os.makedirs(SNIPPETS_DIR, exist_ok=True)

    captured = {}  # faction name -> best (snippet crop, score)

    screenshots = sorted(os.listdir(SCREENSHOTS_DIR))
    faction_store_count = 0

    for filename in screenshots:
        if not filename.lower().endswith(".png"):
            continue
        path = os.path.join(SCREENSHOTS_DIR, filename)
        img = cv2.imread(path)
        if img is None:
            continue

        if not is_faction_store(img, SNIPPETS_DIR):
            continue
        faction_store_count += 1

        h, w = img.shape[:2]
        positions = find_faction_positions(img, factions, SNIPPETS_DIR)

        # Find the selected faction (lowest match score among found buttons)
        candidates = [
            (i, p) for i, p in enumerate(positions)
            if p is not None and p[1] < SELECTED_THRESHOLD
        ]
        if not candidates:
            continue  # no obviously-selected faction found

        # Pick the faction with the lowest match (most different from unselected template)
        sel_idx, sel_pos = min(candidates, key=lambda c: c[1][1])
        sel_score = sel_pos[1]
        faction = factions[sel_idx]
        name = faction["name"]
        code = faction["code"].capitalize()

        # Find the y position (interpolate if needed since selected button looks different)
        y_center = interpolate_y(positions, sel_idx, factions)
        if y_center is None:
            print(f"  {filename}: could not estimate y for '{name}', skipping")
            continue

        # Estimate row height from neighbour spacing
        known = [
            (i, p[0])
            for i, p in enumerate(positions)
            if p is not None and p[1] >= POSITION_THRESHOLD
        ]
        if len(known) >= 2:
            spacings = [known[j + 1][1] - known[j][1] for j in range(len(known) - 1)]
            row_h = int(sum(spacings) / len(spacings))
        else:
            row_h = int(h * 0.047)

        x1 = int(w * PANEL_X_START_FRAC)
        x2 = int(w * PANEL_X_END_FRAC)
        y1 = max(0, y_center - row_h // 2)
        y2 = min(h, y_center + row_h // 2)

        crop = img[y1:y2, x1:x2]
        print(
            f"  {filename} -> '{name}' (match={sel_score:.3f}, y={y1}-{y2}) "
            f"-> SelectedRow{code}.jpg"
        )

        # Keep the first occurrence (screenshots are sorted by timestamp)
        if name not in captured:
            captured[name] = crop

    print(f"\nFaction store screenshots: {faction_store_count}")
    print(f"Saving snippets for: {sorted(captured.keys())}")

    for name, crop in captured.items():
        faction = next(f for f in factions if f["name"] == name)
        code = faction["code"].capitalize()
        out_path = os.path.join(SNIPPETS_DIR, f"SelectedRow{code}.jpg")
        cv2.imwrite(out_path, crop)

    missing = [f["name"] for f in factions if f["name"] not in captured]
    if missing:
        print(f"No snippet extracted for: {missing}")
        print("  (Run the capture screen tool with those factions selected to get screenshots)")


if __name__ == "__main__":
    main()
