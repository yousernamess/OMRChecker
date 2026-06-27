import cv2
import json
import numpy as np
from pathlib import Path
from preprocess import load_image_from_path
from align import align

# ----------------------------------------------------
# Paths
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "templates" / "calibration_points.json"


# ----------------------------------------------------
# Load template
# ----------------------------------------------------
def load_template(path=TEMPLATE_PATH):
    with open(path, "r") as f:
        return json.load(f)


# ----------------------------------------------------
# Bubble score (Circular ROI)
# ----------------------------------------------------
def bubble_fill(binary, center, radius, padding):
    x, y = center

    r = radius + padding

    x1 = max(0, x - r)
    y1 = max(0, y - r)
    x2 = min(binary.shape[1], x + r + 1)
    y2 = min(binary.shape[0], y + r + 1)

    roi = binary[y1:y2, x1:x2]

    if roi.size == 0:
        return 0.0

    mask = np.zeros(roi.shape, dtype=np.uint8)

    cx = x - x1
    cy = y - y1

    cv2.circle(mask, (cx, cy), radius, 255, -1)

    dark_pixels  = cv2.countNonZero(cv2.bitwise_and(roi, mask))
    total_pixels = cv2.countNonZero(mask)

    if total_pixels == 0:
        return 0.0

    return dark_pixels / total_pixels


# ----------------------------------------------------
# Read all bubbles
# ----------------------------------------------------
def read_omr(image_path, template, question_count=None):
    image = load_image_from_path(str(image_path))

    try:
        image = align(image)
        print("Alignment: OK")
    except ValueError as e:
        print(f"Warning: alignment failed ({e}), proceeding without.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)

    radius   = template["bubble_radius"]
    padding  = template["roi_padding"]
    options  = template["options"]

    total   = question_count or template["question_count"]
    bubbles = {
        f"Q{i}": template["bubbles"][f"Q{i}"]
        for i in range(1, total + 1)
    }

    ABSOLUTE_THRESHOLD   = 0.35
    DIFFERENCE_THRESHOLD = 0.08

    results = {}

    for q_key, opts in bubbles.items():
        scores = {}
        for opt in options:
            cx, cy      = opts[opt]
            scores[opt] = bubble_fill(binary, (cx, cy), radius, padding)

        sorted_scores = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        best_opt,   best_score   = sorted_scores[0]
        second_opt, second_score = sorted_scores[1]

        if best_score < ABSOLUTE_THRESHOLD:
            answer = None
        elif (best_score - second_score) < DIFFERENCE_THRESHOLD:
            answer = None
        else:
            answer = best_opt

        results[q_key] = answer

        print(f"{q_key}")
        for opt in options:
            print(f"   {opt}: {scores[opt]:.3f}")
        print(f"Highest    : {best_opt} ({best_score:.3f})")
        print(f"Second     : {second_opt} ({second_score:.3f})")
        print(f"Difference : {(best_score - second_score):.3f}")
        print(f"Detected   : {answer}")
        print()

    return results


# ----------------------------------------------------
# Main
# ----------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python bubble_reader.py <path_to_scanned_omr>")
        sys.exit(1)

    image_path     = Path(sys.argv[1])
    template       = load_template()
    question_count = int(sys.argv[2]) if len(sys.argv) > 2 else None
    results        = read_omr(image_path, template, question_count=question_count)

    print("----------------------------------------")
    print("Final Results")
    print("----------------------------------------")
    for q_key, answer in results.items():
        print(f"  {q_key}: {answer}")