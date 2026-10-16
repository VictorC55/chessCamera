"""
Debug visualization for the color-agnostic chess pipeline.

Draws on the image:
  - green corner quad
  - blue square labels (a8, h8, ..., h1)
  - red piece boxes with "class@square" labels
And prints the FEN.

Usage:
    python yoloTesting/debug_any_board.py pictures/archaic1.jpg
"""
import sys
from pathlib import Path
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chess_pipeline import (
    load_models, detect_pieces, detect_corners_yolo,
    detect_corners_piece_hull, make_homography, pixel_to_square,
    pick_orientation, dedupe_and_map, fen_from_squares, S,
)
from refine_any_color import refine_color
import chess


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python debug_any_board.py <image>")
    img_path = sys.argv[1]
    img = cv2.imread(img_path)
    if img is None:
        raise SystemExit(f"Cannot read {img_path}")
    H_img, W_img = img.shape[:2]
    print(f"Image: {img_path}  ({W_img}x{H_img})")

    print("\nLoading models...")
    pm, cm = load_models()

    # --- pieces ---
    print("Detecting pieces...")
    pieces = detect_pieces(img_path, pm)
    print(f"  {len(pieces)} piece detections")

    # --- corners (YOLO first, hull fallback) ---
    print("Detecting corners...")
    rough = detect_corners_yolo(img_path, cm)
    source = "yolo"
    if rough is None:
        print("  yolo corner model failed -> piece-hull fallback")
        rough = detect_corners_piece_hull(img, pieces)
        source = "hull"
    if rough is None:
        raise SystemExit("  no corners found")
    print(f"  rough ({source}): {np.asarray(rough).astype(int).tolist()}")

    # --- refine ---
    print("Refining corners...")
    result = refine_color(img, rough)
    fine = result[0] if isinstance(result, tuple) else result
    info = result[1] if isinstance(result, tuple) else None
    if info:
        print(f"  ok={info.get('ok')}, ecc={info.get('ecc'):.2f}, "
              f"shift={info.get('shift')}, contrast={info.get('contrast'):.2f}")

    # --- orientation + FEN ---
    name, H, score = pick_orientation(fine, pieces)
    print(f"Orientation: {name}  (score={score})")

    keep = dedupe_and_map(pieces, H)
    fen = fen_from_squares(keep)
    print(f"\nFEN: {fen}")
    try:
        print(chess.Board(fen))
    except Exception as e:
        print(f"invalid FEN: {e}")

    # ======================================================================
    # DRAW
    # ======================================================================
    out = img.copy()

    # Corner quad (green) + corner labels
    quad = np.asarray(fine, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(out, [quad], True, (0, 255, 0), 6)
    for i, (x, y) in enumerate(fine):
        cv2.circle(out, (int(x), int(y)), 15, (0, 255, 0), -1)
        cv2.putText(out, str(i), (int(x) + 18, int(y) - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

    # Square labels — inverse-homography each grid center to pixel space
    Hinv = np.linalg.inv(H)
    for row in range(8):
        for col in range(8):
            bx = col * S + S / 2
            by = row * S + S / 2
            pt = np.array([[[bx, by]]], dtype=np.float32)
            px, py = cv2.perspectiveTransform(pt, Hinv)[0][0]
            if 0 <= px < W_img and 0 <= py < H_img:
                label = f"{'abcdefgh'[col]}{8 - row}"
                cv2.putText(out, label, (int(px) - 22, int(py) + 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)

    # Piece boxes with class@square
    for sq, p in keep.items():
        x1, y1, x2, y2 = p["bbox"]
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 4)
        cv2.putText(out, f"{p['class']}@{sq}", (x1, y1 - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)

    # Save
    out_path = str(Path(img_path).with_name(Path(img_path).stem + "_debug_color.jpg"))
    cv2.imwrite(out_path, out)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()