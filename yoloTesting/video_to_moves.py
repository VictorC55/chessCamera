"""
Video -> FEN timeline -> list of moves.

Samples one frame every `--interval` seconds and runs the image pipeline on
each one, with two changes that matter for video:

  * Board tracking. The camera may move, so corners are re-fitted on every
    frame, but the fit starts from the previous frame's refined quad instead
    of the rough YOLO/piece-hull guess. From a near-correct start the
    checkerboard fit converges in about a second and scores well; from the
    rough guess it takes ~9s and often lands on the wrong grid. The first
    good fit seeds the tracker; frames before it are re-done backwards.
    A checkerboard also fits itself shifted by one square, so a tracked
    grid can drift a rank; the pieces anchor it: if a one-square shift of
    the quad contains clearly more piece base points, the quad is moved
    there and re-polished. A fit that leaves >20% of pieces outside is
    not trusted.
  * Debouncing on occupancy, voting on type. The piece detector flips labels
    (pawn/bishop/king) between frames, so stability is judged on which
    squares hold which colour, and the piece type on each square is the
    majority vote over the frames of that stable run.

Each change between stable positions is then explained as the shortest
legal move sequence (up to 3 plies, in case samples were missed) whose
result best matches what was seen. Matching is on occupancy and colour;
the piece detector's type labels are only a weak tiebreak, because once
the start position is known the rules determine the types and the camera
only has to tell occupied from empty. (The detector mislabels tall pieces
constantly; occupancy it gets right.)

Per-frame results are cached to <video>_fens.json; --replay re-runs only
the move logic from that cache, which is instant.

Start position: 'auto' takes the first stable detection. If that is within a
few squares of the standard start, the standard start's piece types are used
(the detector's labels are unreliable) and, if the first change cannot be
explained from the merged board, the full standard start is tried instead.
Changes no legal sequence explains are skipped once; two in a row force a
resync to the observed position (keeping known piece types where possible).

Known limits on the sample video: a piece the detector never sees on its
square (the h2 pawn at the frame edge, a pawn hidden behind the king) can
produce a phantom move or block one. Read the video from local disk: files on
Google Drive stream from the cloud and OpenCV times out mid-video.

Usage:
    python yoloTesting/video_to_moves.py videos/clip.mp4
    python yoloTesting/video_to_moves.py videos/clip.mp4 --interval 0.5 --save-frames
    python yoloTesting/video_to_moves.py videos/clip.mp4 --start-fen startpos

Options:
    --interval S      seconds between sampled frames (default 1.0; 0.5 tracks
                      a moving camera better at twice the cost)
    --stable N        a position must be seen on N consecutive samples before
                      it counts (default 2). Filters hands and mid-move frames.
    --jitter J        squares of occupancy change tolerated between consecutive
                      samples of one position (default 1: a single spurious or
                      missed detection does not break the run; a move does).
    --tolerance T     occupancy error allowed for a move to be accepted
                      (default 1.5; a missed piece costs 0.5, an invented
                      piece 1.0, squares outside the frame cost nothing)
    --start-fen F     'auto' (default: first stable detection, snapped to the
                      standard start if its occupancy matches), 'startpos',
                      or a FEN.
    --replay          skip detection; load <video>_fens.json from a previous run
    --save-frames     write annotated frames to <video>_frames/ so you can
                      see what the pipeline saw at each sample.
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refine_corners  # noqa: E402
from refine_any_color import refine_color  # noqa: E402
from chess_pipeline import (  # noqa: E402
    load_models, detect_corners_piece_hull, corners_contain_pieces,
    pick_orientation, dedupe_and_map, fen_from_squares, make_homography, S, DST,
)

SEED_EVERY = 3      # until the tracker is seeded, run the slow from-scratch search on every Nth frame
GOOD_ECC = 0.65     # a fit this strong updates the tracker
MIN_ECC = 0.62      # below this the frame's FEN is not trusted
MIN_INSIDE = 0.8    # fraction of piece base points that must fall inside the quad
TRACK_FAILS_BEFORE_RESEED = 2


# =====================================================================
# Per-frame detection
# =====================================================================
def detect_pieces_frame(frame, piece_model, conf=0.4):
    r = piece_model(frame, conf=conf, verbose=False)[0]
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


def detect_corners_frame(frame, corner_model, conf=0.3):
    r = corner_model(frame, conf=conf, max_det=1, verbose=False)[0]
    if len(r.boxes) == 0 or r.keypoints is None:
        return None
    return r.keypoints.xy[0].cpu().numpy()


def refine_quad(frame, rough, retries):
    """Checkerboard-fit `rough`. retries=False (tracking) skips the slow rotated restarts."""
    old = refine_corners.WEAK_ECC
    refine_corners.WEAK_ECC = old if retries else 0.0
    try:
        res = refine_color(frame, rough)
    finally:
        refine_corners.WEAK_ECC = old
    fine, info = (res if isinstance(res, tuple) else (res, {}))
    return fine, float((info or {}).get("ecc", 0.0))


# ---- piece anchoring against one-square drift ----
def pieces_inside(quad, pieces):
    poly = np.asarray(quad, dtype=np.int32).reshape(-1, 1, 2)
    return sum(1 for p in pieces if cv2.pointPolygonTest(poly, p["base_pt"], False) >= 0)


def shift_quad(quad, dx, dy):
    """Move the quad by (dx, dy) squares along its own axes."""
    Hinv = np.linalg.inv(make_homography(quad))
    dst = (DST + np.float32([dx * S, dy * S])).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(dst, Hinv).reshape(4, 2)


def anchor_to_pieces(frame, quad, ecc, pieces):
    """If a one-square shift of `quad` holds clearly more pieces, move there and re-polish.
    Returns (quad, ecc, inside_fraction, shift)."""
    n0 = pieces_inside(quad, pieces)
    best = (n0, 0, 0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx, dy) != (0, 0):
                n = pieces_inside(shift_quad(quad, dx, dy), pieces)
                if n > best[0]:
                    best = (n, dx, dy)
    n, dx, dy = best
    if (dx, dy) == (0, 0) or n - n0 < 2:
        return quad, ecc, n0 / max(1, len(pieces)), (0, 0)
    moved = shift_quad(quad, dx, dy)
    fine, ecc2 = refine_quad(frame, moved, retries=False)
    n2 = pieces_inside(fine, pieces)
    if n2 >= n0:
        return fine, ecc2, n2 / max(1, len(pieces)), (dx, dy)
    return quad, ecc, n0 / max(1, len(pieces)), (0, 0)


def search_quad(frame, pieces, corner_model):
    """Full search from scratch: YOLO corners (if they contain the pieces) and piece hull."""
    cands = []
    rough = detect_corners_frame(frame, corner_model)
    if rough is not None and corners_contain_pieces(rough, pieces):
        fine, ecc = refine_quad(frame, rough, retries=True)
        cands.append((ecc, fine, "yolo"))
    rough = detect_corners_piece_hull(frame, pieces)
    if rough is not None:
        fine, ecc = refine_quad(frame, rough, retries=True)
        cands.append((ecc, fine, "hull"))
    if not cands:
        return None, 0.0, None
    ecc, fine, src = max(cands, key=lambda c: c[0])
    return fine, ecc, src


def fen_for_quad(fine, pieces):
    _, H, _ = pick_orientation(fine, pieces)
    keep = dedupe_and_map(pieces, H)
    if not keep:
        return None, H, keep
    return fen_from_squares(keep).split()[0], H, keep


def visible_squares(H, frame_shape):
    """Square names whose centre projects inside the frame."""
    h, w = frame_shape[:2]
    Hinv = np.linalg.inv(H)
    out = []
    for row in range(8):
        for col in range(8):
            pt = np.array([[[col * S + S / 2, row * S + S / 2]]], dtype=np.float32)
            px, py = cv2.perspectiveTransform(pt, Hinv)[0][0]
            if 0 <= px < w and 0 <= py < h:
                out.append(f"{'abcdefgh'[col]}{8 - row}")
    return out


def draw_debug(frame, s):
    out = frame.copy()
    h, w = out.shape[:2]
    if s.get("fine") is not None:
        color = (0, 255, 0) if s["trusted"] else (0, 0, 255)
        quad = np.asarray(s["fine"], dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [quad], True, color, 3)
    if s.get("H") is not None:
        Hinv = np.linalg.inv(s["H"])
        for row in range(8):
            for col in range(8):
                pt = np.array([[[col * S + S / 2, row * S + S / 2]]], dtype=np.float32)
                px, py = cv2.perspectiveTransform(pt, Hinv)[0][0]
                if 0 <= px < w and 0 <= py < h:
                    cv2.putText(out, f"{'abcdefgh'[col]}{8 - row}", (int(px) - 12, int(py) + 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        for sq, p in (s.get("keep") or {}).items():
            x1, y1, x2, y2 = p["bbox"]
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(out, f"{p['class'].split('-')[1][0]}@{sq}", (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    label = (f"t={s['t']:.1f}s {s['source'] or '-'} ecc={s['ecc']:.2f} inside={s.get('inside', 0):.2f} "
             f"{'OK' if s['trusted'] else 'untrusted'}  {s['board_fen'] or ''}")
    cv2.putText(out, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    return out


# =====================================================================
# Debounce: group by occupancy, vote on type
# =====================================================================
def occupancy(board_fen):
    b = chess.Board(None)
    b.set_board_fen(board_fen)
    return {sq: b.piece_at(sq).color for sq in chess.SQUARES if b.piece_at(sq)}


def occupancy_diff(a, b):
    return sum(1 for sq in chess.SQUARES if a.get(sq) != b.get(sq))


def vote_board_fen(board_fens):
    """Per-square majority over a run of frames: first whether the square is occupied
    (empty counts as a vote), then which piece symbol."""
    n = len(board_fens)
    votes = {sq: Counter() for sq in chess.SQUARES}
    for bf in board_fens:
        b = chess.Board(None)
        b.set_board_fen(bf)
        for sq, p in b.piece_map().items():
            votes[sq][p.symbol()] += 1
    out = chess.Board(None)
    for sq, c in votes.items():
        if sum(c.values()) * 2 > n:  # occupied in a majority of frames
            out.set_piece_at(sq, chess.Piece.from_symbol(c.most_common(1)[0][0]))
    return out.board_fen()


def stable_positions(samples, min_run, max_jitter=1):
    """[(t_first_seen, board_fen, visible_squares|None)] for runs of >= min_run trusted frames whose occupancy
    (which squares hold which colour) differs by <= max_jitter squares frame to frame."""
    out = []
    run = []  # (t, board_fen, occupancy)

    def flush():
        if len(run) >= min_run:
            bf = vote_board_fen([r[1] for r in run])
            vis = None
            if all(r[3] is not None for r in run):
                vis = set.intersection(*[set(chess.parse_square(q) for q in r[3]) for r in run])
            if not out or out[-1][1] != bf:
                out.append((run[0][0], bf, vis))

    for s in samples:
        bf = s["board_fen"] if s["trusted"] else None
        if bf is None:
            flush(); run = []
            continue
        occ = occupancy(bf)
        if run and occupancy_diff(occ, run[-1][2]) > max_jitter:
            flush(); run = []
        run.append((s["t"], bf, occ, s.get("visible")))
    flush()
    return out


# =====================================================================
# Move explanation
# =====================================================================
MOVE_MARGIN = 0.5   # a move must beat the "no move, just noise" explanation by this much
TYPE_WEIGHT = 0.1   # a wrong piece type on a correctly occupied square
MISS_WEIGHT = 0.5   # a piece the detector did not see (dropped detections are common;
                    # invented pieces are rarer and cost 1.0)


def board_distance(a, b, visible=None):
    """Compare tracked board `a` with observed board `b`.
    Returns (occupancy mismatch score, type-only mismatch count).
    Squares not in `visible` (when given) are ignored: they were outside the frame."""
    occ = 0.0
    typ = 0
    for sq in chess.SQUARES:
        if visible is not None and sq not in visible:
            continue
        pa, pb = a.piece_at(sq), b.piece_at(sq)
        if pa == pb:
            continue
        if pa is not None and pb is not None and pa.color == pb.color:
            typ += 1
        elif pb is None:
            occ += MISS_WEIGHT
        else:
            occ += 1.0
    return occ, typ


def distance_score(a, b, visible=None):
    occ, typ = board_distance(a, b, visible)
    return occ + TYPE_WEIGHT * typ


def square_diff(a, b):
    sym = lambda p: p.symbol() if p else "."
    return [f"{chess.square_name(sq)}:{sym(a.piece_at(sq))}->{sym(b.piece_at(sq))}"
            for sq in chess.SQUARES if a.piece_at(sq) != b.piece_at(sq)]


def _occ_diff_squares(a, b, visible=None):
    out = set()
    for sq in chess.SQUARES:
        if visible is not None and sq not in visible:
            continue
        pa, pb = a.piece_at(sq), b.piece_at(sq)
        if (pa is None) != (pb is None) or (pa is not None and pa.color != pb.color):
            out.add(sq)
    return out


def explain_change(board, observed, tolerance, turn_unknown, max_plies=3, visible=None):
    """Shortest legal sequence from `board` whose result matches `observed` on occupancy
    within `tolerance`. Returns (moves|None, score, turn_used).

    Iterative deepening: all 1-ply sequences are tried before any 2-ply one, so a
    longer sequence only wins if no shorter one is within tolerance. Pruning: every
    move must touch a square whose occupancy still differs from the observation."""
    turns = [chess.WHITE, chess.BLACK] if turn_unknown else [board.turn]

    def dfs(b, moves, depth, limit, turn, best):
        diff = _occ_diff_squares(b, observed, visible)
        if not diff:
            return
        for m in b.legal_moves:
            if m.from_square not in diff and m.to_square not in diff:
                continue
            b.push(m)
            seq = moves + [m]
            if depth == limit:
                sc = distance_score(b, observed, visible)
                if sc < best["score"]:
                    best.update(moves=seq, score=sc, turn=turn)
            else:
                dfs(b, seq, depth + 1, limit, turn, best)
            b.pop()

    for limit in range(1, max_plies + 1):
        best = {"moves": None, "score": float("inf"), "turn": board.turn}
        for turn in turns:
            b0 = board.copy()
            b0.turn = turn
            dfs(b0, [], 1, limit, turn, best)
        if best["moves"] is None:
            continue
        final = board.copy()
        final.turn = best["turn"]
        for m in best["moves"]:
            final.push(m)
        occ, _ = board_distance(final, observed, visible)
        if occ <= tolerance:
            return best["moves"], best["score"], best["turn"]
    return None, distance_score(board, observed, visible), board.turn


def with_castling(board):
    """Grant castling rights for every king/rook pair still on its home squares.
    (Boards built from a FEN body have none, which makes castling unmatchable.)"""
    board.castling_rights = chess.BB_CORNERS
    board.castling_rights = board.clean_castling_rights()
    return board


def merge_types(tracked, observed):
    """Resync board: observed occupancy, but keep the tracked board's piece types wherever
    the same colour already sat there (the detector's type labels are unreliable)."""
    out = chess.Board(None)
    for sq in chess.SQUARES:
        po, pt = observed.piece_at(sq), tracked.piece_at(sq)
        if po is None:
            continue
        out.set_piece_at(sq, pt if (pt is not None and pt.color == po.color) else po)
    if out.king(chess.WHITE) is None or out.king(chess.BLACK) is None:
        out = observed.copy()
    return with_castling(out)


def fmt_moves(board, moves):
    b = board.copy()
    parts = []
    for m in moves:
        prefix = f"{b.fullmove_number}." if b.turn == chess.WHITE else f"{b.fullmove_number}..."
        parts.append(prefix + b.san(m))
        b.push(m)
    return " ".join(parts)


# =====================================================================
# Main
# =====================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--stable", type=int, default=2)
    ap.add_argument("--jitter", type=int, default=1,
                    help="squares of occupancy change allowed within one stable run (default 1)")
    ap.add_argument("--tolerance", type=float, default=1.5)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--start-fen", default="auto")
    ap.add_argument("--save-frames", action="store_true")
    args = ap.parse_args()

    cache_path = Path(args.video).with_name(Path(args.video).stem + "_fens.json")
    if args.replay:
        samples = json.loads(cache_path.read_text())
        print(f"replaying {len(samples)} cached frames from {cache_path}")
        analyse(samples, args)
        return

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(args.interval * fps)))
    sample_idx = list(range(0, n_frames, step))
    print(f"{args.video}: {n_frames / fps:.1f}s @ {fps:.1f}fps, sampling every {args.interval}s "
          f"-> {len(sample_idx)} frames")

    out_dir = None
    if args.save_frames:
        out_dir = Path(args.video).with_name(Path(args.video).stem + "_frames")
        out_dir.mkdir(exist_ok=True)

    print("Loading models...")
    pm, cm = load_models()

    def read(idx):
        nonlocal cap
        for attempt in range(3):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if ok:
                return frame
            print(f"  (read of frame {idx} failed, reopening video; attempt {attempt + 1})")
            cap.release()
            cap = cv2.VideoCapture(args.video)
        return None

    def finish(s, frame, fine, ecc, source, pieces):
        inside, shift = 0.0, (0, 0)
        if fine is not None:
            fine, ecc, inside, shift = anchor_to_pieces(frame, fine, ecc, pieces)
            if shift != (0, 0):
                source = f"{source}{shift[0]:+d}{shift[1]:+d}"
        s.update(fine=fine, ecc=ecc, inside=inside, source=source,
                 trusted=fine is not None and ecc >= MIN_ECC and inside >= MIN_INSIDE)
        s["visible"] = None
        if s["trusted"]:
            s["board_fen"], s["H"], s["keep"] = fen_for_quad(fine, pieces)
            s["trusted"] = s["board_fen"] is not None
            if s["H"] is not None:
                s["visible"] = visible_squares(s["H"], frame.shape)
        if out_dir is not None:
            cv2.imwrite(str(out_dir / f"frame_{s['k']:04d}_{s['t']:06.1f}s.jpg"), draw_debug(frame, s))
        print(f"  t={s['t']:6.1f}s  {len(pieces):2d} pieces  {source or '-':9s} ecc={s['ecc']:.2f} "
              f"inside={s['inside']:.2f}  {s['board_fen'] if s['trusted'] else 'untrusted'}")
        return s["fine"], s["ecc"]

    # ---- pass 1: forward, seed then track ----
    samples = []
    t0 = time.time()
    prev_fine, fails, seed_k = None, 0, None
    for k, idx in enumerate(sample_idx):
        frame = read(idx)
        if frame is None:
            break
        s = {"k": k, "t": idx / fps, "board_fen": None, "H": None, "keep": None}
        pieces = detect_pieces_frame(frame, pm)
        s["pieces"] = pieces
        fine, ecc, source = None, 0.0, None
        if len(pieces) >= 2:
            if prev_fine is not None:
                fine, ecc = refine_quad(frame, prev_fine, retries=False)
                source = "track"
            may_search = (fails + 1 >= TRACK_FAILS_BEFORE_RESEED) if prev_fine is not None \
                else (seed_k is None and k % SEED_EVERY == 0)
            if ecc < GOOD_ECC and may_search:
                f2, e2, src2 = search_quad(frame, pieces, cm)
                if e2 > ecc:
                    fine, ecc, source = f2, e2, src2
        fine, ecc = finish(s, frame, fine, ecc, source, pieces)
        if s["trusted"] and ecc >= GOOD_ECC:
            prev_fine, fails = fine, 0
            if seed_k is None:
                seed_k = k
        else:
            fails += 1
        samples.append(s)

    # ---- pass 1b: frames before the seed, tracked backwards from it ----
    if seed_k:
        print(f"re-doing {seed_k} frames before the seed (t={samples[seed_k]['t']:.1f}s) backwards")
        prev_fine = samples[seed_k]["fine"]
        for k in range(seed_k - 1, -1, -1):
            s = samples[k]
            if s["trusted"]:
                continue
            frame = read(sample_idx[k])
            pieces = s["pieces"]
            if frame is None or len(pieces) < 2:
                continue
            fine, ecc = refine_quad(frame, prev_fine, retries=False)
            if ecc > s["ecc"]:
                fine, ecc = finish(s, frame, fine, ecc, "track<", pieces)
                if s["trusted"] and ecc >= GOOD_ECC:
                    prev_fine = fine
    cap.release()
    elapsed = time.time() - t0
    trusted = sum(1 for s in samples if s["trusted"])
    print(f"detection: {elapsed:.0f}s total, {elapsed / max(1, len(samples)):.1f}s per frame; "
          f"{trusted}/{len(samples)} frames trusted")

    cache_path.write_text(json.dumps(
        [{"t": s["t"], "board_fen": s["board_fen"] if s["trusted"] else None,
          "trusted": bool(s["trusted"]), "ecc": s["ecc"], "source": s["source"],
          "visible": s.get("visible")} for s in samples], indent=0))
    print(f"per-frame results cached to {cache_path} (re-run with --replay to redo only the move logic)")
    analyse(samples, args)


def analyse(samples, args):
    # ---- pass 2: stable positions ----
    stable = stable_positions(samples, args.stable, args.jitter)
    print(f"\n{len(stable)} stable positions (>= {args.stable} consecutive samples, "
          f"<= {args.jitter} square of jitter)")
    if not stable:
        raise SystemExit("nothing stable detected; try a smaller --interval or --stable 1")

    # ---- pass 3: moves ----
    near_start = False
    if args.start_fen == "startpos":
        board, turn_unknown = chess.Board(), False
    elif args.start_fen == "auto":
        board = chess.Board(None)
        board.set_board_fen(stable[0][1])
        board = with_castling(board)
        turn_unknown = True
        stable = stable[1:]
        d_start = occupancy_diff(occupancy(board.board_fen()), occupancy(chess.STARTING_BOARD_FEN))
        if d_start == 0:
            board, turn_unknown = chess.Board(), False
            print("start position: standard start")
        elif d_start <= 6:
            # Close to the standard start (a few pieces gone, or out of frame): keep the
            # observed occupancy but take piece types from the standard start, since the
            # detector's type labels are unreliable.
            board = merge_types(chess.Board(), board)
            near_start = True
            print(f"start position: {d_start} squares off the standard start; using its piece types "
                  f"with the observed occupancy: {board.board_fen()}")
        else:
            print(f"start position taken from video: {board.board_fen()}")
    else:
        board, turn_unknown = chess.Board(args.start_fen), False

    moves_all, san_all = [], []
    unexplained = 0
    first_change = True
    print("\nTimeline:")
    print(f"  t=  0.0s  {board.board_fen()}  (start)")
    for t, bf, vis in stable:
        observed = chess.Board(None)
        observed.set_board_fen(bf)
        occ0, typ0 = board_distance(board, observed, vis)
        if occ0 == 0:
            continue
        nomove = distance_score(board, observed, vis)
        moves, dist, turn = explain_change(board, observed, args.tolerance, turn_unknown, visible=vis)
        if moves is None and first_change and near_start:
            # the merged start may have lost a piece the detector never saw; try the real start
            alt = chess.Board()
            m2, d2, t2 = explain_change(alt, observed, args.tolerance, False, visible=vis)
            if m2 is not None:
                print("            (first change is explained from the standard start; adopting it)")
                board, turn_unknown = alt, False
                moves, dist, turn = m2, d2, t2
                nomove = distance_score(board, observed, vis)
        first_change = False
        print(f"  t={t:6.1f}s  {bf}" + ("" if vis is None or len(vis) == 64 else f"  ({64 - len(vis)} squares out of frame)"))
        if moves is not None and dist + MOVE_MARGIN > nomove:
            moves = None  # the move does not beat "nothing happened, detector noise"
        if moves is None and occ0 <= args.tolerance:
            print(f"            ~ within tolerance of the current position ({occ0:.1f}), treating as noise: "
                  f"{', '.join(square_diff(board, observed))}")
            continue
        if moves is None:
            unexplained += 1
            diff = ', '.join(square_diff(board, observed))
            if unexplained < 2:
                print(f"            ?? no legal sequence explains this (occupancy error {occ0:.1f}); "
                      f"skipping it. Diff: {diff}")
                continue
            print(f"            ?? no legal sequence explains this either (occupancy error {occ0:.1f}); "
                  f"resyncing to it. Diff: {diff}")
            fullmove = board.fullmove_number
            board = merge_types(board, observed)
            board.fullmove_number = fullmove
            turn_unknown = True
            unexplained = 0
            continue
        unexplained = 0
        board.turn = turn
        san = fmt_moves(board, moves)
        note = "" if dist == 0 else f"  (best legal fit, residual {dist:.1f})"
        print(f"            -> {san}{note}")
        san_all.append(san)
        for m in moves:
            board.push(m)
            moves_all.append(m)
        turn_unknown = False

    print("\nMoves:")
    if not moves_all:
        print("  (none)")
    else:
        print("  " + " ".join(san_all))
        print("  UCI: " + " ".join(m.uci() for m in moves_all))
    print(f"\nFinal position: {board.board_fen()}")


if __name__ == "__main__":
    main()
