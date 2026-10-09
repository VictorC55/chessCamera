"""
Color-agnostic corner refinement.

Reuses the internals of refine_corners.py, but swaps the green-only mask
for an Otsu-based dark/light mask that works on red, blue, black, wood —
any board color.

Usage:
    from refine_any_color import refine_color
    fine = refine_color(img, rough_corners)
"""
import numpy as np
import cv2

# Import the module itself (so we can monkeypatch), then grab what we need.
import refine_corners
from refine_corners import refine as _refine_original


# ======================================================================
# New mask: color-agnostic dark/light split
# ======================================================================
def board_dark_mask(img, corners=None):
    """
    Return 1 where the board's dark squares are, 0 elsewhere.
    Uses the median luminance of the board region as the threshold, so
    the mask splits the board tones roughly 50/50 (which is what light
    and dark squares are). Color-agnostic.

    If corners are given, the region is ERODED to stay inside the board,
    so the border, table, and wall don't pollute the threshold.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 7)

    if corners is not None:
        region = np.zeros_like(gray, dtype=np.uint8)
        pts = np.asarray(corners, dtype=np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(region, [pts], 1)
        # Erode so we stay well inside the board
        region = cv2.erode(region, np.ones((61, 61), np.uint8))

        pixels = gray[region == 1]
        if len(pixels) < 100:
            # fallback if region is tiny
            _, mask = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            return mask.astype(np.float32)

        thresh = float(np.median(pixels))
        mask = ((gray < thresh) & (region == 1)).astype(np.float32)
    else:
        _, mask = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        mask = mask.astype(np.float32)

    return mask


# ======================================================================
# Monkeypatch: replace refine_corners.green_mask with our new mask,
# then expose a wrapper that calls the (now patched) refine().
# ======================================================================
refine_corners.green_mask = board_dark_mask


def refine_color(img, corners):
    """
    Same signature and return value as refine_corners.refine(), but uses
    the color-agnostic mask. Returns whatever refine() returns — either
    the corners array, or a (corners, info_dict) tuple.
    """
    # Import inside the function so the patched version is used.
    from refine_corners import refine
    return refine(img, corners)