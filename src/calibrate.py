import cv2
import json
import math
import numpy as np
from pathlib import Path
from preprocess import load_image_from_path

# ----------------------------------------------------
# Paths
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_PATH = BASE_DIR / "input" / "STD029-40Q.pdf"
OUTPUT_JSON = BASE_DIR / "templates" / "calibration_points.json"
OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------
# Constants
# ----------------------------------------------------
OPTIONS = ["A", "B", "C", "D"]

COLUMNS = [
    ("C1", 1,  10),
    ("C2", 11, 20),
    ("C3", 21, 30),
    ("C4", 31, 40),
]

ANCHORS = []
for col_name, q_start, q_end in COLUMNS:
    ANCHORS += [
        (col_name, f"Q{q_start}", "A", f"Col {col_name} - Q{q_start} Option A"),
        (col_name, f"Q{q_start}", "D", f"Col {col_name} - Q{q_start} Option D"),
        (col_name, f"Q{q_end}",   "A", f"Col {col_name} - Q{q_end}  Option A"),
    ]

TEMPLATE_NAME    = "vigyan_express_40_v1"
TEMPLATE_VERSION = 1
QUESTION_COUNT   = 40

# ----------------------------------------------------
# State
# ----------------------------------------------------
PHASE_RADIUS  = 0
PHASE_ANCHORS = 1

phase             = PHASE_RADIUS
radius_center     = None   # screen coords
radius_center_img = None   # image coords
radius_edge       = None
bubble_radius     = None
clicked           = []

# Pan / zoom
zoom       = 1.0
ZOOM_MIN   = 0.3
ZOOM_MAX   = 8.0
ZOOM_STEP  = 0.15

pan_x      = 0.0
pan_y      = 0.0
is_panning = False
pan_start  = (0, 0)
pan_origin = (0.0, 0.0)
space_held = False

WINDOW_W = 1200
WINDOW_H = 850
WINDOW   = "Template Calibration"

# ----------------------------------------------------
# Load image
# ----------------------------------------------------
image = load_image_from_path(str(IMAGE_PATH))
original_height, original_width = image.shape[:2]

# ----------------------------------------------------
# Coordinate helpers
# ----------------------------------------------------
def screen_to_image(sx, sy):
    ix = int((sx - pan_x) / zoom)
    iy = int((sy - pan_y) / zoom)
    return ix, iy

def image_to_screen(ix, iy):
    sx = int(ix * zoom + pan_x)
    sy = int(iy * zoom + pan_y)
    return sx, sy

# ----------------------------------------------------
# Draw
# ----------------------------------------------------
def draw_state():
    canvas = np.zeros((WINDOW_H, WINDOW_W, 3), dtype=np.uint8)

    src_x0 = int(-pan_x / zoom)
    src_y0 = int(-pan_y / zoom)
    src_x1 = int((WINDOW_W - pan_x) / zoom)
    src_y1 = int((WINDOW_H - pan_y) / zoom)

    src_x0 = max(0, src_x0)
    src_y0 = max(0, src_y0)
    src_x1 = min(original_width,  src_x1)
    src_y1 = min(original_height, src_y1)

    if src_x1 > src_x0 and src_y1 > src_y0:
        patch = image[src_y0:src_y1, src_x0:src_x1]

        dst_w = min(int((src_x1 - src_x0) * zoom), WINDOW_W)
        dst_h = min(int((src_y1 - src_y0) * zoom), WINDOW_H)

        if dst_w > 0 and dst_h > 0:
            resized = cv2.resize(patch, (dst_w, dst_h), interpolation=cv2.INTER_LINEAR)

            dst_x0 = max(0, int(pan_x))
            dst_y0 = max(0, int(pan_y))
            dst_x1 = min(dst_x0 + dst_w, WINDOW_W)
            dst_y1 = min(dst_y0 + dst_h, WINDOW_H)
            resized = resized[:dst_y1 - dst_y0, :dst_x1 - dst_x0]
            canvas[dst_y0:dst_y1, dst_x0:dst_x1] = resized

    # Draw radius reference bubble
    if phase == PHASE_ANCHORS and bubble_radius is not None and radius_center_img is not None:
        sx, sy = image_to_screen(*radius_center_img)
        sr = max(1, int(bubble_radius * zoom))
        cv2.circle(canvas, (sx, sy), sr, (0, 200, 0), 2)

    # Draw anchor points
    if phase == PHASE_ANCHORS:
        for i, (ox, oy) in enumerate(clicked):
            sx, sy = image_to_screen(ox, oy)
            sr = max(1, int(bubble_radius * zoom)) if bubble_radius else 6
            cv2.circle(canvas, (sx, sy), sr, (0, 0, 255), 2)
            cv2.putText(canvas, str(i + 1), (sx + sr + 4, sy - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 200), 1)

    # Draw radius center dot during radius phase
    if phase == PHASE_RADIUS and radius_center is not None:
        cv2.circle(canvas, radius_center, 5, (0, 0, 255), -1)

    # HUD background
    cv2.rectangle(canvas, (0, 0), (WINDOW_W, 44), (30, 30, 30), -1)

    if phase == PHASE_RADIUS:
        if radius_center is None:
            msg = "Step 1/2: Click CENTER of any bubble"
        else:
            msg = "Step 2/2: Click EDGE of the same bubble"
    elif len(clicked) < len(ANCHORS):
        _, _, _, desc = ANCHORS[len(clicked)]
        msg = f"Next: {len(clicked)+1}. {desc}"
    else:
        msg = "All points collected. Press S to save or U to undo."

    cv2.putText(canvas, msg, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 0), 2)

    # Cursor mode indicator
    mode = "PAN" if space_held else "CLICK"
    mode_color = (0, 200, 255) if space_held else (200, 200, 200)
    footer = f"Zoom: {zoom:.1f}x  |  Scroll=zoom  |  Space+drag=pan  |  Mode: {mode}"
    cv2.rectangle(canvas, (0, WINDOW_H - 28), (WINDOW_W, WINDOW_H), (30, 30, 30), -1)
    cv2.putText(canvas, footer, (10, WINDOW_H - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, mode_color, 1)

    cv2.imshow(WINDOW, canvas)

# ----------------------------------------------------
# Interpolation
# ----------------------------------------------------
def interpolate_column(q_start, q_end, pt_top_A, pt_top_D, pt_bot_A):
    n_questions = q_end - q_start + 1
    n_options   = len(OPTIONS)

    row_vec = (
        (pt_bot_A[0] - pt_top_A[0]) / (n_questions - 1),
        (pt_bot_A[1] - pt_top_A[1]) / (n_questions - 1),
    )
    opt_vec = (
        (pt_top_D[0] - pt_top_A[0]) / (n_options - 1),
        (pt_top_D[1] - pt_top_A[1]) / (n_options - 1),
    )

    result = {}
    for qi in range(n_questions):
        q_num = q_start + qi
        key   = f"Q{q_num}"
        result[key] = {}
        for oi, opt in enumerate(OPTIONS):
            x = pt_top_A[0] + qi * row_vec[0] + oi * opt_vec[0]
            y = pt_top_A[1] + qi * row_vec[1] + oi * opt_vec[1]
            result[key][opt] = [int(round(x)), int(round(y))]

    return result


def compute_bubbles():
    anchor_map = {}
    for i, (col_name, q_key, opt, _) in enumerate(ANCHORS):
        anchor_map[(col_name, q_key, opt)] = clicked[i]

    bubbles = {}
    for col_name, q_start, q_end in COLUMNS:
        pt_top_A = anchor_map[(col_name, f"Q{q_start}", "A")]
        pt_top_D = anchor_map[(col_name, f"Q{q_start}", "D")]
        pt_bot_A = anchor_map[(col_name, f"Q{q_end}",   "A")]
        col_bubbles = interpolate_column(q_start, q_end, pt_top_A, pt_top_D, pt_bot_A)
        bubbles.update(col_bubbles)

    return bubbles

# ----------------------------------------------------
# Mouse callback
# ----------------------------------------------------
def mouse_callback(event, x, y, flags, param):
    global phase, radius_center, radius_center_img, radius_edge
    global bubble_radius, is_panning, pan_start, pan_origin, pan_x, pan_y

    if event == cv2.EVENT_LBUTTONDOWN:
        if space_held:
            is_panning = True
            pan_start  = (x, y)
            pan_origin = (pan_x, pan_y)
            return

        ix, iy = screen_to_image(x, y)

        if phase == PHASE_RADIUS:
            if radius_center is None:
                radius_center     = (x, y)
                radius_center_img = (ix, iy)
                print(f"  Bubble center (image): ({ix}, {iy})")
                draw_state()
            elif radius_edge is None:
                radius_edge   = (x, y)
                display_radius = math.hypot(x - radius_center[0], y - radius_center[1])
                bubble_radius  = int(round(display_radius / zoom))
                print(f"  Bubble edge   (image): ({ix}, {iy})")
                print(f"  Computed radius: {bubble_radius}px")
                phase = PHASE_ANCHORS
                draw_state()

        elif phase == PHASE_ANCHORS:
            if len(clicked) >= len(ANCHORS):
                return
            clicked.append((ix, iy))
            _, _, _, desc = ANCHORS[len(clicked) - 1]
            print(f"  Point {len(clicked)}: {desc} -> ({ix}, {iy})")
            draw_state()

    elif event == cv2.EVENT_LBUTTONUP:
        if is_panning:
            is_panning = False

    elif event == cv2.EVENT_MOUSEMOVE:
        if is_panning:
            pan_x = pan_origin[0] + (x - pan_start[0])
            pan_y = pan_origin[1] + (y - pan_start[1])
            draw_state()

    elif event == cv2.EVENT_MOUSEWHEEL:
        old_zoom = zoom
        if flags > 0:
            new_zoom = min(ZOOM_MAX, zoom * (1 + ZOOM_STEP))
        else:
            new_zoom = max(ZOOM_MIN, zoom * (1 - ZOOM_STEP))
        # zoom toward cursor position
        pan_x = x - (x - pan_x) * (new_zoom / old_zoom)
        pan_y = y - (y - pan_y) * (new_zoom / old_zoom)
        globals()['zoom'] = new_zoom
        draw_state()

# ----------------------------------------------------
# Main loop
# ----------------------------------------------------
cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WINDOW, WINDOW_W, WINDOW_H)
cv2.setMouseCallback(WINDOW, mouse_callback)

print("\n----------------------------------------")
print("Template Calibration - Vigyan Express 40Q")
print("----------------------------------------")
print("Scroll          = zoom in/out")
print("Space + drag    = pan")
print()
print("Phase 1 - Bubble radius:")
print("  1. Click CENTER of any bubble")
print("  2. Click EDGE of that bubble")
print()
print("Phase 2 - Anchor points (12 total):")
for i, (_, _, _, desc) in enumerate(ANCHORS):
    print(f"  {i+1}. {desc}")
print()
print("U   = undo last anchor point")
print("S   = save after all 12 points")
print("ESC = quit without saving")
print("----------------------------------------\n")

draw_state()

while True:
    key = cv2.waitKey(20) & 0xFF

    if key == 32:
        space_held = True
        draw_state()

    elif key == 27:
        print("Exited without saving.")
        break

    elif key == ord('u') or key == ord('U'):
        if phase == PHASE_ANCHORS and clicked:
            removed = clicked.pop()
            print(f"  Undo: removed point {len(clicked)+1} {removed}")
            draw_state()

    elif key == ord('s') or key == ord('S'):
        if phase != PHASE_ANCHORS:
            print("  Complete radius measurement first.")
        elif len(clicked) < len(ANCHORS):
            print(f"  Need {len(ANCHORS)} points, only {len(clicked)} collected.")
        else:
            bubbles = compute_bubbles()
            data = {
                "template_name":  TEMPLATE_NAME,
                "version":        TEMPLATE_VERSION,
                "image_width":    original_width,
                "image_height":   original_height,
                "question_count": QUESTION_COUNT,
                "options":        OPTIONS,
                "bubble_radius":  bubble_radius,
                "fill_threshold": 0.55,
                "roi_padding":    3,
                "bubbles":        bubbles,
            }
            with open(OUTPUT_JSON, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\nSaved {len(bubbles)} questions to:\n  {OUTPUT_JSON}")
            break

    else:
        if space_held:
            space_held = False
            draw_state()

cv2.destroyAllWindows()