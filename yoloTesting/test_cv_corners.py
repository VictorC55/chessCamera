"""
Standalone test for CV-based corner detection.
Tries two methods (Hough lines + contour quadrilateral) and draws both.

Usage:
    python yoloTesting/test_cv_corners.py pictures/archaic1.jpg
"""
import sys
from itertools import combinations
import numpy as np
import cv2


def order_corners_leftmost_first(pts):
    """Order 4 points: leftmost first, then clockwise."""
    pts = np.array(pts, dtype=float)
    leftmost_idx = int(np.argmin(pts[:, 0]))
    pts = np.roll(pts, -leftmost_idx, axis=0)
    cross = ((pts[1, 0] - pts[0, 0]) * (pts[2, 1] - pts[0, 1])
             - (pts[1, 1] - pts[0, 1]) * (pts[2, 0] - pts[0, 0]))
    if cross < 0:
        pts = np.array([pts[0], pts[3], pts[2], pts[1]])
    return pts


# ======================================================================
# Method 1: Contour quadrilateral (robust)
# ======================================================================
def corners_from_contours(img, debug=False):
    """Largest convex quadrilateral in the image."""
    # Downscale so edge detection doesn't pick up every pixel of wood grain
    H0, W0 = img.shape[:2]
    scale = 1200 / max(H0, W0)
    if scale < 1:
        small = cv2.resize(img, (int(W0 * scale), int(H0 * scale)))
    else:
        small = img
    H, W = small.shape[:2]

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # Try several Canny thresholds, accumulate contours
    candidates = []
    for lo, hi in [(30, 80), (50, 150), (80, 200)]:
        edges = cv2.Canny(gray, lo, hi)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:15]:
            area = cv2.contourArea(c)
            if area < 0.03 * H * W:
                continue
            hull = cv2.convexHull(c)
            peri = cv2.arcLength(hull, True)
            # Try a range of epsilon values
            for eps in (0.01, 0.02, 0.03, 0.05, 0.08):
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    pts = approx.reshape(4, 2).astype(float) / scale
                    candidates.append((area, pts, lo, hi, eps))
                    break

    if debug:
        print(f"  [contours] {len(candidates)} candidates across threshold sweeps")

    if not candidates:
        return None

    # Pick largest
    candidates.sort(key=lambda c: -c[0])
    area, pts, lo, hi, eps = candidates[0]
    if debug:
        print(f"  [contours] picked area={area:.0f}, canny=({lo},{hi}), eps={eps}")
    return pts


# ======================================================================
# Method 2: Hough lines (fixed)
# ======================================================================
def corners_from_hough(img, debug=False):
    H0, W0 = img.shape[:2]
    scale = 1600 / max(H0, W0)
    small = cv2.resize(img, (int(W0 * scale), int(H0 * scale))) if scale < 1 else img
    H, W = small.shape[:2]

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    min_len = int(0.25 * min(H, W))
    max_gap = int(0.05 * min(H, W))

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                            threshold=80,
                            minLineLength=min_len,
                            maxLineGap=max_gap)
    if lines is None:
        return None

    # ---- robust reshape: always (N, 4) ----
    segs = np.asarray(lines).reshape(-1, 4)
    if debug:
        print(f"  [hough] {len(segs)} raw segments")

    bins = {"horiz": [], "vert": [], "diag+": [], "diag-": []}
    for x1, y1, x2, y2 in segs:
        dx, dy = x2 - x1, y2 - y1
        length = float(np.hypot(dx, dy))
        ang = float(np.degrees(np.arctan2(dy, dx)) % 180)
        if ang < 20 or ang > 160:
            bins["horiz"].append((x1, y1, x2, y2, length))
        elif 70 < ang < 110:
            bins["vert"].append((x1, y1, x2, y2, length))
        elif 20 <= ang <= 70:
            bins["diag+"].append((x1, y1, x2, y2, length))
        else:
            bins["diag-"].append((x1, y1, x2, y2, length))

    if debug:
        for k, v in bins.items():
            print(f"  [hough] bin {k}: {len(v)}")

    def top_n(bin_list, n=3):
        return sorted(bin_list, key=lambda s: -s[4])[:n]

    all_lines = (top_n(bins["horiz"]) + top_n(bins["vert"])
                 + top_n(bins["diag+"]) + top_n(bins["diag-"]))

    if len(all_lines) < 4:
        return None

    intersections = []
    for a, b in combinations(all_lines, 2):
        p = line_intersection(a, b)
        if p is None:
            continue
        x, y = p
        if 0 <= x < W and 0 <= y < H:
            intersections.append((x, y))

    if debug:
        print(f"  [hough] {len(intersections)} intersections inside image")

    if len(intersections) < 4:
        return None

    best = None
    for quad in combinations(intersections, 4):
        pts = np.array(quad, dtype=np.float32).reshape(-1, 1, 2)
        if not cv2.isContourConvex(pts):
            continue
        area = cv2.contourArea(pts)
        if best is None or area > best[0]:
            best = (area, np.array(quad, dtype=float))

    if best is None:
        return None
    return best[1] / scale


def line_intersection(l1, l2):
    x1, y1, x2, y2 = l1[:4]
    x3, y3, x4, y4 = l2[:4]
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-6:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4)
          - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4)
          - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return float(px), float(py)


# ======================================================================
# Main
# ======================================================================
def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python test_cv_corners.py <image>")
    path = sys.argv[1]
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(f"Cannot read {path}")
    H, W = img.shape[:2]
    print(f"Image: {path}  ({W}x{H})")

    vis = img.copy()

    print("\nMethod 1: contour quadrilateral")
    c_pts = corners_from_contours(img, debug=True)
    if c_pts is not None:
        c_pts = order_corners_leftmost_first(c_pts)
        for i, (x, y) in enumerate(c_pts):
            print(f"  corner[{i}] = ({x:.0f}, {y:.0f})")
        cv2.polylines(vis, [c_pts.astype(np.int32).reshape(-1, 1, 2)],
                      True, (0, 255, 0), 6)
        for x, y in c_pts:
            cv2.circle(vis, (int(x), int(y)), 20, (0, 255, 0), -1)
    else:
        print("  no quadrilateral found")

    print("\nMethod 2: Hough lines")
    h_pts = corners_from_hough(img, debug=True)
    if h_pts is not None:
        h_pts = order_corners_leftmost_first(h_pts)
        for i, (x, y) in enumerate(h_pts):
            print(f"  corner[{i}] = ({x:.0f}, {y:.0f})")
        cv2.polylines(vis, [h_pts.astype(np.int32).reshape(-1, 1, 2)],
                      True, (0, 0, 255), 6)
        for x, y in h_pts:
            cv2.circle(vis, (int(x), int(y)), 20, (0, 0, 255), -1)
    else:
        print("  no corners found")

    out = "cv_corners_test.jpg"
    cv2.imwrite(out, vis)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()