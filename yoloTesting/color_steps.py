"""Draw every stage of the colour-based board finder (board_color.py + refine_corners.py) as a
labelled contact sheet, for explaining how it works.

Usage: python yoloTesting/color_steps.py image.jpg [out.jpg]
Default output: documentation/color_steps_<image stem>.jpg
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board_color as bc
import refine_corners as rc
from chess_pipeline import _order_corners

TILE_W, TILE_H, HEAD = 640, 420, 78
FONT = cv2.FONT_HERSHEY_SIMPLEX
GREEN, RED, ORANGE, YELLOW, CYAN, WHITE = (0, 200, 0), (0, 0, 255), (0, 140, 255), (0, 220, 220), (220, 200, 0), (255, 255, 255)


def fit(img, w=TILE_W, h=TILE_H):
    """Letterbox `img` into w x h on black."""
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    s = min(w / img.shape[1], h / img.shape[0])
    r = cv2.resize(img, (int(img.shape[1] * s), int(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    out = np.zeros((h, w, 3), np.uint8)
    y, x = (h - r.shape[0]) // 2, (w - r.shape[1]) // 2
    out[y:y + r.shape[0], x:x + r.shape[1]] = r
    return out


def tile(img, title, lines=()):
    out = np.full((HEAD + TILE_H, TILE_W, 3), 28, np.uint8)
    cv2.putText(out, title, (10, 26), FONT, 0.7, WHITE, 2, cv2.LINE_AA)
    for i, ln in enumerate(lines[:2]):
        cv2.putText(out, ln, (10, 50 + 20 * i), FONT, 0.48, (200, 200, 200), 1, cv2.LINE_AA)
    out[HEAD:] = fit(img)
    return out


def mask_rgb(mask, color=WHITE):
    out = np.zeros((*mask.shape, 3), np.uint8)
    out[mask > 0] = color
    return out


def dim(img, keep):
    """Colour where keep, grey and dark elsewhere."""
    grey = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR) // 3
    out = grey.copy()
    out[keep > 0] = img[keep > 0]
    return out


def main(path, out_path):
    img0 = cv2.imread(str(path))
    if img0 is None:
        raise SystemExit(f"cannot read {path}")
    scale = min(1.0, bc.WORK_SIZE / max(img0.shape[:2]))
    img = cv2.resize(img0, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img0.copy()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    area = img.shape[0] * img.shape[1]
    tiles = []

    # ---- 1. input
    tiles.append(tile(img, "1. Input", [f"{img0.shape[1]}x{img0.shape[0]} px, searched at {img.shape[1]}x{img.shape[0]}",
                                       "(longest side resized to 1920 so pixel limits mean the same thing)"]))

    # ---- 2. saturation / brightness gate
    sat = ((hsv[..., 1] >= bc.MIN_SAT) & (hsv[..., 2] >= bc.MIN_VAL)).astype(np.uint8)
    tiles.append(tile(dim(img, sat), "2. HSV gate: keep S >= 70 and V >= 50",
                      [f"{100 * sat.mean():.0f}% of pixels survive (shown in colour)",
                       "floor, cream squares, white pieces, skin and shadows drop out"]))

    # ---- 3. score all 72 hue bands
    scored = {}
    for centre in range(0, 180, 5):
        for half in (bc.HUE_HALF, 2 * bc.HUE_HALF):
            m = cv2.erode(bc._hue_band(hsv, centre, half), np.ones((5, 5), np.uint8))
            blobs = bc._square_blobs(m, area)
            lat = int(bc._on_lattice(blobs).sum()) if len(blobs) >= bc.MIN_SQUARES else 0
            scored[(centre, half)] = (lat, len(blobs))
    cands = bc._hue_candidates(hsv)
    kept = [(c, h) for c, h, _ in cands]
    chart = np.full((TILE_H, TILE_W, 3), 28, np.uint8)
    top = max(1, max(v[0] for v in scored.values()))
    bw = TILE_W // 36
    for i, centre in enumerate(range(0, 180, 5)):
        x = i * bw
        # hue swatch along the bottom
        sw = cv2.cvtColor(np.uint8([[[centre, 255, 255]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
        cv2.rectangle(chart, (x, TILE_H - 22), (x + bw - 1, TILE_H - 6), sw, -1)
        for j, half in enumerate((bc.HUE_HALF, 2 * bc.HUE_HALF)):
            lat = scored[(centre, half)][0]
            hgt = int((TILE_H - 50) * lat / top)
            col = GREEN if (centre, half) in kept else (110, 110, 110)
            x0 = x + j * (bw // 2)
            cv2.rectangle(chart, (x0, TILE_H - 26 - hgt), (x0 + bw // 2 - 2, TILE_H - 26), col, -1)
    for rank, (c, h, blobs) in enumerate(cands):
        cv2.putText(chart, f"#{rank + 1}: hue {c}+-{h}  {scored[(c, h)][0]} on lattice / {len(blobs)} blobs",
                    (10, 24 + 22 * rank), FONT, 0.55, GREEN, 1, cv2.LINE_AA)
    cv2.putText(chart, "bar = blobs with a diagonal neighbour; left bar narrow band, right bar wide band", (10, TILE_H - 34), FONT, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
    tiles.append(tile(chart, "3. Score all 72 hue bands (36 centres x 2 widths)",
                      ["each band: mask -> erode -> square blobs -> count diagonal neighbours",
                       "top 3 kept, at least 12 hue steps apart (green bars)"]))

    if not cands:
        raise SystemExit("no coloured checkerboard found")
    # every candidate gets the full fit, exactly as search_color does; the highest ECC wins and the
    # remaining tiles walk through that band (its lattice rank is shown)
    fits = []
    for c, h, bl in cands:
        pts_c = bc._board_region(bc._hue_band(hsv, c, h), bl)
        if pts_c is None or len(pts_c) < 4:
            fits.append(None)
            continue
        rq = _order_corners(bc._quad_from_points(pts_c))
        fits.append((rq, *bc.refine_hue(img, rq, c, h)))
    ranked = [(fits[i][2]["ecc"], i) for i in range(len(cands)) if fits[i] is not None]
    if not ranked:
        raise SystemExit("no candidate band produced a region")
    win = max(ranked)[1]
    hue, half, blobs_win = cands[win]
    band = bc._hue_band(hsv, hue, half)
    others = [f"hue {cands[i][0]}+-{cands[i][1]}: {fits[i][2]['ecc']:.2f}" if fits[i] else f"hue {cands[i][0]}+-{cands[i][1]}: no region"
              for i in range(len(cands)) if i != win]

    # ---- 4. the winning band's mask, and erosion close-up
    tiles.append(tile(dim(img, band), f"4. Winning band: hue {hue} +- {half} (ranked #{win + 1} of 3 by lattice)",
                      [f"{100 * band.mean():.1f}% of pixels; this is the mask every later step uses",
                       "OpenCV hue runs 0-179 (0 = red, 60 = green, 120 = blue)"]))
    eroded = cv2.erode(band, np.ones((5, 5), np.uint8))
    # close-up around the densest blob cluster
    lat_win = bc._on_lattice(blobs_win)
    focus = [c for c, o in zip(blobs_win, lat_win) if o] or blobs_win
    cents = np.array([cv2.boundingRect(c)[:2] for c in focus])
    cx, cy = (np.median(cents, 0) if len(cents) else (img.shape[1] / 2, img.shape[0] / 2)).astype(int)
    side = int(np.median([max(cv2.boundingRect(c)[2:]) for c in blobs_win]) * 3) if len(blobs_win) else 200
    x0, y0 = max(0, cx - side), max(0, cy - side // 2)
    crop_b = mask_rgb(band[y0:y0 + side, x0:x0 + 2 * side])
    crop_a = mask_rgb(eroded[y0:y0 + side, x0:x0 + 2 * side])
    for c, col in ((crop_b, RED), (crop_a, GREEN)):
        n, _ = cv2.connectedComponents(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY))
        cv2.putText(c, f"{n - 1} blobs", (8, 24), FONT, 0.7, col, 2, cv2.LINE_AA)
    both = np.vstack([crop_b, np.full((6, crop_b.shape[1], 3), 90, np.uint8), crop_a])
    tiles.append(tile(both, "5. Erode 5x5 (top: before, bottom: after)",
                      ["each blob shrinks 2 px per side, so diagonal squares that",
                       "touch at one corner split into separate blobs"]))

    # ---- 6. square-like blobs + size filter
    opened = cv2.morphologyEx(eroded, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    shape_ok = []
    for c in contours:
        a = cv2.contourArea(c)
        if not (area * 2e-5 < a < area * 0.02):
            continue
        hull = cv2.convexHull(c)
        if a / max(cv2.contourArea(hull), 1) < 0.75:
            continue
        poly = cv2.approxPolyDP(hull, 0.06 * cv2.arcLength(hull, True), True)
        if 4 <= len(poly) <= 6:
            shape_ok.append(c)
    areas = np.array([cv2.contourArea(c) for c in shape_ok]) if shape_ok else np.array([])
    med = np.median(areas) if len(areas) else 0
    size_ok = [c for c, a in zip(shape_ok, areas) if med / 6 < a < med * 6]
    vis = (img // 2).copy()
    cv2.drawContours(vis, contours, -1, RED, 2)
    cv2.drawContours(vis, shape_ok, -1, YELLOW, 2)
    cv2.drawContours(vis, size_ok, -1, GREEN, 3)
    tiles.append(tile(vis, "6. Square-like blobs",
                      [f"red: all {len(contours)} blobs | yellow: {len(shape_ok)} pass shape (area 0.002-2% of image,",
                       f"solidity>=0.75, 4-6 corners) | green: {len(size_ok)} within 1/6..6x median area {med:.0f}px"]))

    # ---- 7. lattice check
    on = bc._on_lattice(size_ok)
    vis = (img // 2).copy()
    boxes = np.array([cv2.boundingRect(c) for c in size_ok], float)
    cents = boxes[:, :2] + boxes[:, 2:] / 2
    for i, c in enumerate(size_ok):
        cv2.drawContours(vis, [c], -1, GREEN if on[i] else ORANGE, 3)
    for i in range(len(size_ok)):
        if not on[i]:
            continue
        dx = np.abs(cents[:, 0] - cents[i, 0]) / boxes[i, 2]
        dy = np.abs(cents[:, 1] - cents[i, 1]) / boxes[i, 3]
        ok = (dx > 0.4) & (dx < 1.6) & (dy > 0.4) & (dy < 1.6)
        ok[i] = False
        js = np.where(ok)[0]
        if len(js):
            j = js[np.argmin(dx[js] + dy[js])]
            cv2.line(vis, tuple(cents[i].astype(int)), tuple(cents[j].astype(int)), CYAN, 2)
    tiles.append(tile(vis, "7. Lattice check: is a diagonal neighbour where it should be?",
                      [f"green: {int(on.sum())} of {len(size_ok)} blobs have another blob ~1 width across and ~1 height down",
                       "(measured in the blob's own size, so low angles still work); orange: none found"]))

    # ---- 8. region -> rough quad
    pts = bc._board_region(band, blobs_win)
    sidepx = float(np.median([np.sqrt(cv2.contourArea(c)) for c in blobs_win]))
    n, labels = cv2.connectedComponents(band)
    seeds = np.zeros(n, int)
    for c in blobs_win:
        x, y = c.reshape(-1, 2).mean(0).astype(int)
        seeds[labels[y, x]] += 1
    keep = seeds > 0
    keep[0] = False
    seeded = keep[labels].astype(np.uint8)
    k = max(5, int(2.2 * sidepx) | 1)
    closed = cv2.morphologyEx(seeded, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    vis = (img // 2).copy()
    vis[seeded > 0] = (vis[seeded > 0] * 0.4 + np.array(YELLOW) * 0.6).astype(np.uint8)
    cc, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vis, cc, -1, CYAN, 2)
    rough = _order_corners(bc._quad_from_points(pts))
    cv2.polylines(vis, [rough.astype(np.int32).reshape(-1, 1, 2)], True, RED, 4)
    tiles.append(tile(vis, "8. Region -> rough quad",
                      ["yellow: mask parts that contain a square blob | cyan: after closing with an",
                       f"ellipse {k}px (~2.2 squares) wide | red: largest region's hull cut to 4 corners"]))

    # ---- 9. canvas + ECC fit
    hue_mask = lambda im: bc._hue_band(cv2.cvtColor(im, cv2.COLOR_BGR2HSV), hue, half).astype(np.float32)
    green = hue_mask(img)
    canvas, H = rc._canvas(green, rough.astype(np.float32))
    score0, W = rc._ecc(canvas, [np.eye(3, dtype=np.float32)])
    retried = False
    if score0 < rc.WEAK_ECC:
        retried = True
        score0, W = rc._ecc(canvas, rc._rotated_starts((0, -10, 10, -20, 20)))
    cv_vis = cv2.cvtColor((canvas * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    g = rc.GRID.astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(cv_vis, [g], True, RED, 2)
    for i in range(1, 8):  # template grid lines
        p = rc.M * rc.C + i * rc.C
        cv2.line(cv_vis, (rc.M * rc.C, p), ((rc.M + 8) * rc.C, p), (0, 0, 120), 1)
        cv2.line(cv_vis, (p, rc.M * rc.C), (p, (rc.M + 8) * rc.C), (0, 0, 120), 1)
    if W is not None:
        fitted_canvas = cv2.perspectiveTransform(rc.GRID[None], W)[0]
        cv2.polylines(cv_vis, [fitted_canvas.astype(np.int32).reshape(-1, 1, 2)], True, GREEN, 2)
    tiles.append(tile(cv_vis, "9. Warp mask onto a canvas, fit a perfect checkerboard (ECC)",
                      ["red: where the rough quad landed (8x8 with a 2-square margin) | green: where ECC",
                       f"moved the template to | score {score0:.2f}" + (" after rotated restarts" if retried else " on first try")]))

    # ---- 10. shift check
    fitted = cv2.perspectiveTransform(cv2.perspectiveTransform(rc.GRID[None], W), np.linalg.inv(H))[0]
    canvas2, H2 = rc._canvas(green, fitted)
    quality = rc._grid_quality(canvas2)
    shift = max(quality, key=lambda kk: quality[kk][0])
    cv_vis = cv2.cvtColor((canvas2 * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    for (dy, dx), (s, con, ring) in quality.items():
        col = GREEN if (dy, dx) == shift else (90, 90, 90)
        off = rc.GRID + np.float32([dx * rc.C, dy * rc.C])
        cv2.polylines(cv_vis, [off.astype(np.int32).reshape(-1, 1, 2)], True, col, 3 if col == GREEN else 1)
        cv2.putText(cv_vis, f"{s:+.2f}", (int(off[0, 0]) + 4 + dx * 0, int(off[0, 1]) + 16 + dy * 0), FONT, 0.4, col, 1, cv2.LINE_AA)
    tiles.append(tile(cv_vis, "10. Shift check: a checkerboard also fits one square off",
                      ["score each of the 9 placements: squares alternate strongly, ring outside has no",
                       f"dark-square colour | best shift (rows, cols) = {shift}" + (" -> keep the fit" if shift == (0, 0) else " -> move and re-fit")]))

    # ---- 11. final
    rough, fine, info = fits[win]
    vis = img.copy()
    cv2.polylines(vis, [rough.astype(np.int32).reshape(-1, 1, 2)], True, RED, 3)
    cv2.polylines(vis, [np.asarray(fine).astype(np.int32).reshape(-1, 1, 2)], True, GREEN, 4)
    for i, (x, y) in enumerate(np.asarray(fine)):
        cv2.circle(vis, (int(x), int(y)), 10, GREEN, -1)
        cv2.putText(vis, str(i), (int(x) + 12, int(y) - 8), FONT, 0.8, GREEN, 2, cv2.LINE_AA)
    tiles.append(tile(vis, "11. Final corners mapped back into the photo",
                      [f"red: rough | green: refined, ECC {info['ecc']:.2f}, ok={info['ok']} (contrast {info['contrast']:.2f}, ring {info['ring_green']:.2f})",
                       "other candidate bands scored " + (", ".join(others) if others else "none") + " -> highest ECC wins"]))

    # ---- compose
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    while len(tiles) < rows * cols:
        tiles.append(np.full_like(tiles[0], 28))
    gap = 8
    sheet = np.full((rows * (HEAD + TILE_H) + (rows + 1) * gap, cols * TILE_W + (cols + 1) * gap, 3), 12, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        y = gap + r * (HEAD + TILE_H + gap)
        x = gap + c * (TILE_W + gap)
        sheet[y:y + t.shape[0], x:x + t.shape[1]] = t
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("saved", out_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "documentation" / f"color_steps_{src.stem}.jpg"
    main(src, dst)
