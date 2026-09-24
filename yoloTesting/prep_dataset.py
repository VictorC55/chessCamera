"""Validate + fix a Roboflow keypoint export before training.

Usage: python prep_dataset.py path/to/roboflow-export-folder
Rewrites data.yaml with absolute paths and reports anything that would silently
ruin training. Does not modify images or labels.
"""
import sys
from collections import Counter
from pathlib import Path
import yaml

root = Path(sys.argv[1]).resolve()
yml = root / "data.yaml"
cfg = yaml.safe_load(yml.read_text())

NK = 4  # expected keypoints per board
problems, notes = [], []

# --- data.yaml sanity -------------------------------------------------------
kpt_shape = cfg.get("kpt_shape")
if kpt_shape != [NK, 3]:
    problems.append(f"kpt_shape is {kpt_shape}, expected [{NK}, 3] "
                    f"(3 = x,y,visibility; without it occlusion flags are lost)")
if len(cfg.get("names", [])) != 1:
    problems.append(f"expected 1 class (board), got {cfg.get('names')}")
if "flip_idx" in cfg:
    problems.append(f"flip_idx={cfg['flip_idx']} present -> enables mirror augmentation. "
                    f"A mirrored chessboard is invalid; removing it from data.yaml.")
    cfg.pop("flip_idx")

# --- label checks -----------------------------------------------------------
vis = Counter()
split_counts = {}
stems = {}
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

    for lp in labels:
        lines = [l for l in lp.read_text().splitlines() if l.strip()]
        if len(lines) != 1:
            problems.append(f"{split}/{lp.name}: {len(lines)} boards annotated, expected exactly 1")
            continue
        t = lines[0].split()
        if len(t) != 5 + NK * 3:
            problems.append(f"{split}/{lp.name}: {len(t)} values, expected {5 + NK * 3}")
            continue
        for i in range(NK):
            x, y, v = float(t[5 + i * 3]), float(t[6 + i * 3]), int(float(t[7 + i * 3]))
            vis[v] += 1
            if v != 0 and not (-0.05 <= x <= 1.05 and -0.05 <= y <= 1.05):
                notes.append(f"{split}/{lp.name}: keypoint {i} at ({x:.2f},{y:.2f}) is outside the frame")

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

for n in notes:
    print("note:", n)
if problems:
    print(f"\n{len(problems)} problem(s):")
    for p in problems:
        print("  -", p)
else:
    print("\nno problems found. data.yaml rewritten with absolute paths.")
