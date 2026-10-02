window.EPIC_2 = {
  "id": "epic-2",
  "number": 2,
  "name": "Dataset v1 — Capture & Annotation",
  "shortName": "Dataset v1",
  "description": "49 photos of 10 board setups from 5 angles each, annotated in Roboflow with the 4 board corners and a visibility flag. Enough to prove the pipeline; too small for a final model (see Epic 6).",
  "status": "REQUIRE_HUMAN_REVIEW",
  "tasks": [
    {
      "id": "2-1",
      "name": "Capture plan",
      "details": "10 setups (openings, midgames, occluded corners, sparse) × 5 shots with the camera near a different corner and height each time",
      "dependencies": [],
      "status": "COMPLETED",
      "prLinks": ["https://github.com/VictorC55/chessCamera/commit/7181d29d458a0131c452ee5f86e40655c7593fb7"],
      "links": [{ "label": "plan.txt", "url": "https://github.com/VictorC55/chessCamera/blob/main/plan.txt" }],
      "fullDetails": "<h3>What was delivered</h3><p><code>plan.txt</code>: a shot list that rotates the camera around all four corners at low, medium and high angles, so every corner name appears in every image position.</p><table><thead><tr><th>Setups</th><th>Content</th></tr></thead><tbody><tr><td>1–2</td><td>Starting position</td></tr><tr><td>3–6, 9</td><td>Midgames A–E</td></tr><tr><td>7–8</td><td>Corners occluded by pieces</td></tr><tr><td>10</td><td>Sparse (6–8 pieces)</td></tr></tbody></table><h3>Lesson</h3><p>Rotating the camera is what made named-corner regression hard (Epic 3). It is still the right data: the pipeline has to work from any side.</p>"
    },
    {
      "id": "2-2",
      "name": "Shoot and extract 49 photos",
      "details": "Photographed, scanned to PDF with CamScanner, extracted with <code>pdfToJPGs.py</code>",
      "dependencies": ["Capture plan"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>What was delivered</h3><p>49 JPGs (one planned shot is missing) at 2480×3509.</p><h3>Known quirks</h3><ul><li>Portrait scan pages: white bottom margin and a CamScanner watermark</li><li>Scanner colour enhancement (very saturated floor)</li><li>The vinyl mat is rolled for storage, so its edges curl up; this limits how exactly a flat grid can fit (Epic 4)</li></ul>"
    },
    {
      "id": "2-3",
      "name": "Roboflow keypoint annotation",
      "details": "One <code>chessboard</code> class, 4 keypoints stored cyclically a1 → h1 → h8 → a8, visibility 2 = visible, 1 = hidden but estimated",
      "dependencies": ["Shoot and extract 49 photos"],
      "status": "COMPLETED",
      "prLinks": [],
      "links": [{ "label": "Roboflow project", "url": "https://app.roboflow.com/victor-cao-student/board-detection-503v7" }],
      "fullDetails": "<h3>What was delivered</h3><p>Every photo labelled with the 4 outer corners of the 8×8 grid (not the mat's corners).</p><table><thead><tr><th>Measure</th><th>Value</th></tr></thead><tbody><tr><td>Keypoints visible (v=2)</td><td>162</td></tr><tr><td>Hidden but estimated (v=1)</td><td>34 (17%)</td></tr><tr><td>Unlabelled (v=0)</td><td>0</td></tr></tbody></table><h3>Keypoint order</h3><p>Roboflow stores the corners going <em>around</em> the board: a1, h1, h8, a8 (kp0/kp2 and kp1/kp3 are diagonals in all 49 photos). The README still says a1, h1, a8, h8, which is the Hugging Face model's order (task 10-2).</p>"
    },
    {
      "id": "2-4",
      "name": "Split by setup",
      "details": "39 train / 10 valid; valid = two whole setups (photos 35–39 and 45–49), no test split",
      "dependencies": ["Roboflow keypoint annotation"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>Why</h3><p>A random split puts other angles of the same board in validation, which inflates every score. Whole setups keep validation honest.</p><h3>Checked by</h3><p><code>prep_dataset.py</code> reports any file name that appears in two splits.</p>"
    },
    {
      "id": "2-5",
      "name": "Fix mirrored labels and loose boxes (exports v2, v3)",
      "details": "photo_07, 09, 24 had h1 and a8 swapped; boxes were ~2× the corner area. Fixed in Roboflow; <b>photo_09 was still mirrored in the v2 export — confirm v3</b>",
      "dependencies": ["Roboflow keypoint annotation"],
      "status": "REQUIRE_HUMAN_REVIEW",
      "prLinks": [],
      "links": [{ "label": "Roboflow project", "url": "https://app.roboflow.com/victor-cao-student/board-detection-503v7" }],
      "fullDetails": "<h3>What happened</h3><ul><li>A winding check (do the 4 corners go around counter-clockwise?) found photo_07, photo_09 and photo_24 going the other way: h1 and a8 swapped, a mirrored board no camera can produce.</li><li>The square-colour check could not see it, because swapping h1/a8 keeps the dark a1/h8 diagonal in place.</li><li>Boxes: median 2.0× the corner area (up to 3.7×), which made keypoint scoring lenient.</li></ul><h3>Status</h3><ul><li>Boxes: no longer matter; <code>prep_dataset.py</code> rebuilds them from the corners.</li><li>Mirroring: v2 (<code>Edited50</code>) still had photo_09 mirrored. This only matters for the naming step (Epic 5), not the corner model.</li></ul><h3>To do</h3><ol><li>Open photo_09 in Roboflow and swap its h1/a8 points if needed.</li><li>Re-run the winding check on the export (one-off script, or add it to <code>prep_dataset.py</code> before reordering).</li></ol>"
    },
    {
      "id": "2-6",
      "name": "Commit the annotated set",
      "details": "<code>pictures/50testAnnotated</code> (Roboflow v1 export) committed for reproducibility",
      "dependencies": ["Split by setup"],
      "status": "COMPLETED",
      "prLinks": ["https://github.com/VictorC55/chessCamera/commit/593a845a54601dc02a12ee91c6aedde07361b9ce"],
      "fullDetails": "<h3>Notes</h3><ul><li>The commit includes Ultralytics <code>labels.cache</code> files, which are regenerated automatically; they can be removed and ignored (task 10-3).</li><li>Later exports (<code>Edited50</code>, <code>50testEdited</code>) live only in Drive.</li></ul>"
    }
  ]
};
