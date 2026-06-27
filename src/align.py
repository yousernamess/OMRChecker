import cv2
import numpy as np


# ----------------------------------------------------
# Constants
# ----------------------------------------------------
TARGET_W = 2382
TARGET_H = 3368

# Marker size bounds (px) -- at target resolution
MARKER_MIN_AREA = 100
MARKER_MAX_AREA = 1200

# Search region: look for markers only in the outer
# N% of the image to avoid false positives in content
CORNER_MARGIN = 0.15


# ----------------------------------------------------
# Detect corner fiducial markers
# ----------------------------------------------------
def find_markers(image):
    gray    = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    h, w = image.shape[:2]
    margin_x = int(w * CORNER_MARGIN)
    margin_y = int(h * CORNER_MARGIN)

    # Corner search regions (x1, y1, x2, y2)
    regions = {
        "top_left":     (0,            0,            margin_x,      margin_y),
        "top_right":    (w - margin_x, 0,            w,             margin_y),
        "bottom_left":  (0,            h - margin_y, margin_x,      h),
        "bottom_right": (w - margin_x, h - margin_y, w,             h),
    }

    found = {}

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (MARKER_MIN_AREA <= area <= MARKER_MAX_AREA):
            continue

        # Check squareness
        x, y, bw, bh = cv2.boundingRect(cnt)
        aspect = bw / bh if bh > 0 else 0
        if not (0.6 <= aspect <= 1.4):
            continue

        # Find which corner region this belongs to
        cx = x + bw // 2
        cy = y + bh // 2

        for corner, (rx1, ry1, rx2, ry2) in regions.items():
            if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                if corner not in found:
                    found[corner] = (cx, cy)
                break

    return found


# ----------------------------------------------------
# Perspective warp
# ----------------------------------------------------
def align(image):
    markers = find_markers(image)

    required = ["top_left", "top_right", "bottom_left", "bottom_right"]
    missing  = [r for r in required if r not in markers]

    if missing:
        raise ValueError(f"Could not find markers: {missing}")

    src = np.float32([
        markers["top_left"],
        markers["top_right"],
        markers["bottom_left"],
        markers["bottom_right"],
    ])

    # Destination: where each marker should land in the warped image.
    # Use the marker centers from the blank template at target resolution.
    # These are approximate -- adjust after first test if needed.
    dst = np.float32([
    [96,   215],   # top_left
    [2285, 215],   # top_right
    [96,   3152],  # bottom_left
    [2285, 3152],  # bottom_right
])

    M = cv2.getPerspectiveTransform(src, dst)

    warped = cv2.warpPerspective(
        image, M,
        (TARGET_W, TARGET_H),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    return warped


# ----------------------------------------------------
# Debug: visualize detected markers
# ----------------------------------------------------
def debug_markers(image, output_path=None):
    markers = find_markers(image)
    debug   = image.copy()

    colors = {
        "top_left":     (0,   0,   255),
        "top_right":    (0,   255, 0),
        "bottom_left":  (255, 0,   0),
        "bottom_right": (0,   255, 255),
    }

    for corner, (cx, cy) in markers.items():
        color = colors.get(corner, (255, 255, 255))
        cv2.circle(debug, (cx, cy), 20, color, 3)
        cv2.putText(debug, corner, (cx + 25, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    print(f"Found {len(markers)}/4 markers:")
    for corner, pt in markers.items():
        print(f"  {corner}: {pt}")

    missing = [r for r in ["top_left", "top_right", "bottom_left", "bottom_right"]
               if r not in markers]
    if missing:
        print(f"  MISSING: {missing}")

    if output_path:
        cv2.imwrite(str(output_path), debug)
        print(f"  Debug image saved to: {output_path}")

    return debug


# ----------------------------------------------------
# Standalone test
# ----------------------------------------------------
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from preprocess import load_image_from_path

    BASE_DIR = Path(__file__).resolve().parent.parent

    if len(sys.argv) < 2:
        print("Usage: python align.py <path_to_scanned_omr>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    image      = load_image_from_path(str(image_path))

    # Debug: show marker detection before warping
    debug_markers(image, BASE_DIR / "output" / "debug_markers.png")

    # Warp
    try:
        warped = align(image)
        out    = BASE_DIR / "output" / "aligned.png"
        cv2.imwrite(str(out), warped)
        print(f"\nAligned image saved to: {out}")
    except ValueError as e:
        print(f"\nAlignment failed: {e}")