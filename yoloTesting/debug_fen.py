"""
debug_fen.py — Full pipeline with verbose prints at every step.

Usage:
  python debug_fen.py <image_path>

Prints each intermediate result so you can see exactly where things go right
or wrong: piece detections, corner detections (image order), refinement,
all 8 orientation candidates with scores, final corner assignment, piece-to-square
mapping, deduplication, and FEN.
"""
import sys
from pathlib import Path
import numpy as np
import cv2
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

# Make yoloTesting/ importable so we can reuse refine_corners.refine()
sys.path.insert(0, str(Path(__file__).resolve().parent / "yoloTesting"))
from refine_corners import refine

CORNER_WEIGHTS = "yoloTesting/runs/corners/weights/last_recal.pt"
PIECE_MODEL_HF = "KanisornPutta/chess-model-yolov8m"
PIECE_MODEL_FILE = "chess-model-yolov8m.pt"

FEN_MAP = {
    "white-pawn": "P", "white-knight": "N", "white-bishop": "B",
    "white-rook": "R", "white-queen": "Q", "white-king": "K",
    "black-pawn": "p", "black-knight": "n", "black-bishop": "b",
    "black-rook": "r", "black-queen": "q", "black-king": "k",
}


def header(title):
    print()
    print("=" * 68)
    print(f"  {title}")
    print("=" * 68)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python debug_fen.py <image_path>")
    img_path = sys.argv[1]
    img = cv2.imread(img_path)
    if img is None:
        raise SystemExit(f"Could not read image: {img_path}")
    H_img, W_img = img.shape[:2]

    print(f"Image: {img_path}")
    print(f"Dimensions: {W_img} x {H_img} pixels")

    # ==================================================================
    # STEP 1: Piece detection
    # ==================================================================
    header("STEP 1 — Piece detection (HuggingFace YOLOv8m)")
    print("Loading piece model...")
    piece_model = YOLO(hf_hub_download(PIECE_MODEL_HF, PIECE_MODEL_FILE))
    res = piece_model(img_path, conf=0.4)[0]

    pieces = []
    for b in res.boxes:
        cls = piece_model.names[int(b.cls)]
        x1, y1, x2, y2 = [int(v) for v in b.xyxy[0]]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        pieces.append({
            "class": cls,
            "conf": float(b.conf),
            "bbox": (x1, y1, x2, y2),
            "center": (cx, cy),
            "square_pt": (cx, y2),
        })

    print(f"\nFound {len(pieces)} raw piece detections:")
    for i, p in enumerate(pieces):
        print(f"  [{i:2}] {p['class']:<14} conf={p['conf']:.2f}  "
              f"center=({p['center'][0]:6.0f}, {p['center'][1]:6.0f})  "
              f"bbox={p['bbox']}")

    # ==================================================================
    # STEP 2: Corner detection (rough)
    # ==================================================================
    header("STEP 2 — Corner detection (YOLO11s-pose, last_recal.pt)")
    print("Loading corner model...")
    corner_model = YOLO(CORNER_WEIGHTS)
    cres = corner_model(img_path, conf=0.3, max_det=1)[0]

    if len(cres.boxes) == 0 or cres.keypoints is None:
        raise SystemExit("  ERROR: no board detected.")

    rough = cres.keypoints.xy[0].cpu().numpy()
    kconf = cres.keypoints.conf[0].cpu().numpy()

    print(f"\nModel found {len(rough)} corners (IMAGE order, not chess order):")
    print("  Order was set during Roboflow annotation:")
    print("    index 0 = leftmost corner in the image")
    print("    index 1 = next corner clockwise")
    print("    index 2 = next corner clockwise")
    print("    index 3 = next corner clockwise")
    print()
    for i, (x, y) in enumerate(rough):
        print(f"  corner[{i}]  = ({x:7.1f}, {y:7.1f})   keypoint_conf={kconf[i]:.2f}")

    # ==================================================================
    # STEP 3: Corner refinement
    # ==================================================================
    header("STEP 3 — Corner refinement (ECC snap to checkerboard grid)")
    print("Running refine_corners.refine()...")
    print("This warps the board to a flat canvas and aligns the ideal")
    print("checkerboard template to the green squares, then maps back.")
    result = refine(img, rough)
    # refine() returns (refined_corners, check_dict) or just corners depending on version
    if isinstance(result, tuple):
        fine, check = result
        print(f"refine() info: {check}")
    else:
        fine = result

    print(f"\nRefined corners (order preserved from Step 2):")
    for i, (x, y) in enumerate(fine):
        dx = x - rough[i][0]
        dy = y - rough[i][1]
        print(f"  corner[{i}]  = ({x:7.1f}, {y:7.1f})   "
              f"delta from rough = ({dx:+6.1f}, {dy:+6.1f})")

    # ==================================================================
    # STEP 4: Orientation search — try all 8 assignments
    # ==================================================================
    header("STEP 4 — Orientation search (8 candidate assignments)")
    print("We don't yet know which detected corner is a8/h8/h1/a1.")
    print("Try all 4 rotations x 2 reflections = 8 assignments.")
    print("Score each by counting pieces on their home side of the board.")
    print()

    S = 100  # arbitrary units per square in target space
    # Target: standard board with (a8)=(0,0), (h8)=(8,0), (h1)=(8,8), (a1)=(0,8)
    dst = np.array([[0, 0], [8*S, 0], [8*S, 8*S], [0, 8*S]], dtype=np.float32)

    def make_H(corners_ordered):
        src = np.array(corners_ordered, dtype=np.float32)
        H, _ = cv2.findHomography(src, dst)
        return H

    def px_to_sq(H, px, py):
        pt = np.array([[[px, py]]], dtype=np.float32)
        bx, by = cv2.perspectiveTransform(pt, H)[0][0]
        col = int(bx // S)
        row = int(by // S)
        if 0 <= col <= 7 and 0 <= row <= 7:
            return f"{'abcdefgh'[col]}{8 - row}"
        return None  # off-board

    def score_orientation(corners_ordered):
        H = make_H(corners_ordered)
        white_on_low = 0   # white pieces on ranks 1-4 (white's home)
        black_on_high = 0  # black pieces on ranks 5-8 (black's home)
        off_board = 0
        for p in pieces:
            sq = px_to_sq(H, *p["square_pt"])
            if sq is None:
                off_board += 1
                continue
            rank = int(sq[1])
            if p["class"].startswith("white-"):
                if rank <= 4: white_on_low += 1
            else:
                if rank >= 5: black_on_high += 1
        score = white_on_low + black_on_high - 3 * off_board
        return score, white_on_low, black_on_high, off_board

    # 4 rotations (clockwise starting at each index), then 4 with reversed orientation
    candidates = [
        ("rot 0°           (0,1,2,3)", (0, 1, 2, 3)),
        ("rot 90°          (1,2,3,0)", (1, 2, 3, 0)),
        ("rot 180°         (2,3,0,1)", (2, 3, 0, 1)),
        ("rot 270°         (3,0,1,2)", (3, 0, 1, 2)),
        ("flip + rot 0°    (0,3,2,1)", (0, 3, 2, 1)),
        ("flip + rot 90°   (3,2,1,0)", (3, 2, 1, 0)),
        ("flip + rot 180°  (2,1,0,3)", (2, 1, 0, 3)),
        ("flip + rot 270°  (1,0,3,2)", (1, 0, 3, 2)),
    ]

    print(f"{'candidate':<26} {'score':>6} {'white↓':>8} {'black↑':>8} {'off':>5}")
    print("-" * 60)

    results = []
    for name, order in candidates:
        c_ordered = [fine[i] for i in order]
        score, w, b, off = score_orientation(c_ordered)
        results.append((score, name, order, c_ordered, w, b, off))
        print(f"{name:<26} {score:>6} {w:>8} {b:>8} {off:>5}")

    # Pick best
    results.sort(key=lambda r: -r[0])
    best = results[0]
    score, name, order, corners_best, w, b, off = best
    second = results[1] if len(results) > 1 else None

    print()
    print(f"WINNER: {name}  (score={score}, white↓={w}, black↑={b}, off-board={off})")
    if second:
        print(f"  margin over runner-up: {score - second[0]} points")
        print(f"  (runner-up was '{second[1]}' with score {second[0]})")
    if score - (second[0] if second else 0) < 3:
        print("  WARNING: margin is small — orientation is ambiguous on this image")

    # ==================================================================
    # STEP 5: Final corner assignment
    # ==================================================================
    header("STEP 5 — Final corner assignment")
    print("The winning orientation assigns the 4 detected corners to:")
    print()
    for label, (x, y) in zip(["a8", "h8", "h1", "a1"], corners_best):
        print(f"  {label}: pixel ({x:7.1f}, {y:7.1f})")

    # ==================================================================
    # STEP 6: Piece -> square mapping
    # ==================================================================
    header("STEP 6 — Map every piece to a square")
    H = make_H(corners_best)
    print(f"Homography computed from the 4 winning corners to the 8x8 grid.")
    print()
    print(f"{'piece':<14} {'conf':>5}   {'center':<16} -> square")
    print("-" * 55)
    for p in pieces:
        sq = px_to_sq(H, *p["square_pt"])
        sq_str = sq if sq else "OFF-BOARD"
        print(f"{p['class']:<14} {p['conf']:>5.2f}   "
              f"({p['center'][0]:6.0f},{p['center'][1]:6.0f}) -> {sq_str}")

    # ==================================================================
    # STEP 7: Deduplicate — one piece per square, highest confidence wins
    # ==================================================================
    header("STEP 7 — Deduplicate (highest confidence per square)")
    keep = {}
    dropped = 0
    for p in pieces:
        sq = px_to_sq(H, *p["square_pt"])
        if sq is None:
            continue  # already counted as off-board
        if sq in keep:
            if keep[sq]["conf"] >= p["conf"]:
                print(f"  drop {p['class']}@{sq} (conf {p['conf']:.2f}) — "
                      f"kept {keep[sq]['class']} (conf {keep[sq]['conf']:.2f})")
                dropped += 1
                continue
            else:
                print(f"  replace {keep[sq]['class']}@{sq} "
                      f"(conf {keep[sq]['conf']:.2f}) with "
                      f"{p['class']} (conf {p['conf']:.2f})")
                dropped += 1
        keep[sq] = p

    print(f"\nDropped {dropped} duplicate detections.")
    print(f"Kept {len(keep)} unique pieces:")
    for sq in sorted(keep.keys()):
        p = keep[sq]
        print(f"  {sq}: {p['class']} (conf {p['conf']:.2f})")

    # ==================================================================
    # STEP 8: Build FEN
    # ==================================================================
    header("STEP 8 — Build FEN string")
    grid = [["" for _ in range(8)] for _ in range(8)]
    for sq, p in keep.items():
        col = "abcdefgh".index(sq[0])
        row = 8 - int(sq[1])
        grid[row][col] = FEN_MAP[p["class"]]

    rows = []
    for row in grid:
        empty = 0
        s = ""
        for cell in row:
            if cell == "":
                empty += 1
            else:
                if empty:
                    s += str(empty)
                    empty = 0
                s += cell
        if empty:
            s += str(empty)
        rows.append(s)

    fen = "/".join(rows) + " w - - 0 1"
    print(f"FEN: {fen}")

    # ==================================================================
    # STEP 9: Sanity check + visual
    # ==================================================================
    header("STEP 9 — Sanity check + debug image")
    try:
        import chess
        b = chess.Board(fen)
        print("python-chess: FEN is legal.")
        print()
        print(b)
    except ImportError:
        print("python-chess not installed; skipping legality check.")
    except Exception as e:
        print(f"python-chess: FEN is INVALID — {e}")

    # Draw debug image
    out = img.copy()
    cv2.polylines(out, [np.array(corners_best).astype(np.int32).reshape(-1, 1, 2)],
                  True, (0, 255, 0), 4)
    for label, (x, y) in zip(["a8", "h8", "h1", "a1"], corners_best):
        cv2.circle(out, (int(x), int(y)), 15, (0, 255, 0), -1)
        cv2.putText(out, label, (int(x) + 20, int(y) - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)

    Hinv = np.linalg.inv(H)
    for row in range(8):
        for col in range(8):
            bx, by = col * S + S / 2, row * S + S / 2
            pt = np.array([[[bx, by]]], dtype=np.float32)
            px, py = cv2.perspectiveTransform(pt, Hinv)[0][0]
            if 0 <= px < W_img and 0 <= py < H_img:
                cv2.putText(out, f"{'abcdefgh'[col]}{8 - row}",
                            (int(px) - 25, int(py) + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)

    for sq, p in keep.items():
        x1, y1, x2, y2 = p["bbox"]
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 3)
        cv2.putText(out, f"{p['class']}@{sq}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    out_path = Path(img_path).with_name(Path(img_path).stem + "_debug.jpg")
    cv2.imwrite(str(out_path), out)
    print(f"\nSaved debug image: {out_path}")


if __name__ == "__main__":
    main()