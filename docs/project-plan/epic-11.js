window.EPIC_11 = {
  "id": "epic-11",
  "number": 11,
  "name": "Generalization — Any Board, Any Surface",
  "shortName": "Generalization",
  "description": "Everything so far was built and measured on one green vinyl mat on one wood floor. Make corners, refinement and orientation work on boards and backgrounds never seen before — and first check whether an existing system (chesscog) already does this better.",
  "status": "NOT_STARTED",
  "deploymentCards": [
    {
      "title": "Board-specific assumptions today",
      "items": [
        "Dark squares are green (fixed hue 35–95) — refinement mask",
        "Nothing outside the board is green — ring check, template margin",
        "A plain white border surrounds the grid — one-square shift check",
        "Printed a–h / 1–8 notation — planned 180° tie-breaker (5-3)",
        "One board, one floor, one light in all 49 training photos — pose model"
      ]
    },
    {
      "title": "Already general",
      "items": [
        "Homography + ECC fitting (any flat board)",
        "The board is exactly 8 × 8 squares",
        "a1 is a dark square on every correctly set up board",
        "corner_error.py as the yardstick for any method"
      ]
    }
  ],
  "tasks": [
    {
      "id": "11-1",
      "name": "Unseen-board test set",
      "details": "20–30 photos of 2+ other boards (wooden, black/white) on other surfaces and light, labelled like Dataset v1. Never used for training or tuning",
      "dependencies": [],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "Roboflow project", "url": "https://app.roboflow.com/victor-cao-student/board-detection-503v7" }],
      "fullDetails": "<h3>Why first</h3><p>Every number so far comes from one mat, so none of them says anything about generality. Without this set, changes in this epic can't be judged, and the system can look fine while only working on the green mat.</p><h3>Contents</h3><ul><li>Boards: at least one wooden (brown/tan, wooden frame instead of a white border) and one black/white</li><li>Surfaces: table, carpet, and one \"hard\" case (green table / patterned cloth)</li><li>Angles: include low shots like photo_49</li><li>Labels: 4 corners in a1 → h1 → h8 → a8 order, plus the true orientation</li></ul>"
    },
    {
      "id": "11-2",
      "name": "Bake-off: chesscog vs our model vs model + refinement",
      "details": "Run chesscog's board localisation on Dataset v1 and the unseen-board set; score everything with corner_error.py. Decide from the numbers whether to adopt, combine, or keep our approach",
      "dependencies": ["Unseen-board test set"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "chesscog (GitHub)", "url": "https://github.com/georg-wolflein/chesscog" }],
      "fullDetails": "<h3>Question</h3><p>An existing, board-agnostic system may already solve corners (and more). We never compared against it; the current design came from the project's history, not a comparison.</p><h3>Steps</h3><ol><li>Check chesscog's licence, install it in a separate venv, confirm it runs</li><li>Run its board localisation (lines + lattice fitting, no board-specific colours) on all photos</li><li>Score with <code>corner_error.py</code>: detection rate, median / worst error in squares, share within ¼ square</li><li>Also try chesscog corners → our refinement, and our model → chesscog's lattice step</li></ol><h3>Expected weak spots (unverified)</h3><ul><li>Very low camera angles: far rows are slivers, tall pieces hide lines</li><li>Straight-line clutter: wood-grain floors, tiles</li><li>Choosing which 8 × 8 of the lattice is the board (the same off-by-one problem as ours)</li></ul><h3>Decision</h3><ul><li>chesscog ≥ ours → adopt it for corners; keep our model only if it helps chesscog find the board</li><li>Ours better → keep, and take chesscog's lattice idea for 11-5</li></ul>"
    },
    {
      "id": "11-3",
      "name": "Decide: build on chesscog for the whole pipeline?",
      "details": "chesscog also does occupancy and piece classification and reports adapting to a new chess set from a few photos. If 11-2 goes well, Epics 7–8 could reuse it and this project focuses on low angles, naming and game recording",
      "dependencies": ["Bake-off: chesscog vs our model vs model + refinement"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "chesscog (GitHub)", "url": "https://github.com/georg-wolflein/chesscog" }],
      "fullDetails": "<h3>Inputs</h3><ul><li>Bake-off results (11-2)</li><li>chesscog's square-occupancy and piece accuracy on our photos (quick test on a few opening positions with known FEN)</li><li>Effort to adapt it to a new chess set</li></ul><h3>Outcome</h3><p>A short decision note in this plan: what is reused, what we build, and how Epics 4, 7 and 8 change.</p>"
    },
    {
      "id": "11-4",
      "name": "Refinement: two tones instead of green",
      "details": "Learn each photo's two square tones (first principal component of Lab colour inside the rough quad, or normalised brightness) and fit to that instead of a fixed green mask",
      "dependencies": ["Unseen-board test set"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Why it's a small change</h3><p>ECC ignores overall brightness and contrast, and both template parities are already tried, so it doesn't matter which tone counts as \"dark\". Only <code>green_mask</code> is replaced.</p><h3>Check</h3><ul><li>No regression on the green mat (median ≈ 0.13 squares)</li><li>Works on the unseen boards (11-1)</li></ul><p>Supersedes task 4-7.</p>"
    },
    {
      "id": "11-5",
      "name": "Shift check: \"pattern stops\" instead of \"border is empty\"",
      "details": "Require that the ring just outside the 8 × 8 does not continue the alternating pattern, rather than that it has no green. Works whatever surrounds the board",
      "dependencies": ["Refinement: two tones instead of green"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Test</h3><p>For each candidate grid, measure how strongly the ring squares alternate in step with the grid (tone difference between ring squares of the two parities). Inside the 8 × 8 it's strong; one square beyond, a wooden frame, white border, table or carpet doesn't alternate with the grid.</p><h3>Only assumption left</h3><p>The board is exactly 8 squares across.</p>"
    },
    {
      "id": "11-6",
      "name": "Colour-free fallback: fit the grid from its junctions",
      "details": "Find the X-junctions where four squares meet (grayscale, sub-pixel), fit the lattice with RANSAC, extend to the outer corners. Standard board-agnostic method; also handles the curled mat locally",
      "dependencies": ["Bake-off: chesscog vs our model vs model + refinement"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "OpenCV cornerSubPix", "url": "https://docs.opencv.org/4.x/dd/d1a/group__imgproc__feature.html" }],
      "fullDetails": "<h3>Steps</h3><ol><li>Saddle-point detector on grayscale inside the (expanded) rough quad</li><li><code>cv2.cornerSubPix</code> for sub-pixel positions</li><li>RANSAC homography to integer lattice coordinates; covered or false junctions become outliers</li><li>Choose the 8 × 8 extent with the \"pattern stops\" test (11-5)</li><li>Optional: local warps per quadrant for curled mats (overlaps task 4-5)</li></ol><p>May be unnecessary if chesscog wins 11-2 — its lattice step does much of this.</p>"
    },
    {
      "id": "11-7",
      "name": "Diverse training data for the corner model",
      "details": "More boards, surfaces and light: own photos of 2–3 boards, public sets (Roboflow Universe, ChessReD — confirm it has corner labels), and possibly rendered boards",
      "dependencies": ["Bake-off: chesscog vs our model vs model + refinement"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "Roboflow Universe", "url": "https://universe.roboflow.com/" }],
      "fullDetails": "<h3>Goal</h3><p>The model only has to land within ~1 square, but on boards it has never seen.</p><h3>Sources</h3><table><thead><tr><th>Source</th><th>Cost</th><th>Notes</th></tr></thead><tbody><tr><td>Own photos, 2–3 boards</td><td>low</td><td>most representative of real use</td></tr><tr><td>Roboflow Universe chessboard keypoint sets</td><td>low</td><td>check label format and corner definition</td></tr><tr><td>ChessReD (~10k real photos)</td><td>medium</td><td>believed to include corner annotations for part of it — verify</td></tr><tr><td>Synthetic renders</td><td>high</td><td>unlimited variety; chesscog trained on ~4.9k renders</td></tr></tbody></table><p>Only needed if the model stays in the pipeline after 11-2 / 11-3. Evaluate on 11-1 boards held out from training.</p>"
    },
    {
      "id": "11-8",
      "name": "Board-agnostic orientation",
      "details": "Keep \"a1 is dark\" (universal) using the two-tone signal; replace the notation tie-breaker with pieces / first-frame tracking for boards without printed coordinates",
      "dependencies": ["Refinement: two tones instead of green"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Changes to Epic 5</h3><ul><li>Diagonal check (5-1): use the darker tone, not green</li><li>Notation tie-breaker (5-3): optional, only when notation is detected</li><li>Pieces / first-frame tracking (5-4): the default tie-breaker</li></ul>"
    }
  ]
};
