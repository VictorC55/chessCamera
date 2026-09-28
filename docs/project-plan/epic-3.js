window.EPIC_3 = {
  "id": "epic-3",
  "number": 3,
  "name": "Corner Model (YOLO11s-pose)",
  "shortName": "Corner model",
  "description": "Fine-tune YOLO11s-pose to find the 4 board corners. Training now works reliably; the model is ~0.67 squares off (median) and its job is to land inside the refinement's ~1-square capture range (Epic 4).",
  "status": "IN_PROGRESS",
  "deploymentCards": [
    {
      "title": "Current result (runs/corners-2, 60 epochs, 960 px, CPU)",
      "items": [
        "Board found in 10 / 10 validation photos",
        "Corner error: median <b>0.67</b>, mean 0.73, worst 2.14 squares",
        "15% of corners within ¼ square (goal: 100%, reached by adding Epic 4)",
        "Pose mAP50-95 0.955 (lenient; judge by corner error instead)"
      ]
    },
    {
      "title": "How to run",
      "items": [
        "<code>cd yoloTesting</code>",
        "<code>.venv/bin/python prep_dataset.py ../pictures/50testEdited</code>",
        "<code>.venv/bin/python train.py ../pictures/50testEdited</code> (~42 min on CPU)",
        "Use <code>runs/corners*/weights/last_recal.pt</code>; pictures in <code>runs/corners*/corner_preds/</code>"
      ]
    }
  ],
  "tasks": [
    {
      "id": "3-1",
      "name": "Dataset validator (prep_dataset.py)",
      "details": "Checks kpt_shape, class count, label format, visibility, split leakage; writes absolute paths into <code>data.yaml</code>",
      "dependencies": ["Epic 2"],
      "status": "COMPLETED",
      "prLinks": ["https://github.com/VictorC55/chessCamera/commit/7181d29d458a0131c452ee5f86e40655c7593fb7"],
      "links": [{ "label": "prep_dataset.py", "url": "https://github.com/VictorC55/chessCamera/blob/main/yoloTesting/prep_dataset.py" }],
      "fullDetails": "<h3>Checks</h3><ul><li><code>kpt_shape == [4, 3]</code> (visibility kept)</li><li>exactly 1 board and 17 values per label</li><li>share of v=0 keypoints (skipped by the loss) and of occluded ones</li><li>same file name in two splits</li><li>Roboflow's <code>flip_idx</code> and stale <code>test:</code> entries removed</li></ul><h3>Run</h3><pre>.venv/bin/python prep_dataset.py ../pictures/50testEdited</pre><p>Should end with <code>no problems found</code> and <code>corner order: 0=leftmost corner in the image, then 1-3 clockwise</code>. Safe to re-run.</p>"
    },
    {
      "id": "3-2",
      "name": "Positional corner order + boxes from corners",
      "details": "Labels rewritten as leftmost corner first, then clockwise; box rebuilt tightly around the corners (+5%); originals copied to <code>labels_roboflow/</code>",
      "dependencies": ["Dataset validator (prep_dataset.py)"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>Why</h3><p>With named corners, keypoint 0 appeared bottom-right in 20 photos, bottom-left in 9, top-right in 8 and top-left in 12. The model had to infer the board's facing from 39 photos and hedged between positions.</p><h3>Why \"leftmost\" and not \"top-left\"</h3><p>\"Smallest x+y\" nearly tied in low-angle shots (margin 1.5% of board width on photo_25). \"Leftmost\" wins by at least 25% of the board width in all 49 photos, so small rotations can't flip the numbering.</p><h3>Consequences</h3><ul><li>Horizontal flips must stay off: a mirror makes the rightmost corner leftmost, and its index varies per photo, so no fixed <code>flip_idx</code> works.</li><li>Naming the corners moves to Epic 5.</li></ul><h3>Not yet committed</h3><p>Part of task 3-7.</p>"
    },
    {
      "id": "3-3",
      "name": "Diagnose the zero-mAP collapse",
      "details": "Validation read 0 after epoch 1 on MPS and CPU alike. Root causes: flattened keypoint loss, ~0.6 weight updates per epoch, stale BatchNorm statistics",
      "dependencies": [],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>Symptoms</h3><ul><li>Box mAP50 0.73–0.95 after epoch 1, then 0 for 20+ epochs</li><li>Validation classification loss up to 10<sup>9</sup> while training loss stayed ~2</li><li>Model output the same confident box for unrelated photos</li></ul><h3>What it was not</h3><p>Apple's MPS backend (CPU did the same), the data, the learning rate, NaNs, the class bias, or rectangular validation batches — each tested and ruled out.</p><h3>Causes</h3><table><thead><tr><th>Cause</th><th>Evidence</th><th>Fix</th></tr></thead><tbody><tr><td>Keypoint sigma 0.05 flattened the loss</td><td>pose loss stuck at 11 / 12</td><td>default sigma (loss then fell 4.3 → 0.3)</td></tr><tr><td><code>nbs=64</code>: one update per 8 batches</td><td>identical val scores on consecutive epochs</td><td><code>nbs=8</code></td></tr><tr><td>BatchNorm running stats lag the weights</td><td>deep layers off by 75–122 std; batch-stat mode predicted correctly</td><td>recalibrate after training</td></tr></tbody></table>"
    },
    {
      "id": "3-4",
      "name": "Training fixes in train.py",
      "details": "<code>nbs=8</code>, <code>patience=0</code>, <code>cache=\"ram\"</code>, CUDA-else-CPU device, absolute <code>runs/</code> path, 60 epochs default",
      "dependencies": ["Diagnose the zero-mAP collapse"],
      "status": "COMPLETED",
      "prLinks": [],
      "links": [
        { "label": "Ultralytics train settings", "url": "https://docs.ultralytics.com/modes/train/" },
        { "label": "Ultralytics pose task", "url": "https://docs.ultralytics.com/tasks/pose/" }
      ],
      "fullDetails": "<h3>Settings</h3><table><thead><tr><th>Setting</th><th>Value</th><th>Why</th></tr></thead><tbody><tr><td>imgsz</td><td>960</td><td>corners need detail; ~11 model pixels = ¼ square</td></tr><tr><td>nbs</td><td>8</td><td>update every batch (5 per epoch)</td></tr><tr><td>patience</td><td>0</td><td>early stopping would fire during the stale-BN zeros</td></tr><tr><td>mosaic</td><td>0.3</td><td>heavy mosaic crops corners out</td></tr><tr><td>fliplr / flipud</td><td>0</td><td>would scramble positional order</td></tr><tr><td>degrees</td><td>10</td><td>larger rotations change which corner is leftmost</td></tr><tr><td>cache</td><td>ram</td><td>2480×3509 decode is slow</td></tr></tbody></table><h3>Expected log</h3><p>Validation mAP ~0 for the first ~15–20 epochs, then recovers. Ignore it; the final printed numbers are after recalibration.</p>"
    },
    {
      "id": "3-5",
      "name": "BatchNorm recalibration → last_recal.pt",
      "details": "After training, recompute BN running statistics from the un-augmented training photos; same weights went from pose mAP50-95 0.17 to 0.98 in testing",
      "dependencies": ["Training fixes in train.py"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>How</h3><ol><li>Load <code>last.pt</code> (EMA weights)</li><li>Reset every BatchNorm's running mean/var, momentum = cumulative</li><li>Forward all training photos (letterboxed, no augmentation) in train mode without gradients</li><li>Save <code>weights/last_recal.pt</code> and validate it</li></ol><h3>Why last and not best</h3><p><code>best.pt</code> is chosen by the broken in-training validation scores.</p>"
    },
    {
      "id": "3-6",
      "name": "Corner-error metric and pictures (corner_error.py)",
      "details": "Error per corner in board squares, model vs refined, full-size annotated photos and a <code>zoom_sheet.jpg</code> of every corner",
      "dependencies": ["BatchNorm recalibration → last_recal.pt"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>Run</h3><pre>.venv/bin/python corner_error.py runs/corners-2/weights/last_recal.pt ../pictures/50testEdited [split] [imgsz]</pre><h3>Output</h3><ul><li>Per photo: model errors → refined errors, and a flag if the refinement looks unreliable</li><li><code>runs/…/corner_preds/&lt;photo&gt;.jpg</code>: labels green, model red, refined blue</li><li><code>runs/…/corner_preds/zoom_sheet.jpg</code>: every corner, 3 squares across, captioned <code>model -&gt; refined</code></li></ul><h3>Scale</h3><p>1 square ≈ 169 px in the full photo (≈ 46 px at 960). Goal ¼ square ≈ 42 px.</p><p><code>train.py</code> calls it automatically at the end of every run.</p>"
    },
    {
      "id": "3-7",
      "name": "Commit and push the training work",
      "details": "Branch + PR for <code>prep_dataset.py</code>, <code>train.py</code>, <code>corner_error.py</code>, <code>refine_corners.py</code> and this plan",
      "dependencies": ["Corner-error metric and pictures (corner_error.py)"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Steps</h3><ol><li><code>git checkout -b corner-model-training</code></li><li>Commit the 4 scripts and <code>docs/project-plan/</code>; leave the label rewrites in <code>pictures/50testAnnotated</code> out unless they're wanted (prep rewrote them in place)</li><li>Push and open a PR; add its link to tasks 3-2 … 3-6 and Epic 4</li></ol>"
    },
    {
      "id": "3-8",
      "name": "Get every photo inside the refinement's capture range",
      "details": "Goal: model error under 1 square on 100% of corners (now worst 2.14). Try 100 epochs, imgsz 1280, yolo11m-pose, freezing the backbone; compare with corner_error.py",
      "dependencies": ["Commit and push the training work"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Why this target</h3><p>Refinement succeeds on 90% of photos when every corner starts within 1 square, and 73% when starting up to 2 squares off. Precision below a square matters less than never being far off.</p><h3>Experiments (one change each)</h3><table><thead><tr><th>#</th><th>Change</th><th>Cost</th></tr></thead><tbody><tr><td>A</td><td>epochs 100</td><td>~70 min CPU</td></tr><tr><td>B</td><td>imgsz 1280, batch 4, nbs 4</td><td>~2× per epoch</td></tr><tr><td>C</td><td><code>freeze=10</code> (backbone)</td><td>faster</td></tr><tr><td>D</td><td>yolo11m-pose</td><td>~2× per epoch; use Colab</td></tr></tbody></table><p>Report median, worst and share within 1 square for model and refined. Keep the winner as the new default. More data (Epic 6) is likely the bigger lever.</p>"
    },
    {
      "id": "3-9",
      "name": "Re-test Apple GPU (MPS)",
      "details": "MPS was blamed before the BN issue was found; a 20-epoch comparison with CPU decides whether <code>train.py</code> can use it (speed-up unmeasured)",
      "dependencies": ["Commit and push the training work"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Steps</h3><ol><li>Run 20 epochs on <code>device=\"mps\"</code> and on CPU with the same seed</li><li>Compare training losses and the recalibrated corner error</li><li>If they match, prefer MPS when available in <code>train.py</code></li></ol>"
    },
    {
      "id": "3-10",
      "name": "Colab notebook",
      "details": "Saved notebook in <code>yoloTesting/</code> that mounts Drive, installs, preps, trains and shows the zoom sheet",
      "dependencies": ["Commit and push the training work"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "Google Colab", "url": "https://colab.research.google.com/" }],
      "fullDetails": "<h3>Cells</h3><ol><li>Mount Drive, <code>%cd</code> to the project</li><li><code>pip install -r requirements.txt</code></li><li><code>prep_dataset.py</code> on the chosen export</li><li><code>train.py</code></li><li>Display <code>corner_preds/zoom_sheet.jpg</code> inline</li></ol>"
    }
  ]
};
