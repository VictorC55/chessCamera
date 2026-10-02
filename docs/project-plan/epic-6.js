window.EPIC_6 = {
  "id": "epic-6",
  "number": 6,
  "name": "Dataset v2 — More and Harder Photos",
  "shortName": "Dataset v2",
  "description": "Grow from 49 scanned photos to ~200+ original camera photos covering the cases that fail today (steep angles, curled mat, hands, other lighting). The current model + refinement pre-annotates, so labelling is mostly correcting.",
  "status": "NOT_STARTED",
  "tasks": [
    {
      "id": "6-1",
      "name": "Capture plan v2",
      "details": "~200 photos over 20+ setups: all 4 sides, low / medium / overhead, curled mat edges, hands in frame, daylight / lamp / dim, 2–3 surfaces, and the actual phone position planned for games",
      "dependencies": [],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Coverage matrix</h3><table><thead><tr><th>Factor</th><th>Values</th></tr></thead><tbody><tr><td>Side</td><td>behind White, behind Black, a-file, h-file, diagonals</td></tr><tr><td>Height</td><td>low (like photo_49), medium, high, overhead</td></tr><tr><td>Mat</td><td>flat, curled edges</td></tr><tr><td>Occlusion</td><td>none, pieces on corners, hand reaching in</td></tr><tr><td>Light</td><td>daylight, warm lamp, dim</td></tr><tr><td>Surface</td><td>wood floor, table, carpet</td></tr></tbody></table><h3>Rules</h3><ul><li>Use the phone's original files, not CamScanner scans (no margins, watermark or colour boost)</li><li>Keep a shot log with setup IDs so splits stay by setup</li></ul>"
    },
    {
      "id": "6-2",
      "name": "Pre-annotate with model + refinement",
      "details": "Run model → refine → orient on new photos and upload the corners to Roboflow as predictions; the human fixes only the misses",
      "dependencies": ["Capture plan v2", "Epic 4", "Epic 5"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "Roboflow project", "url": "https://app.roboflow.com/victor-cao-student/board-detection-503v7" }],
      "fullDetails": "<h3>Steps</h3><ol><li>Script: for each photo, predict + refine; write YOLO-pose labels with a1, h1, h8, a8 order</li><li>Upload images with labels (Roboflow upload API or zip import)</li><li>Review in Roboflow; prioritise photos flagged by <code>info[\"ok\"] == False</code></li></ol><p>Expect most corners within ¼ square already, so review is fast.</p>"
    },
    {
      "id": "6-3",
      "name": "Held-out test set",
      "details": "Set aside ~15% of setups as a test split nobody tunes on; report final numbers only there",
      "dependencies": ["Capture plan v2"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Why</h3><p>Every decision so far was checked on the same 10 validation photos, which slowly overfits choices to them. A test split kept untouched gives an honest final number.</p><h3>Split</h3><p>By setup: ~70% train / 15% valid / 15% test.</p>"
    },
    {
      "id": "6-4",
      "name": "Winding / sanity check on every export",
      "details": "Add the counter-clockwise check to <code>prep_dataset.py</code> (before reordering) so mirrored labels like photo_07/09/24 are caught automatically",
      "dependencies": [],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Check</h3><p>Shoelace area of kp0 → kp1 → kp2 → kp3 must have the same sign in every label; report outliers as problems. Also warn if kp0/kp2 are not diagonals.</p>"
    },
    {
      "id": "6-5",
      "name": "Retrain and compare",
      "details": "Train on v2 with the Epic 3 settings; compare model and refined corner error with the v1 model on the new test split",
      "dependencies": ["Pre-annotate with model + refinement", "Held-out test set"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Success criteria</h3><ul><li>Model: every test corner within 1 square (refinement capture range)</li><li>Refined: ≥ 95% of corners within ¼ square</li><li>No flagged-but-accepted failures</li></ul>"
    }
  ]
};
