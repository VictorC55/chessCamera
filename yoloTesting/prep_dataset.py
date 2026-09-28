"""Validate + fix a Roboflow keypoint export before training.

Usage: python prep_dataset.py path/to/roboflow-export-folder
Rewrites data.yaml with absolute paths and reports anything that would silently
ruin training. Also rewrites the label files (originals are copied once to
<split>/labels_roboflow/):
  - corners are reordered by image position (leftmost corner first, then
    clockwise) instead of by chess square, so the model only has to find
    corners, not work out which one is a1 from 39 photos
  - the bounding box is rebuilt tightly around the 4 corners, because keypoint
    loss and scoring are both scaled by box area (loose box = lenient grading)
Safe to re-run: both fixes give the same result on already-fixed labels.
"""
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
import yaml

root = Path(sys.argv[1]).resolve()
yml = root / "data.yaml"
cfg = yaml.safe_load(yml.read_text())

NK = 4                  # expected keypoints per board
PAD = 0.05              # box padding around the corners, as a fraction of their extent
problems, notes = [], []


def order_corners(kpts):
    """Sort (x, y, v) corners clockwise from the leftmost one.

    Leftmost beats "top-left" (smallest x+y) here: in low-angle shots two corners
    often tie on x+y, while the leftmost wins by >=25% of the board width in every photo.
    """
    cx = sum(k[0] for k in kpts) / len(kpts)
    cy = sum(k[1] for k in kpts) / len(kpts)
    cw = sorted(kpts, key=lambda k: math.atan2(k[1] - cy, k[0] - cx))  # image y points down -> clockwise
    start = min(range(len(cw)), key=lambda i: cw[i][0])
    return cw[start:] + cw[:start]


def box_from_corners(kpts):
    """Tight xywh box around the labeled corners, padded and clipped to the image."""
    pts = [k for k in kpts if k[2] > 0]
    x0, x1 = min(k[0] for k in pts), max(k[0] for k in pts)
    y0, y1 = min(k[1] for k in pts), max(k[1] for k in pts)
    px, py = (x1 - x0) * PAD, (y1 - y0) * PAD
    x0, y0 = max(0.0, x0 - px), max(0.0, y0 - py)
    x1, y1 = min(1.0, x1 + px), min(1.0, y1 + py)
    return (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


# --- data.yaml sanity -------------------------------------------------------
kpt_shape = cfg.get("kpt_shape")
if kpt_shape != [NK, 3]:
    problems.append(f"kpt_shape is {kpt_shape}, expected [{NK}, 3] "
                    f"(3 = x,y,visibility; without it occlusion flags are lost)")
if len(cfg.get("names", [])) != 1:
    problems.append(f"expected 1 class (board), got {cfg.get('names')}")
if "flip_idx" in cfg:
    # a mirror turns the leftmost corner into the rightmost, whose index varies per photo,
    # so no fixed flip_idx keeps the order consistent; removing it disables mirroring
    notes.append(f"removed flip_idx={cfg.pop('flip_idx')} from data.yaml")
# a small sigma (e.g. 0.05) flattens the keypoint loss when corners start far off, so the
# model never learns them; keep Ultralytics' default and measure precision in pixels instead
cfg.pop("kpt_oks_sigmas", None)

# --- label checks + fixes ---------------------------------------------------
vis = Counter()
split_counts = {}
stems = {}
area_ratios = []
for split, key in (("train", "train"), ("valid", "val"), ("test", "test")):
    d = root / split
    if not d.exists():
        continue
    labels = sorted((d / "labels").glob("*.txt"))
    images = [p for p in (d / "images").iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    split_counts[split] = (len(images), len(labels))
    stems[split] = {p.stem for p in labels}
    if len(images) != len(labels):
        problems.append(f"{split}: {len(images)} images but {len(labels)} label files")

    backup = d / "labels_roboflow"
    if not backup.exists():
        shutil.copytree(d / "labels", backup)

    for lp in labels:
        lines = [l for l in lp.read_text().splitlines() if l.strip()]
        if len(lines) != 1:
            problems.append(f"{split}/{lp.name}: {len(lines)} boards annotated, expected exactly 1")
            continue
        t = lines[0].split()
        if len(t) != 5 + NK * 3:
            problems.append(f"{split}/{lp.name}: {len(t)} values, expected {5 + NK * 3}")
            continue
        kpts = [(float(t[5 + i * 3]), float(t[6 + i * 3]), int(float(t[7 + i * 3]))) for i in range(NK)]
        for i, (x, y, v) in enumerate(kpts):
            vis[v] += 1
            if v != 0 and not (-0.05 <= x <= 1.05 and -0.05 <= y <= 1.05):
                notes.append(f"{split}/{lp.name}: keypoint {i} at ({x:.2f},{y:.2f}) is outside the frame")
        if sum(k[2] > 0 for k in kpts) < 2:
            problems.append(f"{split}/{lp.name}: fewer than 2 labeled corners, can't rebuild its box")
            continue

        old_area = float(t[3]) * float(t[4])
        kpts = order_corners(kpts)
        cx, cy, w, h = box_from_corners(kpts)
        area_ratios.append(old_area / (w * h))
        kp_str = " ".join(f"{x:.6f} {y:.6f} {v}" for x, y, v in kpts)
        lp.write_text(f"{t[0]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f} {kp_str}\n")

    # Ultralytics caches parsed labels; drop it so the rewritten ones are read
    for c in d.glob("*.cache"):
        c.unlink()

# leakage check: same basename in two splits usually means a duplicate shot
for a in stems:
    for b in stems:
        if a < b and (dup := stems[a] & stems[b]):
            problems.append(f"{len(dup)} filenames appear in both {a} and {b}")

# --- write corrected yaml ---------------------------------------------------
cfg["path"] = str(root)
for split, key in (("train", "train"), ("valid", "val"), ("test", "test")):
    if (root / split).exists():
        cfg[key] = f"{split}/images"
    else:
        cfg.pop(key, None)  # Roboflow lists test even when the split is empty
yml.write_text(yaml.safe_dump(cfg, sort_keys=False))

# --- report -----------------------------------------------------------------
print(f"dataset: {root}")
for s, (i, l) in split_counts.items():
    print(f"  {s:6s} {i:4d} images / {l:4d} labels")
total = sum(vis.values())
print(f"keypoint visibility: v0(unlabeled)={vis[0]} v1(occluded)={vis[1]} v2(visible)={vis[2]}")
if total and vis[0] / total > 0.02:
    print(f"  !! {vis[0]/total:.0%} of keypoints are v=0 and will be SKIPPED by the loss.")
    print("     Occluded corners should be v=1 at their estimated position, not v=0.")
if total and vis[1] / total < 0.10:
    print(f"  note: only {vis[1]/total:.0%} occluded keypoints; your plan targets ~25% of images.")
if area_ratios:
    area_ratios.sort()
    print(f"boxes rebuilt from corners: old box was {area_ratios[len(area_ratios) // 2]:.2f}x "
          f"the new area (median), max {area_ratios[-1]:.2f}x")
print("corner order: 0=leftmost corner in the image, then 1-3 clockwise")

for n in notes:
    print("note:", n)
if problems:
    print(f"\n{len(problems)} problem(s):")
    for p in problems:
        print("  -", p)
else:
    print("\nno problems found. labels and data.yaml rewritten.")
