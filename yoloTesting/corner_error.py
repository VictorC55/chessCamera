"""Measure how far predicted corners are from the labels, in board squares.

Usage: python corner_error.py path/to/weights.pt path/to/dataset-folder [split] [imgsz]
split defaults to "valid", imgsz to 960. Run prep_dataset.py on the folder first
so labels use the same corner order the model was trained on.
Reports the model's corners and the same corners after refine_corners.py, and
writes to corner_preds/ next to the weights folder:
  <photo>.jpg     labels green, model red, refined blue, "model -> refined" error per corner
  zoom_sheet.jpg  every corner up close (one row per photo), 3 squares across

Pose mAP is graded relative to the box size and reads ~0.98 even when corners are
a full square off; this is the number that matters for mapping pieces to squares.
One square = the board's mean side length / 8 in that photo.
"""
import sys
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO
from refine_corners import refine

GOOD = 0.25  # corners within a quarter square are safely inside the right square
GREEN, RED, BLUE = (0, 200, 0), (0, 0, 255), (255, 128, 0)
ZOOM = 240   # zoom-sheet tile size in pixels


def draw(img, gt, pred, fine, errs):
    """Mark label (green), model (red) and refined (blue) corners; pred=None marks a miss. Returns the marked
    image (for the zoom sheet) and a copy with the per-corner error text added (for the full-size photo)."""
    s = max(img.shape[:2]) / 1000  # scale marks to the photo size
    t = max(1, int(1.5 * s))
    quads = [(gt, GREEN)] if pred is None else [(gt, GREEN), (pred, RED), (fine, BLUE)]
    for pts, color in quads:
        cv2.polylines(img, [pts.astype(np.int32).reshape(-1, 1, 2)], True, color, t)
        for x, y in pts:
            cv2.drawMarker(img, (int(x), int(y)), color, cv2.MARKER_CROSS, int(14 * s), t)
    labelled = img.copy()
    if pred is None:
        cv2.putText(labelled, "NO BOARD FOUND", (int(20 * s), int(60 * s)), cv2.FONT_HERSHEY_SIMPLEX, 2 * s, RED, 2 * t)
    else:
        for i, ((x, y), (em, ef)) in enumerate(zip(gt, errs)):
            cv2.putText(labelled, f"{i}: {em:.2f} -> {ef:.2f}", (int(x + 10 * s), int(y - 10 * s)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9 * s, BLUE, t)
    return img, labelled


def zoom_row(img, gt, square, name, errs=None):
    """Four tiles, each 3 squares across, centred on a labelled corner, captioned with model -> refined error."""
    h, w = img.shape[:2]
    half = int(1.5 * square)
    pad = cv2.copyMakeBorder(img, half, half, half, half, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    tiles = []
    for i, (x, y) in enumerate(gt):
        x, y = int(np.clip(x, 0, w - 1)) + half, int(np.clip(y, 0, h - 1)) + half
        tile = cv2.resize(pad[y - half:y + half, x - half:x + half], (ZOOM, ZOOM))
        caption = f"{name} c{i}" + (f"  {errs[i][0]:.2f}->{errs[i][1]:.2f}" if errs else "  missed")
        cv2.rectangle(tile, (0, 0), (ZOOM, 26), (40, 40, 40), -1)
        cv2.putText(tile, caption, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(tile)
    return np.hstack(tiles)


def summary(label, errs):
    e = np.concatenate(errs)
    print(f"{label:8s} median {np.median(e):.2f}, mean {e.mean():.2f}, worst {e.max():.2f} squares; "
          f"{np.mean(e < GOOD):.0%} of corners within {GOOD} square")


def corner_errors(weights, root, split="valid", imgsz=960, device="cpu"):
    """Print per-photo corner errors (model and refined), save images, return refined errors in squares."""
    model = YOLO(weights)
    out_dir = Path(weights).parent.parent / "corner_preds"
    out_dir.mkdir(exist_ok=True)
    img_dir = Path(root) / split / "images"
    model_errs, fine_errs, missed, flagged, rows = [], [], [], [], []
    for ip in sorted(p for p in img_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}):
        t = [float(v) for v in (img_dir.parent / "labels" / f"{ip.stem}.txt").read_text().split()]
        r = model.predict(ip, imgsz=imgsz, conf=0.25, max_det=1, device=device, verbose=False)[0]
        h, w = r.orig_shape
        gt = np.array([[t[5 + i * 3] * w, t[6 + i * 3] * h] for i in range(4)])
        square = np.mean([np.linalg.norm(gt[i] - gt[(i + 1) % 4]) for i in range(4)]) / 8
        name = ip.name.split("_jpg")[0]
        if not len(r.boxes):
            missed.append(ip.name)
            marked, labelled = draw(r.orig_img.copy(), gt, None, None, None)
            cv2.imwrite(str(out_dir / ip.name), labelled)
            rows.append(zoom_row(marked, gt, square, name))
            continue
        pred = r.keypoints.xy[0].cpu().numpy()
        fine, info = refine(r.orig_img, pred)
        em = np.linalg.norm(pred - gt, axis=1) / square
        ef = np.linalg.norm(fine - gt, axis=1) / square
        model_errs.append(em)
        fine_errs.append(ef)
        if not info["ok"]:
            flagged.append(name)
        marked, labelled = draw(r.orig_img.copy(), gt, pred, fine, list(zip(em, ef)))
        cv2.imwrite(str(out_dir / ip.name), labelled)
        rows.append(zoom_row(marked, gt, square, name, list(zip(em, ef))))
        print(f"  {name:10s} model {' '.join(f'{v:4.2f}' for v in em)}  ->  refined {' '.join(f'{v:4.2f}' for v in ef)}"
              f"{'' if info['ok'] else '   (refinement flagged: ' + str(info) + ')'}")

    if rows:
        cv2.imwrite(str(out_dir / "zoom_sheet.jpg"), np.vstack(rows))
    print(f"\nannotated photos: {out_dir}  (zoom_sheet.jpg = every corner up close)")
    print(f"{split}: board found in {len(model_errs)}/{len(model_errs) + len(missed)} photos", end="")
    print(f" (missed: {', '.join(missed)})" if missed else "")
    if flagged:
        print(f"refinement flagged as unreliable on: {', '.join(flagged)}")
    if model_errs:
        summary("model", model_errs)
        summary("refined", fine_errs)
        return np.concatenate(fine_errs)
    return np.array([])


if __name__ == "__main__":
    corner_errors(sys.argv[1], sys.argv[2],
                  sys.argv[3] if len(sys.argv) > 3 else "valid",
                  int(sys.argv[4]) if len(sys.argv) > 4 else 960)
