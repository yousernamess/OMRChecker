# OMRChecker

**An easy-to-use 4-step process that works with any custom OMR sheet** -- just add 4 black square markers to the corners of your sheet, calibrate once, and read unlimited scanned sheets automatically.

## How It Works (4 Steps)

| Step | What You Do | What Happens |
|---|---|---|
| 1 | **Install** | Clone repo + install dependencies |
| 2 | **Calibrate** | Run calibration tool, click 12 anchor points on your sheet once |
| 3 | **Scan & Read** | Place scanned sheet in `input/`, run one command |
| 4 | **Get Results** | Answers printed to terminal |

That's it. Works with any sheet layout -- 10 questions or 200, 4 options or 5, single column or multi-column. You just need **4 black square markers** (fiducials) in the corners of your OMR sheet for alignment.

> **No markers on your sheet?** Print or draw small filled black squares (~5-10mm) in each corner of your OMR sheet before scanning. These are what `align.py` uses to correct for scan skew, rotation, and perspective distortion.

## Features

- **PDF & Image Input** -- Accepts both `.pdf` and image files (`.jpeg`, `.png`, etc.)
- **Automatic Alignment** -- Perspective correction using 4 corner black square markers, so sheets don't need to be perfectly scanned
- **Calibration Tool** -- Interactive GUI to map bubble positions for any OMR sheet layout (one-time setup per sheet format)
- **Bubble Detection** -- Reads fill level of each bubble using circular ROI analysis with configurable thresholds
- **Works with any OMR sheet** -- 40 questions, 100 questions, 5 columns, 2 columns -- calibrate once and it reads every time

## Project Structure

```
omrPrototype/
  input/                  # Place scanned OMR sheets here
    template.pdf          # Sample/template sheet
  output/                 # Generated debug/aligned images
  src/
    preprocess.py         # Image loading (PDF/image), resize, grayscale, threshold
    align.py              # Corner marker detection + perspective warp
    calibrate.py          # Interactive GUI to calibrate bubble positions
    bubble_reader.py      # Main OMR reader -- reads answers from a sheet
    check.py              # Quick sanity-check script
  templates/
    calibration_points.json  # Bubble coordinates for the current template
  requirements.txt
```

## Requirements

```
opencv-python
numpy
pillow
pymupdf
matplotlib
```

## Step-by-Step Guide

### Step 1: Install

```bash
git clone https://github.com/yousernamess/OMRChecker.git
cd OMRChecker
pip install -r requirements.txt
```

### Step 2: Calibrate for Your OMR Sheet (One-Time Setup)

> **Skip this step** if you're using the included `vigyan_express_40_v1` template. Go straight to Step 3.

For any **new/custom OMR sheet**, you need to calibrate once so the system knows where each bubble is located:

1. Make sure your sheet has **4 black square markers** in the corners
2. Scan it or convert the PDF to an image and place it in `input/`
3. Open `src/calibrate.py` and update the `IMAGE_PATH` at the top to point to your sheet:

```python
IMAGE_PATH = BASE_DIR / "input" / "your_custom_sheet.pdf"
```

4. Also update these constants if your sheet differs from the default 40-question, 4-option layout:

```python
OPTIONS = ["A", "B", "C", "D"]          # Change to ["A","B","C","D","E"] if 5 options
QUESTION_COUNT = 40                      # Total questions on your sheet
```

Update the `COLUMNS` list to match your sheet's column structure. For example, 2 columns of 20 questions each:

```python
COLUMNS = [
    ("C1", 1,  20),
    ("C2", 21, 40),
]
```

5. Run the calibration tool:

```bash
python src/calibrate.py
```

6. Follow the on-screen prompts:

**Phase 1 -- Bubble Radius (2 clicks):**
- Click the **center** of any bubble on your sheet
- Click the **edge** of the same bubble
- This tells the system how big your bubbles are

**Phase 2 -- Anchor Points (12 clicks for 4 columns):**
- The tool prompts you to click 3 anchor points per column:
  - **Q_first, Option A** (top-left bubble of first question)
  - **Q_first, Option D** (top-right bubble of first question)
  - **Q_last, Option A** (bottom-left bubble of last question)
- The system interpolates all other bubble positions from these 3 points per column

**Controls:**

| Key | Action |
|---|---|
| Scroll | Zoom in/out |
| Space + Drag | Pan the image |
| U | Undo last anchor point |
| S | Save calibration (after all points collected) |
| ESC | Quit without saving |

7. On save, the tool generates `templates/calibration_points.json` with all bubble coordinates. This file is what `bubble_reader.py` uses at runtime.

> **Tip:** You can re-calibrate at any time if your sheet layout changes. Just run `calibrate.py` again.

### Step 3: Read an OMR Sheet

Place your scanned sheet (PDF or image) in the `input/` folder, then run:

```bash
python src/bubble_reader.py input/your_sheet.jpg
```

This will:
1. Load and resize the image to standard dimensions (2382 x 3368)
2. Detect corner markers and align the sheet via perspective warp
3. Read each bubble using the calibrated template
4. Print detected answers for all questions

Optionally pass a question count to read fewer questions:

```bash
python src/bubble_reader.py input/your_sheet.jpg 20
```

### Step 4 (Optional): Debug Alignment

If sheets aren't reading correctly, check whether the corner markers are being detected properly:

```bash
python src/align.py input/your_sheet.jpg
```

This saves a debug image to `output/debug_markers.png` with colored circles and labels on each detected marker.

### Quick Test

```bash
python src/check.py
```

Loads `input/template.pdf`, prints its shape, and saves to `output/blank_check.png`.

## How It Works

1. **Preprocessing** (`preprocess.py`) -- Converts input to a standardized 2382x3368 image, applies grayscale + adaptive thresholding
2. **Alignment** (`align.py`) -- Finds 4 corner fiducial markers in the outer 15% of the image, applies perspective warp to correct for scan skew/rotation
3. **Bubble Reading** (`bubble_reader.py`) -- For each question, computes a circular mask at each option's coordinates, counts dark pixels inside, and picks the option with the highest fill. Uses two thresholds:
   - **Absolute threshold** (0.35) -- minimum fill to consider a bubble marked
   - **Difference threshold** (0.08) -- minimum gap between best and second-best to confirm a single answer

## Adapting to New Sheet Formats

1. Add **4 black square markers** to the corners of your sheet (if not already present)
2. Scan it (or convert PDF to image) and place in `input/`
3. Update `calibrate.py` constants (`IMAGE_PATH`, `COLUMNS`, `OPTIONS`, `QUESTION_COUNT`) to match your sheet
4. Run `python src/calibrate.py` and follow the prompts (2 radius clicks + 12 anchor clicks)
5. Test with `python src/bubble_reader.py input/your_sheet.jpg`

## License

MIT
