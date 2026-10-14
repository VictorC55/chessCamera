"""
Batch test the color-agnostic pipeline over a folder.

Usage:
    python yoloTesting/batch_test.py pictures/differentthengreen
"""
import sys
from pathlib import Path
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chess_pipeline import (
    load_models, detect_fen, detect_pieces, dedupe_and_map, S,
)

import chess


def draw_debug(img, out_path, H, fine, keep):
    out = img.copy()
    H_img, W_img = img.shape[:2]

    if fine is not None:
        cv2.polylines(out, [np.asarray(fine, dtype=np.int32).reshape(-1, 1, 2)],
                      True, (0, 255, 0), 6)
        for i, (x, y) in enumerate(fine):
            cv2.circle(out, (int(x), int(y)), 15, (0, 255, 0), -1)
            cv2.putText(out, str(i), (int(x) + 18, int(y) - 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 0), 3)

    if H is not None:
        Hinv = np.linalg.inv(H)
        for row in range(8):
            for col in range(8):
                bx, by = col * S + S / 2, row * S + S / 2
                pt = np.array([[[bx, by]]], dtype=np.float32)
                px, py = cv2.perspectiveTransform(pt, Hinv)[0][0]
                if 0 <= px < W_img and 0 <= py < H_img:
                    cv2.putText(out, f"{'abcdefgh'[col]}{8 - row}",
                                (int(px) - 22, int(py) + 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)

    if keep:
        for sq, p in keep.items():
            x1, y1, x2, y2 = p["bbox"]
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 4)
            cv2.putText(out, f"{p['class']}@{sq}", (x1, y1 - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)

    cv2.imwrite(str(out_path), out)


def process(img_path, pm, cm):
    img = cv2.imread(str(img_path))
    if img is None:
        return None, "cannot read"

    result = detect_fen(img_path, pm, cm, verbose=True)
    fen = result["fen"]
    H = result["H"]
    fine = result["fine"]

    keep = None
    if H is not None:
        pieces = detect_pieces(img_path, pm)
        keep = dedupe_and_map(pieces, H)

    out_path = img_path.with_name(img_path.stem + "_debug.jpg")
    draw_debug(img, out_path, H, fine, keep)

    return result, result.get("source")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python batch_test.py <folder>")
    folder = Path(sys.argv[1])
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")

    files = sorted([f for f in folder.iterdir()
                    if f.suffix.lower() in (".jpg", ".jpeg", ".png")
                    and "_debug" not in f.stem])
    if not files:
        raise SystemExit(f"No images in {folder}")

    print(f"Found {len(files)} images\n")
    print("Loading models...")
    pm, cm = load_models()
    print()

    passed = 0
    for f in files:
        print(f"--- {f.name} ---")
        result, source = process(f, pm, cm)
        if result is None or result["fen"] is None:
            print("    !! FAILED\n")
            continue
        fen = result["fen"]
        print(f"    FEN: {fen}")
        try:
            valid = chess.Board(fen).is_valid()
        except Exception:
            valid = False
        if valid:
            passed += 1
        print()

    print(f"{'='*60}")
    print(f"Valid FENs: {passed}/{len(files)}")
    print(f"Debug images saved as *_debug.jpg next to each input.")


if __name__ == "__main__":
    main()