"""
Reusable chess pipeline.

Public API:
    load_models()                          -> (piece_model, corner_model)
    detect_fen(img_path, pm=None, cm=None) -> dict with keys
                                              'fen', 'H', 'fine', 'source'
    detect_fen_locked(img_path, H, pm)     -> fen
    find_move(fen_before, fen_after)       -> [uci moves]
    pgn_from_moves(start_fen, moves)       -> chess.pgn.Game
"""
from pathlib import Path
import sys
import numpy as np
import cv2
from huggingface_hub import hf_hub_download
from ultralytics import YOLO
import chess
import chess.pgn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refine_any_color import refine_color

def _find_corner_weights():
    """Newest runs/corners*/weights/last_recal.pt (train.py writes last_recal.pt; see recalibrate_bn)."""
    runs = Path(__file__).resolve().parent / "runs"
    found = sorted(runs.glob("corners*/weights/last_recal.pt"), key=lambda f: f.stat().st_mtime)
    if not found:
        raise FileNotFoundError(f"no corners*/weights/last_recal.pt under {runs}; run train.py first")
    return str(found[-1])


CORNER_WEIGHTS = _find_corner_weights()
PIECE_MODEL_HF = "KanisornPutta/chess-model-yolov8m"
PIECE_MODEL_FILE = "chess-model-yolov8m.pt"

FEN_MAP = {
    "white-pawn": "P", "white-knight": "N", "white-bishop": "B",
    "white-rook": "R", "white-queen": "Q", "white-king": "K",
    "black-pawn": "p", "black-knight": "n", "black-bishop": "b",
    "black-rook": "r", "black-queen": "q", "black-king": "k",
}

S = 100
DST = np.array([[0, 0], [8*S, 0], [8*S, 8*S], [0, 8*S]], dtype=np.float32)

CANDIDATES = [
    ("rot 0",    (0, 1, 2, 3)),
    ("rot 90",   (1, 2, 3, 0)),
    ("rot 180",  (2, 3, 0, 1)),
    ("rot 270",  (3, 0, 1, 2)),
    ("flip 0",   (0, 3, 2, 1)),
    ("flip 90",  (3, 2, 1, 0)),
    ("flip 180", (2, 1, 0, 3)),
    ("flip 270", (1, 0, 3, 2)),
]


# =====================================================================
# Models
# =====================================================================
def load_models():
    piece = YOLO(hf_hub_download(PIECE_MODEL_HF, PIECE_MODEL_FILE))
    corner = YOLO(CORNER_WEIGHTS)
    return piece, corner


# =====================================================================
# Piece detection
# =====================================================================
def detect_pieces(img_path, piece_model, conf=0.4):
    r = piece_model(str(img_path), conf=conf, verbose=False)[0]
    out = []
    for b in r.boxes:
        x1, y1, x2, y2 = [int(v) for v in b.xyxy[0]]
        out.append({
            "class": piece_model.names[int(b.cls)],
            "conf": float(b.conf),
            "bbox": (x1, y1, x2, y2),
            "base_pt": ((x1 + x2) / 2, y2),
        })
    return out


# =====================================================================
# Corner detection
# =====================================================================
def detect_corners_yolo(img_path, corner_model, conf=0.3):
    r = corner_model(str(img_path), conf=conf, max_det=1, verbose=False)[0]
    if len(r.boxes) == 0 or r.keypoints is None:
        return None
    return r.keypoints.xy[0].cpu().numpy()


def detect_corners_piece_hull(img, pieces, expand=1.5):
    """Rotated rect around piece base-points, expanded by `expand * median_width`."""
    if len(pieces) < 6:
        return None
    pts = np.array([p["base_pt"] for p in pieces], dtype=np.float32)
    widths = np.array([p["bbox"][2] - p["bbox"][0] for p in pieces], dtype=float)
    sq = float(np.median(widths))
    (cx, cy), (w, h), angle = cv2.minAreaRect(pts)
    w_exp = w + expand * sq
    h_exp = h + expand * sq
    corners = cv2.boxPoints(((cx, cy), (w_exp, h_exp), angle)).astype(float)
    return _order_corners(corners)


def corners_contain_pieces(corners, pieces, min_inside_ratio=0.9):
    if corners is None or len(pieces) == 0:
        return False
    poly = np.asarray(corners, dtype=np.int32).reshape(-1, 1, 2)
    inside = 0
    for p in pieces:
        if cv2.pointPolygonTest(poly, p["base_pt"], False) >= 0:
            inside += 1
    return inside >= min_inside_ratio * len(pieces)


def _order_corners(corners):
    """Leftmost first, then clockwise."""
    corners = np.asarray(corners, dtype=float)
    li = int(np.argmin(corners[:, 0]))
    corners = np.roll(corners, -li, axis=0)
    cross = ((corners[1, 0] - corners[0, 0]) * (corners[2, 1] - corners[0, 1])
             - (corners[1, 1] - corners[0, 1]) * (corners[2, 0] - corners[0, 0]))
    if cross < 0:
        corners = np.array([corners[0], corners[3], corners[2], corners[1]])
    return corners


# =====================================================================
# Homography
# =====================================================================
def make_homography(ordered_corners):
    src = np.array(ordered_corners, dtype=np.float32)
    H, _ = cv2.findHomography(src, DST)
    return H


def pixel_to_square(H, px, py):
    pt = np.array([[[px, py]]], dtype=np.float32)
    bx, by = cv2.perspectiveTransform(pt, H)[0][0]
    col, row = int(bx // S), int(by // S)
    if 0 <= col <= 7 and 0 <= row <= 7:
        return f"{'abcdefgh'[col]}{8 - row}"
    return None


# =====================================================================
# Orientation
# =====================================================================
def _score_orientation(fine_corners, pieces, order):
    H = make_homography([fine_corners[i] for i in order])
    w_low = b_high = off = 0
    for p in pieces:
        sq = pixel_to_square(H, *p["base_pt"])
        if sq is None:
            off += 1
            continue
        rank = int(sq[1])
        if p["class"].startswith("white-"):
            if rank <= 4:
                w_low += 1
        else:
            if rank >= 5:
                b_high += 1
    return w_low + b_high - 3 * off, H


def pick_orientation(fine_corners, pieces):
    best = None
    for name, order in CANDIDATES:
        s, H = _score_orientation(fine_corners, pieces, order)
        if best is None or s > best[2]:
            best = (name, H, s)
    return best


# =====================================================================
# FEN
# =====================================================================
def dedupe_and_map(pieces, H):
    keep = {}
    for p in pieces:
        sq = pixel_to_square(H, *p["base_pt"])
        if sq is None:
            continue
        if sq in keep and keep[sq]["conf"] >= p["conf"]:
            continue
        keep[sq] = p
    return keep


def fen_from_squares(keep, turn="w"):
    grid = [["" for _ in range(8)] for _ in range(8)]
    for sq, p in keep.items():
        col = "abcdefgh".index(sq[0])
        row = 8 - int(sq[1])
        grid[row][col] = FEN_MAP[p["class"]]
    rows = []
    for row in grid:
        empty, s = 0, ""
        for c in row:
            if c == "":
                empty += 1
            else:
                if empty:
                    s += str(empty)
                    empty = 0
                s += c
        if empty:
            s += str(empty)
        rows.append(s)
    return "/".join(rows) + f" {turn} - - 0 1"


# =====================================================================
# Top-level
# =====================================================================
def _try_corners(img, rough, source, verbose):
    if rough is None:
        return None, None
    result = refine_color(img, rough)
    fine = result[0] if isinstance(result, tuple) else result
    info = result[1] if isinstance(result, tuple) else None
    if verbose and info:
        print(f"  {source:5s}: ok={info.get('ok')}, "
              f"ecc={info.get('ecc'):.2f}, shift={info.get('shift')}, "
              f"contrast={info.get('contrast'):.2f}")
    return fine, info


def detect_fen(img_path, piece_model=None, corner_model=None, verbose=False):
    """
    Full pipeline. Returns dict:
        { 'fen': str|None, 'H': np.ndarray|None,
          'fine': np.ndarray|None, 'source': str|None }
    Tries YOLO and piece-hull, keeps whichever refined with higher ECC.
    """
    empty = {"fen": None, "H": None, "fine": None, "source": None}

    if piece_model is None or corner_model is None:
        piece_model, corner_model = load_models()

    img = cv2.imread(str(img_path))
    if img is None:
        return empty

    pieces = detect_pieces(img_path, piece_model)
    if verbose:
        print(f"  pieces: {len(pieces)}")
    if not pieces:
        return empty

    candidates = []

    # YOLO
    rough_yolo = detect_corners_yolo(img_path, corner_model)
    if rough_yolo is not None and corners_contain_pieces(rough_yolo, pieces):
        fine_y, info_y = _try_corners(img, rough_yolo, "yolo", verbose)
        if fine_y is not None and info_y is not None:
            candidates.append(("yolo", fine_y, info_y))
    elif rough_yolo is not None and verbose:
        print("  yolo corners rejected (don't contain pieces)")

    # Hull
    rough_hull = detect_corners_piece_hull(img, pieces)
    if rough_hull is not None:
        fine_h, info_h = _try_corners(img, rough_hull, "hull", verbose)
        if fine_h is not None and info_h is not None:
            candidates.append(("hull", fine_h, info_h))

    if not candidates:
        if verbose:
            print("  all detectors failed")
        return empty

    candidates.sort(key=lambda t: t[2].get("ecc", 0.0), reverse=True)
    source, fine, info = candidates[0]
    if verbose:
        print(f"  picked: {source} (ecc={info.get('ecc', 0):.2f})")

    name, H, score = pick_orientation(fine, pieces)
    if verbose:
        print(f"  orientation: {name}, score={score}")

    keep = dedupe_and_map(pieces, H)
    if not keep:
        return empty

    return {
        "fen": fen_from_squares(keep),
        "H": H,
        "fine": fine,
        "source": source,
    }


def detect_fen_locked(img_path, H, piece_model=None):
    if piece_model is None:
        piece_model, _ = load_models()
    pieces = detect_pieces(img_path, piece_model)
    if not pieces:
        return None
    keep = dedupe_and_map(pieces, H)
    if not keep:
        return None
    return fen_from_squares(keep)


# =====================================================================
# Move disambiguation + PGN
# =====================================================================
def find_move(fen_before, fen_after):
    try:
        b = chess.Board(fen_before)
        a = chess.Board(fen_after)
    except Exception:
        return []
    target = a.board_fen()
    matches = []
    for move in b.legal_moves:
        t = b.copy()
        t.push(move)
        if t.board_fen() == target:
            matches.append(move.uci())
    return matche


def pgn_from_moves(start_fen, moves_uci):
    game = chess.pgn.Game()
    game.setup(chess.Board(start_fen))
    node = game
    for uci in moves_uci:
        node = node.add_variation(chess.Move.from_uci(uci))
    return game