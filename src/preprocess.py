import cv2
import fitz
import numpy as np


TARGET_WIDTH = 2382
TARGET_HEIGHT = 3368


def load_image_from_path(path):
    lower = path.lower()

    if lower.endswith(".pdf"):
        doc = fitz.open(path)
        page = doc[0]

        pix = page.get_pixmap(matrix=fitz.Matrix(4,4))

        img = np.frombuffer(
            pix.samples,
            dtype=np.uint8
        ).reshape(
            pix.height,
            pix.width,
            pix.n
        )

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    else:
        img = cv2.imread(path)

    img = cv2.resize(
        img,
        (TARGET_WIDTH, TARGET_HEIGHT)
    )

    return img


def preprocess(img):

    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        15
    )

    return gray, thresh