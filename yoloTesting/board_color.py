"""
Find the board from the colour of its dark squares, without the corner model.

The corner model was trained on one green mat from one angle and finds
nothing on other boards. But coloured dark squares (green, red, blue,
brown) are the most saturated thing in most frames, and within one hue
band they form a grid of similar-sized blobs that nothing else in the
frame looks like:

  1. Among saturated pixels, try every hue band (each centre, narrow and
     wide) and keep the few whose square-shaped blobs sit on a checkerboard
     lattice (diagonal neighbours ~1.4 squares apart). Each candidate goes
     through steps 2-3 and the band with the best checkerboard fit (ECC)
     wins.
  2. Rough corners: close the hue mask with a kernel about two squares
     wide, which fills the light squares and the pieces between dark
     squares but not the floor around the board, so the board becomes one
     solid region. A quadrilateral around the largest region is within
     about a square of the true board edge, which is what refine_corners
     needs; its shift check fixes the rest.
  3. Refinement uses the same hue mask, so the checkerboard fit sees only
     dark squares instead of a brightness split that also catches cream
     squares, white pieces and a light floor.

Boards whose dark squares are grey/black/brown-without-saturation are not
handled here (no hue to find); the brightness mask in refine_any_color.py
still covers those.

Usage:
    from board_color import search_color, detect_corners_color, refine_hue
    best = search_color(img)                 # None, or (fine corners, info, candidate)
    # or step by step:
    for cand in detect_corners_color(img):   # dicts with corners, hue, half, n_squares
        fine, info = refine_hue(img, cand["corners"], cand["hue"], cand["half"])

    python yoloTesting/board_color.py frame.jpg   # writes frame_color.jpg
"""
import sys
from pathlib import Path

import cv2
import numpy as np

import refine_corners
from refine_corners import refine as _refine

MIN_SAT = 70        # dark squares are clearly coloured; floor, cream squares and white pieces are not
MIN_VAL = 50        # ignore shadows, where hue is noise
HUE_HALF = 7        # half-width of the narrow hue band (OpenCV hue runs 0-179); the wide band is
                    # twice this, for a green mat under mixed light that spreads over ~30 hue steps
MIN_SQUARES = 6     # fewer square-like blobs than this is not a board
WORK_SIZE = 1920    # longest side the colour search runs at (1280 loses the hairline gaps between squares)


def _hue_band(hsv, centre, half=HUE_HALF):
    """1 where the pixel is saturated and its hue is within `half` of `centre` (hue wraps at 180)."""
    h, s, v = hsv[..., 0].astype(np.int16), hsv[..., 1], hsv[..., 2]
    d = np.abs(h - centre)
    d = np.minimum(d, 180 - d)
    return ((d <= half) & (s >= MIN_SAT) & (v >= MIN_VAL)).astype(np.uint8)


def _square_blobs(mask, img_area):
    """Contours of the mask that look like one board square seen in perspective."""
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        area = cv2.contourArea(c)
        if not (img_area * 2e-5 < area < img_area * 0.02):
            continue
        hull = cv2.convexHull(c)
        solidity = area / max(cv2.contourArea(hull), 1)
        if solidity < 0.75:  # a square, possibly with a piece's base bitten out of one side
            continue
        poly = cv2.approxPolyDP(hull, 0.06 * cv2.arcLength(hull, True), True)
        if not 4 <= len(poly) <= 6:
            continue
        out.append(c)
    if len(out) < MIN_SQUARES:
        return out
    # keep blobs of the board's size: squares shrink with distance, but not by 10x
    areas = np.array([cv2.contourArea(c) for c in out])
    med = np.median(areas)
    return [c for c, a in zip(out, areas) if med / 6 < a < med * 6]


def _on_lattice(blobs):
    """Per blob: is another blob of similar size where a diagonal neighbour square would be?

    A dark square's nearest dark neighbours are its diagonal ones: offset by about one square
    width across and one square height down. Offsets are measured in each blob's own width and
    height, because from a low camera a square can look four times wider than it is tall. Wood
    grain, fabric folds and piece highlights also make square-ish blobs, but rarely in this
    arrangement. Pieces hide many squares, so one neighbour is enough.
    """
    if len(blobs) < 2:
        return np.zeros(len(blobs), bool)
    boxes = np.array([cv2.boundingRect(c) for c in blobs], float)
    cents = boxes[:, :2] + boxes[:, 2:] / 2
    areas = np.array([cv2.contourArea(c) for c in blobs])
    dx = np.abs(cents[None, :, 0] - cents[:, None, 0]) / boxes[:, None, 2]
    dy = np.abs(cents[None, :, 1] - cents[:, None, 1]) / boxes[:, None, 3]
    ratio = areas[None, :] / areas[:, None]
    diag = (dx > 0.4) & (dx < 1.6) & (dy > 0.4) & (dy < 1.6) & (ratio > 0.4) & (ratio < 2.5)
    np.fill_diagonal(diag, False)
    return diag.any(1)


def _hue_candidates(hsv, keep=3):
    """[(hue centre, half-width, square blobs)]: the `keep` hue bands whose square-like blobs sit
    most like a checkerboard lattice, at least 12 hue steps apart, each with MIN_SQUARES blobs.

    Every centre is tried at a narrow and a wide band instead of looking for histogram peaks: a red
    board's peak sits right next to the cream pieces' and a wooden floor's hump is bumpy, so peak
    finding either merges bands or misses the board. Scoring all 72 bands takes ~0.2s at WORK_SIZE.
    """
    sat = (hsv[..., 1] >= MIN_SAT) & (hsv[..., 2] >= MIN_VAL)
    if sat.sum() < 1000:
        return []
    area = hsv.shape[0] * hsv.shape[1]
    scored = []
    for centre in range(0, 180, 5):
        for half in (HUE_HALF, 2 * HUE_HALF):
            # erode first: diagonal neighbours touch at their corners and would merge into one blob
            mask = cv2.erode(_hue_band(hsv, centre, half), np.ones((5, 5), np.uint8))
            blobs = _square_blobs(mask, area)
            if len(blobs) >= MIN_SQUARES:
                scored.append(((int(_on_lattice(blobs).sum()), len(blobs)), centre, half, blobs))
    out = []
    for _, centre, half, blobs in sorted(scored, key=lambda c: c[0], reverse=True):
        if all(min(abs(centre - c), 180 - abs(centre - c)) >= 12 for c, _, _ in out):
            out.append((centre, half, blobs))
        if len(out) == keep:
            break
    return out


def _board_region(mask, blobs, work_w=640):
    """Points on the outline of the largest region left after closing `mask` by ~2 squares, or None."""
    # Keep only the parts of the mask that hold a square blob, or closing would glue a same-hue
    # shoe, sleeve or hand onto the board. (Requiring lattice squares instead drops too much of
    # a board seen from a low angle; a size cap per square didn't help either.)
    side = float(np.median([np.sqrt(cv2.contourArea(c)) for c in blobs]))
    n, labels = cv2.connectedComponents(mask)
    seeds = np.zeros(n, int)
    for c in blobs:
        x, y = c.reshape(-1, 2).mean(0).astype(int)
        seeds[labels[y, x]] += 1
    keep = seeds > 0
    keep[0] = False
    if not keep.any():
        return None
    mask = keep[labels].astype(np.uint8)
    scale = work_w / mask.shape[1]
    small = cv2.resize(mask, (work_w, int(round(mask.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    sq = side * scale
    k = max(5, int(2.2 * sq) | 1)
    closed = cv2.morphologyEx((small > 0).astype(np.uint8), cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(closed)
    if n < 2:
        return None
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    contours, _ = cv2.findContours((labels == biggest).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(contours, key=cv2.contourArea).reshape(-1, 2) / scale


def _quad_from_points(pts):
    """Best-fitting 4-gon around a point set: hull, simplified until it has 4 vertices."""
    hull = cv2.convexHull(pts.astype(np.float32))
    peri = cv2.arcLength(hull, True)
    for eps in np.linspace(0.01, 0.15, 29):
        poly = cv2.approxPolyDP(hull, eps * peri, True)
        if len(poly) == 4:
            return poly.reshape(4, 2).astype(float)
        if len(poly) < 4:
            break
    # could not simplify to exactly 4: fall back to a rotated rectangle
    return cv2.boxPoints(cv2.minAreaRect(hull)).astype(float)


def detect_corners_color(img):
    """Rough board corners for each plausible dark-square colour band.

    Returns [{"corners": 4x2 (leftmost first, then clockwise), "hue": hue centre,
    "half": hue band half-width, "n_squares": square blobs in that band}], most lattice-like band first.
    The caller should refine each with refine_hue() and keep the highest ECC.
    """
    from chess_pipeline import _order_corners
    # work at a fixed size so the erosion and blob-size limits mean the same thing on a phone photo and a video frame
    scale = min(1.0, WORK_SIZE / max(img.shape[:2]))
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    out = []
    for hue, half, blobs in _hue_candidates(hsv):
        pts = _board_region(_hue_band(hsv, hue, half), blobs)
        if pts is None or len(pts) < 4:
            continue
        corners = _order_corners(_quad_from_points(pts)) / scale
        out.append({"corners": corners, "hue": int(hue), "half": half, "n_squares": len(blobs)})
    return out


def search_color(img, retries=True):
    """Best colour-based fit: (fine corners, info, candidate) with the highest ECC, or None."""
    # every candidate gets the full fit: from these rough quads the right band often only fits
    # after the rotated restarts, so a quick fit would hand the win to a wrong band
    best = None
    for cand in detect_corners_color(img):
        fine, info = refine_hue(img, cand["corners"], cand["hue"], cand["half"], retries=retries)
        if best is None or info["ecc"] > best[1]["ecc"]:
            best = (fine, info, cand)
    return best


def refine_hue(img, corners, hue, half=HUE_HALF, retries=True):
    """refine_corners.refine() with the board's own dark-square hue band in place of green.
    retries=False skips the slow rotated restarts (for tracking from a near-correct quad)."""
    original, weak = refine_corners.green_mask, refine_corners.WEAK_ECC
    refine_corners.green_mask = lambda im: _hue_band(cv2.cvtColor(im, cv2.COLOR_BGR2HSV), hue, half).astype(np.float32)
    if not retries:
        refine_corners.WEAK_ECC = 0.0
    try:
        fine, info = _refine(img, corners)
    finally:
        refine_corners.green_mask, refine_corners.WEAK_ECC = original, weak
    info["ecc"] = float(info["ecc"])
    return fine, info


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python board_color.py <image>")
    path = Path(sys.argv[1])
    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"cannot read {path}")
    best = None
    for cand in detect_corners_color(img):
        f, i = refine_hue(img, cand["corners"], cand["hue"], cand["half"])
        print(f"  candidate hue {cand['hue']:3d}±{cand['half']}: {cand['n_squares']:2d} square blobs, ecc {i['ecc']:.2f}")
        if best is None or i["ecc"] > best[1]["ecc"]:
            best = (f, i, cand)
    if best is None:
        raise SystemExit("no coloured checkerboard found")
    fine, info, found = best
    print(f"dark-square hue {found['hue']}±{found['half']}, {found['n_squares']} square blobs")
    print("rough:", found["corners"].round().astype(int).tolist())
    print("fine: ", np.asarray(fine).round().astype(int).tolist())
    print("check:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in info.items()})
    out = img.copy()
    for pts, color in ((found["corners"], (0, 0, 255)), (fine, (0, 255, 0))):
        cv2.polylines(out, [np.asarray(pts, np.int32).reshape(-1, 1, 2)], True, color, 4)
    dst = path.with_name(path.stem + "_color.jpg")
    cv2.imwrite(str(dst), out)
    print("saved", dst)
