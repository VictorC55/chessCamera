window.PROJECT_META = {
  "meta": {
    "title": "chessCamera — Project Plan",
    "lastUpdated": "2026-09-27"
  },
  "overview": {
    "totalEpics": 10,
    "completed": 1,
    "inProgress": 4,
    "needsReview": 1,
    "notStarted": 4
  },
  "keyDecisions": [
    {
      "label": "Goal",
      "text": "Turn photos (later video) of a physical game into a board state (FEN) and eventually a full game record (PGN). Pipeline: find board corners → snap them to the exact grid → decide which corner is a1 → detect pieces → map pieces to squares."
    },
    {
      "label": "Corners are found by position, named later",
      "text": "The pose model numbers corners by image position (0 = leftmost, then clockwise) instead of a1/h1/h8/a8. Naming them needs to know which way the board faces, which 39 photos can't teach a regressor. Naming is a separate step (Epic 5). The original named labels are kept in <code>labels_roboflow/</code>."
    },
    {
      "label": "Training settings for a tiny dataset",
      "text": "<code>nbs=8</code> (update every batch; the default 64 gives ~0.6 updates per epoch on 39 photos), <code>patience=0</code> (val reads ~0 for ~15 epochs), default keypoint sigma (0.05 flattened the loss and stopped corner learning), and BatchNorm recalibration after training (<code>last_recal.pt</code>). Use <code>last_recal.pt</code>, never <code>best.pt</code>."
    },
    {
      "label": "Judge corners in board squares, not mAP",
      "text": "Pose mAP50-95 reads ~0.95 while corners are a full square off. <code>corner_error.py</code> reports the error in squares (1 square ≈ 169 px in the 2480×3509 photos). Target: under 0.25 squares for every corner."
    },
    {
      "label": "Model + CV, not model alone",
      "text": "The model gets within about a square; <code>refine_corners.py</code> fits a perfect checkerboard to the green squares (OpenCV ECC plus a one-square shift check). Median error drops from 0.67 to 0.13 squares. Model work should aim at getting every photo inside the refinement's ~1-square capture range, not at sub-pixel precision."
    },
    {
      "label": "Data lives in Drive, code in git",
      "text": "Weights, <code>runs/</code>, source PDFs and large photo sets stay out of git (<code>.gitignore</code>). The first annotated set (<code>pictures/50testAnnotated</code>) is committed for reproducibility. Datasets are split by board setup, never randomly, so near-duplicate angles can't leak into validation."
    },
    {
      "label": "Environment",
      "text": "Local training uses <code>yoloTesting/.venv</code> (Python 3.14, torch 2.14, ultralytics 8.4.155) on CPU, about 42 s/epoch at 960 px. Colab (T4) is the fast option. One <code>requirements.txt</code> at the repo root covers the whole project and deliberately leaves torch unpinned."
    },
    {
      "label": "Viewing this plan",
      "text": "Open <code>docs/project-plan/index.html</code> directly in a browser, or run <code>python3 -m http.server 8000</code> in <code>docs/project-plan</code> and visit <a href=\"http://localhost:8000\" target=\"_blank\" rel=\"noopener\">http://localhost:8000</a>. Edit an epic by changing its <code>epic-N.js</code> file."
    }
  ]
};
