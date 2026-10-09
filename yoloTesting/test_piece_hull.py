"""
Find board corners using piece detections.
Pieces are always inside the board, so their convex hull approximates
the board boundary (we expand it by ~1 square).

Usage:
    python yoloTesting/test_piece_hull.py pictures/archaic1.jpg
"""
import sys
from pathlib import Path
import numpy as np
import cv2
from huggingface_hub import hf_hub_download
from ultralytics import YOLO


PIECE_MODEL_HF = "KanisornPutta/chess-model-yolov8m"
PIECE_MODEL_FILE = "chess-model-yolov8m.pt"


def corners_from_pieces(img, piece_model):
    """
    Take all piece detections, build a min-area rectangle around them,
    expand outward to cover the full board, return 4 corners.
    """
    r = piece_model(img, conf=0.4, verbose=False)[0]
    boxes = []
    sizes = []
    for b in r.boxes:
        x1, y1, x2, y2 = [float(v) for v in b.xyxy[0]]
        cx = (x1 + x2) / 2
        cy = y2  # bottom-center (piece base, where it touches the board)
        boxes.append((cx, cy))
        sizes.append(((x2 - x1), (y2 - y1)))  # width, height

    if len(boxes) < 6:
        print(f"  only {len(boxes)} pieces — not enough for hull")
        return None

    pts = np.array(boxes, dtype=np.float32)

    # Estimate 1 square in pixels from the median piece width and height.
    # A pawn's bbox ≈ 1 square wide, ≈ 1.2 squares tall (with vertical extent).
    widths = np.array([s[0] for s in sizes])
    heights = np.array([s[1] for s in sizes])
    sq_w = float(np.median(widths))
    sq_h = float(np.median(heights) / 1.2)

    print(f"  {len(boxes)} pieces, estimated square ≈ {sq_w:.0f}x{sq_h:.0f} px")

    # Min-area rectangle around piece base points
    rect = cv2.minAreaRect(pts)
    (cx, cy), (w, h), angle = rect
    print(f"  minAreaRect: center=({cx:.0f},{cy:.0f}) size=({w:.0f}x{h:.0f}) angle={angle:.1f}")

    # Expand: pieces sit inside squares, so the board extends roughly
    # 1 square beyond the piece hull on all sides.

    sq = sq_w          # use width only — more reliable than height
    w_exp = w + 2.5 * sq   # 1.25 squares per side
    h_exp = h + 2.5 * sq

    # Rotated rectangle corners
    rect_pts = cv2.boxPoints(((cx, cy), (w_exp, h_exp), angle))
    return rect_pts.astype(float)


def order_corners_leftmost_first(pts):
    pts = np.array(pts, dtype=float)
    leftmost_idx = int(np.argmin(pts[:, 0]))
    pts = np.roll(pts, -leftmost_idx, axis=0)
    cross = ((pts[1, 0] - pts[0, 0]) * (pts[2, 1] - pts[0, 1])
             - (pts[1, 1] - pts[0, 1]) * (pts[2, 0] - pts[0, 0]))
    if cross < 0:
        pts = np.array([pts[0], pts[3], pts[2], pts[1]])
    return pts


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python test_piece_hull.py <image>")
    path = sys.argv[1]
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(f"Cannot read {path}")

    print("Loading piece model...")
    piece_model = YOLO(hf_hub_download(PIECE_MODEL_HF, PIECE_MODEL_FILE))

    corners = corners_from_pieces(img, piece_model)
    if corners is None:
        raise SystemExit("Failed to find corners.")

    corners = order_corners_leftmost_first(corners)
    print("\nCorners (leftmost-first, clockwise):")
    for i, (x, y) in enumerate(corners):
        print(f"  corner[{i}] = ({x:.0f}, {y:.0f})")

    vis = img.copy()
    cv2.polylines(vis, [corners.astype(np.int32).reshape(-1, 1, 2)],
                  True, (0, 255, 0), 6)
    for x, y in corners:
        cv2.circle(vis, (int(x), int(y)), 20, (0, 255, 0), -1)

    out = "piece_hull_test.jpg"
    cv2.imwrite(out, vis)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()