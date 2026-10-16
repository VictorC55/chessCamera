"""
Stitch the annotated frames from video_to_moves.py --save-frames into a
demo video, with a side panel showing the FEN the pipeline read from each
frame and the moves it had recognised by that time.

Usage:
    python yoloTesting/make_demo_video.py videos/clip.mp4 [--fps 2]

Reads  <video>_frames/frame_*.jpg   (from --save-frames)
       <video>_fens.json            (per-frame cache)
       the --replay timeline        (run internally)
Writes <video>_demo.mp4 and <video>_contact_sheet.jpg
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

PANEL_W = 560
FONT = cv2.FONT_HERSHEY_SIMPLEX


def replay_timeline(video):
    """Run video_to_moves.py --replay and parse (t, text) events from its timeline."""
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("video_to_moves.py")),
                          str(video), "--replay"], capture_output=True, text=True).stdout
    events, start, t = [], None, None
    for line in out.splitlines():
        m = re.match(r"\s+t=\s*([\d.]+)s\s+(\S+)", line)
        if m:
            t = float(m.group(1))
            if "(start)" in line:
                start = m.group(2)
            continue
        if t is None:
            continue
        s = line.strip()
        if s.startswith("->"):
            events.append((t, "move", s[3:].split("  (")[0]))
        elif s.startswith("~"):
            events.append((t, "noise", "treated as noise"))
        elif s.startswith("??"):
            events.append((t, "skip", "unexplained, " + ("resync" if "resync" in s else "skipped")))
    moves_line = ""
    for line in out.splitlines():
        if re.match(r"\s+\d+\.", line):
            moves_line = line.strip()
    return start, events, moves_line


def draw_board(fen, size=240):
    """Tiny 2D board from a board FEN (letters only, no images needed)."""
    img = np.full((size, size, 3), 255, np.uint8)
    sq = size // 8
    rows = fen.split("/") if fen else ["8"] * 8
    for r in range(8):
        for c in range(8):
            col = (235, 236, 208) if (r + c) % 2 == 0 else (119, 149, 86)  # lichess-ish, BGR
            cv2.rectangle(img, (c * sq, r * sq), ((c + 1) * sq, (r + 1) * sq), col, -1)
    for r, row in enumerate(rows[:8]):
        c = 0
        for ch in row:
            if ch.isdigit():
                c += int(ch)
                continue
            x, y = c * sq + sq // 2, r * sq + sq // 2
            white = ch.isupper()
            cv2.circle(img, (x, y), sq // 2 - 3, (245, 245, 245) if white else (30, 30, 30), -1)
            cv2.circle(img, (x, y), sq // 2 - 3, (0, 0, 0), 1)
            cv2.putText(img, ch.upper(), (x - 7, y + 6), FONT, 0.55, (0, 0, 0) if white else (255, 255, 255), 2)
            c += 1
    return img


def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=2.0, help="playback rate of sampled frames")
    args = ap.parse_args()
    video = Path(args.video)
    frames_dir = video.with_name(video.stem + "_frames")
    cache = json.loads(video.with_name(video.stem + "_fens.json").read_text())
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames or not cache:
        raise SystemExit("run video_to_moves.py --save-frames first")
    start, events, moves_line = replay_timeline(video)
    print(f"{len(frames)} frames, {len(events)} timeline events")

    first = cv2.imread(str(frames[0]))
    H, W = first.shape[:2]
    scale = 720 / H
    FW, FH = int(W * scale), 720
    out_path = video.with_name(video.stem + "_demo.mp4")
    vw = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (FW + PANEL_W, FH))

    keyframes = []
    for i, (f, s) in enumerate(zip(frames, cache)):
        img = cv2.resize(cv2.imread(str(f)), (FW, FH))
        panel = np.full((FH, PANEL_W, 3), 28, np.uint8)
        t = s["t"]
        y = 36
        cv2.putText(panel, f"t = {t:5.1f}s", (16, y), FONT, 0.9, (255, 255, 255), 2); y += 34
        status = "TRUSTED" if s["trusted"] else "untrusted (skipped)"
        colr = (80, 220, 80) if s["trusted"] else (60, 60, 230)
        cv2.putText(panel, f"{status}  fit={s['ecc']:.2f}  {s['source'] or ''}", (16, y), FONT, 0.6, colr, 2); y += 30
        cv2.putText(panel, "what the camera read:", (16, y), FONT, 0.55, (200, 200, 200), 1); y += 10
        board = draw_board(s["board_fen"] if s["trusted"] else None, 240)
        panel[y:y + 240, 16:256] = board
        if not s["trusted"]:
            cv2.line(panel, (16, y), (256, y + 240), (60, 60, 230), 3)
            cv2.line(panel, (256, y), (16, y + 240), (60, 60, 230), 3)
        y += 240 + 28
        # events up to now
        done = [e for e in events if e[0] <= t + 1e-6]
        recent = done[-1] if done else None
        if recent and abs(recent[0] - t) < 0.75:
            col = {"move": (80, 220, 80), "noise": (200, 200, 80), "skip": (60, 60, 230)}[recent[1]]
            cv2.putText(panel, f"@ {recent[0]:.1f}s: {recent[2]}", (16, y), FONT, 0.6, col, 2)
            keyframes.append((i, f"t={t:.1f}s {recent[2]}"))
        y += 34
        cv2.putText(panel, "moves recognised so far:", (16, y), FONT, 0.55, (200, 200, 200), 1); y += 26
        san = " ".join(e[2] for e in done if e[1] == "move")
        for line in wrap(san, 38)[:8]:
            cv2.putText(panel, line, (16, y), FONT, 0.6, (255, 255, 255), 1); y += 26
        vw.write(np.hstack([img, panel]))
    vw.release()
    print(f"wrote {out_path}")

    # contact sheet: the frames where a move was recognised (up to 12)
    picks = [k for k in keyframes if "treated" not in k[1] and "unexplained" not in k[1]][:12]
    if picks:
        tiles = []
        for i, cap in picks:
            tile = cv2.resize(cv2.imread(str(frames[i])), (640, 360))
            cv2.rectangle(tile, (0, 0), (640, 28), (0, 0, 0), -1)
            cv2.putText(tile, cap, (8, 20), FONT, 0.6, (0, 255, 255), 2)
            tiles.append(tile)
        while len(tiles) % 3:
            tiles.append(np.zeros((360, 640, 3), np.uint8))
        rows = [np.hstack(tiles[r:r + 3]) for r in range(0, len(tiles), 3)]
        sheet = np.vstack(rows)
        sheet_path = video.with_name(video.stem + "_contact_sheet.jpg")
        cv2.imwrite(str(sheet_path), sheet)
        print(f"wrote {sheet_path}")
    print("\nfinal move list:", moves_line)


if __name__ == "__main__":
    main()
