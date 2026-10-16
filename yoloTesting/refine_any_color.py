"""
Color-agnostic corner refinement.

Reuses the internals of refine_corners.py but swaps the green-only mask
for an Otsu + median threshold mask that works on red, blue, black, wood —
any board color.

The key trick: refine() internally calls green_mask(img) with just one
argument, so we can't pass corners through directly. Instead, we
temporarily replace refine_corners.green_mask with a closure that has
the corners already baked in.

Usage:
    from refine_any_color import refine_color
    fine = refine_color(img, rough_corners)
"""
import numpy as np
import cv2

# Grab the module so we can monkeypatch its green_mask symbol at call time
import refine_corners
from refine_corners import refine as _refine


# ======================================================================
# Color-agnostic mask
# ======================================================================
def board_dark_mask(img, corners=None):
    """
    Return 1 where the board's dark squares are, 0 elsewhere.

    Strategy:
      - Grayscale + median blur to kill noise and piece edges.
      - If corners are given, restrict attention to the inside of the board
        (erode the corner polygon so we stay away from the border, table,
        wall, and pieces).
      - Threshold the board region at the MEDIAN luminance of its pixels.
        This splits the board's tones roughly 50/50, which is exactly what
        light squares and dark squares are.
      - Else (no corners), fall back to Otsu on the whole image.

    Works for green, red, blue, black, wood, cream — any board color.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 7)

    if corners is None:
        _, mask = cv2.threshold(gray, 0, 1,
                                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return mask.astype(np.float32)

    # Restrict to inside the board
    region = np.zeros_like(gray, dtype=np.uint8)
    pts = np.asarray(corners, dtype=np.int32).reshape(-1, 1, 2)
    cv2.fillPoly(region, [pts], 1)
    # Erode so we pull away from the border and pieces near the edges
    region = cv2.erode(region, np.ones((61, 61), np.uint8))

    pixels = gray[region == 1]
    if len(pixels) < 100:
        # Region too small — fall back to Otsu on the whole image
        _, mask = cv2.threshold(gray, 0, 1,
                                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return mask.astype(np.float32)

    # Threshold on the median luminance of the board region
    thresh = float(np.median(pixels))
    mask = ((gray < thresh) & (region == 1)).astype(np.float32)
    return mask


# ======================================================================
# Wrapper that binds corners into the mask before calling refine()
# ======================================================================
def refine_color(img, corners):
    """
    Same return shape as refine_corners.refine():
        (refined_corners, info_dict)   OR   refined_corners

    Uses board_dark_mask instead of the default green_mask.
    """
    original_green_mask = refine_corners.green_mask

    # refine() calls green_mask(img) with one arg, so we build a closure
    # that captures `corners` and satisfies that 1-arg signature.
    def bound_mask(_img):
        return board_dark_mask(_img, corners)

    refine_corners.green_mask = bound_mask
    try:
        return _refine(img, corners)
    finally:
        # Always restore, even if refine() raised
        refine_corners.green_mask = original_green_mask


# ======================================================================
# Quick self-test
# ======================================================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python refine_any_color.py <image> [corners.json]")
    img = cv2.imread(sys.argv[1])
    if img is None:
        raise SystemExit(f"Cannot read {sys.argv[1]}")

    # Default rough corners (from piece-hull test on archaic1.jpg)
    corners = np.array([[84, 1695], [1315, 331], [2750, 1625], [1519, 2990]],
                       dtype=float)

    result = refine_color(img, corners)
    fine = result[0] if isinstance(result, tuple) else result
    info = result[1] if isinstance(result, tuple) else None

    print("Refined corners:")
    for i, (x, y) in enumerate(fine):
        print(f"  [{i}] ({x:.0f}, {y:.0f})")
    print()
    if info:
        print("Refine info:")
        for k, v in info.items():
            print(f"  {k} = {v}")