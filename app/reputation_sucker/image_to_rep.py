import cv2
import numpy as np
import pytesseract
from PIL import Image

# If on Windows, set tesseract path:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

FACTION_NAMES = [
    "Federation", "Klingon", "Romulan", "Augment",
    "Rogue", "Bajoran", "Ex-Borg", "Section 31", "Terran", "DTI"
]


def find_highlighted_faction(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    height, width = img.shape[:2]

    # The faction list is on the left portion of the screen
    # Crop to just the faction list area (roughly left 45% of image)
    faction_panel = img[:, :int(width * 0.45)]

    # Convert to grayscale for brightness analysis
    gray = cv2.cvtColor(faction_panel, cv2.COLOR_BGR2GRAY)

    # Divide into rows (one per faction)
    num_factions = len(FACTION_NAMES)
    row_height = height // num_factions

    best_faction = None
    best_brightness = -1

    for i, faction in enumerate(FACTION_NAMES):
        y1 = i * row_height
        y2 = y1 + row_height
        row = gray[y1:y2, :]
        avg_brightness = np.mean(row)

        if avg_brightness > best_brightness:
            best_brightness = avg_brightness
            best_faction = faction

    return best_faction


def extract_points(image_path):
    img = cv2.imread(image_path)
    height, width = img.shape[:2]

    # Points text is in the upper-right area
    # Crop to the top portion of the right panel
    points_region = img[0:int(height * 0.12), int(width * 0.40):]

    # Convert to PIL for Tesseract
    pil_img = Image.fromarray(cv2.cvtColor(points_region, cv2.COLOR_BGR2RGB))

    # Upscale for better OCR accuracy
    scale = 3
    new_size = (pil_img.width * scale, pil_img.height * scale)
    pil_img = pil_img.resize(new_size, Image.LANCZOS)

    # OCR config: digits and comma only for the number
    text = pytesseract.image_to_string(pil_img, config='--psm 7 -c tessedit_char_whitelist=Points:0123456789,')

    # Parse out the number
    import re
    match = re.search(r'Points[:\s]*([\d,]+)', text, re.IGNORECASE)
    if match:
        points_str = match.group(1).replace(',', '')
        return int(points_str)

    # Fallback: just grab any number found
    numbers = re.findall(r'[\d,]+', text)
    if numbers:
        return int(max(numbers, key=len).replace(',', ''))

    return None


def analyze_screenshot(image_path):
    faction = find_highlighted_faction(image_path)
    points = extract_points(image_path)

    print(f"Highlighted Faction: {faction}")
    print(f"Points: {points:,}" if points else "Points: Could not extract")

    return faction, points


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "screenshot.png"
    analyze_screenshot(path)