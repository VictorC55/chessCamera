"""Snap roughly-placed board corners onto the exact 8x8 checkerboard grid.

The pose model gets corners to within about a square; this fits a perfect
checkerboard to the green squares to get them to about a tenth of a square.
No training: it only uses the mat's colours (green dark squares, white light
squares, white border, non-green floor).

  1. Flatten the board with the rough corners onto a canvas with a 2-square margin.
  2. Align an ideal checkerboard template to the green pixels (OpenCV ECC,
     coarse to fine). If the first fit is weak, retry from rotated starts.
  3. Shift check: a checkerboard also fits one square off, so compare the fit
     with its 8 one-square shifts and keep the one whose 64 squares alternate
     green/white while the ring just outside them has no green (border/floor).
  4. Map the template's outer corners back into the photo.

Usage: python refine_corners.py weights.pt photo.jpg   (writes photo_refined.jpg)
"""
import sys
from pathlib import Path
import cv2
import numpy as np

C = 40                     # canvas pixels per square
M = 2                      # canvas margin in squares; the shift check needs 2
N = (8 + 2 * M) * C
GRID = np.float32([[M * C, M * C], [(M + 8) * C, M * C], [(M + 8) * C, (M + 8) * C], [M * C, (M + 8) * C]])
WEAK_ECC = 0.7             # below this, retry the alignment from rotated starts
ECC_CRITERIA = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-5)


def green_mask(img):
    """1 where the mat's dark (green) squares are; pieces, white squares and floor are 0."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return ((hsv[..., 0] > 35) & (hsv[..., 0] < 95) & (hsv[..., 1] > 50)).astype(np.float32)


def _template(parity):
    t = np.zeros((N, N), np.float32)
    for r in range(8):
        for f in range(8):
            if (r + f) % 2 == parity:
                t[(M + r) * C:(M + r + 1) * C, (M + f) * C:(M + f + 1) * C] = 1
    return t


TEMPLATES = (_template(0), _template(1))


def _canvas(green, corners):
    """Warp the green mask so `corners` land on GRID. Returns (canvas, image->canvas H)."""
    H = cv2.getPerspectiveTransform(np.ascontiguousarray(corners, np.float32), GRID)
    return cv2.warpPerspective(green, H, (N, N)), H


def _ecc(canvas, starts):
    """Best (score, W) aligning a checkerboard template to the canvas; W maps template -> canvas."""
    best = (0.0, None)
    for tmpl in TEMPLATES:  # the corner square nearest corner 0 can be dark or light
        for W0 in starts:
            W = W0.copy()
            try:
                for blur in (41, 21, 9, 3):
                    score, W = cv2.findTransformECC(tmpl, canvas, W, cv2.MOTION_HOMOGRAPHY, ECC_CRITERIA, None, blur)
            except cv2.error:  # did not converge from this start
                continue
            if score > best[0]:
                best = (score, W)
    return best


def _rotated_starts(degrees):
    out = []
    for d in degrees:
        R = cv2.getRotationMatrix2D((N / 2, N / 2), d, 1.0)
        out.append(np.vstack([R, [0, 0, 1]]).astype(np.float32))
    return out


def _grid_quality(canvas):
    """Score each one-square shift of the grid on a canvas where the fit sits at GRID.

    Returns {(dy, dx): (score, contrast, ring_green)}: contrast is how strongly the
    8x8 squares alternate, ring_green how much green is in the ring just outside.
    """
    m = C // 4  # ignore square edges so neighbours don't bleed in
    cells = np.array([[canvas[r * C + m:(r + 1) * C - m, f * C + m:(f + 1) * C - m].mean()
                       for f in range(N // C)] for r in range(N // C)])
    parity = (np.add.outer(np.arange(8), np.arange(8)) % 2).astype(bool)
    out = {}
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            r0, f0 = M + dy, M + dx
            inside = cells[r0:r0 + 8, f0:f0 + 8]
            ring = cells[r0 - 1:r0 + 9, f0 - 1:f0 + 9].copy()
            ring[1:-1, 1:-1] = np.nan
            contrast = abs(inside[parity].mean() - inside[~parity].mean())
            ring_green = np.nanmean(ring)
            out[(dy, dx)] = (contrast - 2 * ring_green, contrast, ring_green)
    return out


def refine(img, corners):
    """Refine 4 rough corners (4x2, cyclic order around the board) against the checkerboard.

    Returns (corners 4x2 in the same order, info dict). info["ok"] is False when the
    fitted grid doesn't look like a clean 8x8 board; keep the model's corners then.
    """
    green = green_mask(img)
    corners = np.ascontiguousarray(corners, np.float32).reshape(4, 2)
    identity = [np.eye(3, dtype=np.float32)]

    canvas, H = _canvas(green, corners)
    score, W = _ecc(canvas, identity)
    if score < WEAK_ECC:
        score, W = _ecc(canvas, _rotated_starts((0, -10, 10, -20, 20)))
    if W is None:
        return corners, {"ok": False, "ecc": 0.0, "shift": (0, 0), "contrast": 0.0, "ring_green": 1.0}
    fitted = cv2.perspectiveTransform(cv2.perspectiveTransform(GRID[None], W), np.linalg.inv(H))[0]

    # shift check on a canvas built from the fitted corners
    canvas, H = _canvas(green, fitted)
    quality = _grid_quality(canvas)
    shift = max(quality, key=lambda k: quality[k][0])
    if shift != (0, 0):
        moved = GRID + np.float32([shift[1] * C, shift[0] * C])
        fitted = cv2.perspectiveTransform(moved[None], np.linalg.inv(H))[0]
        canvas, H = _canvas(green, fitted)
        score, W = _ecc(canvas, identity)  # re-polish from the corrected position
        if W is not None:
            fitted = cv2.perspectiveTransform(cv2.perspectiveTransform(GRID[None], W), np.linalg.inv(H))[0]
            canvas, H = _canvas(green, fitted)
        quality = _grid_quality(canvas)

    _, contrast, ring_green = quality[(0, 0)]
    ok = contrast > 0.3 and ring_green < 0.1
    return fitted, {"ok": ok, "ecc": float(score), "shift": shift, "contrast": float(contrast),
                    "ring_green": float(ring_green)}


if __name__ == "__main__":
    from ultralytics import YOLO
    weights, photo = sys.argv[1], Path(sys.argv[2])
    img = cv2.imread(str(photo))
    r = YOLO(weights).predict(img, imgsz=960, max_det=1, verbose=False)[0]
    if not len(r.boxes):
        sys.exit("board not found")
    rough = r.keypoints.xy[0].cpu().numpy()
    fine, info = refine(img, rough)
    print("model corners:  ", rough.round(1).tolist())
    print("refined corners:", fine.round(1).tolist())
    print("check:", info)
    for pts, color in ((rough, (0, 0, 255)), (fine, (255, 128, 0))):
        cv2.polylines(img, [pts.astype(np.int32).reshape(-1, 1, 2)], True, color, 4)
    out = photo.with_name(photo.stem + "_refined.jpg")
    cv2.imwrite(str(out), img)
    print("saved", out)
