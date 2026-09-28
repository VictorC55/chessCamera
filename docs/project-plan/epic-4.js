window.EPIC_4 = {
  "id": "epic-4",
  "number": 4,
  "name": "Grid Refinement (Computer Vision)",
  "shortName": "Grid refinement",
  "description": "Snap the model's rough corners onto the exact checkerboard by fitting a perfect 8×8 grid to the mat's green squares. No training. Brings the median error from 0.67 to 0.13 squares.",
  "status": "IN_PROGRESS",
  "deploymentCards": [
    {
      "title": "Validation (10 photos, model + refinement)",
      "items": [
        "Median <b>0.13</b> squares (~22 px), mean 0.21, worst 1.42",
        "85% of corners within ¼ square (model alone: 15%)",
        "photo_49 fails (model started 1.4–2.1 squares off) and is correctly flagged",
        "~2 s per photo on CPU including the model"
      ]
    },
    {
      "title": "Stress test (49 photos, labels shifted randomly)",
      "items": [
        "Start ≤ 1 square off: 44 / 49 photos fully within ½ square",
        "Start ≤ 1.5 squares: 35 / 49 (27 before the shift check)",
        "Start ≤ 2 squares: 36 / 49 (22 before the shift check)",
        "Unreliable flag: 0 false alarms in 147 trials; catches ~40% of failures"
      ]
    }
  ],
  "tasks": [
    {
      "id": "4-1",
      "name": "Checkerboard alignment (ECC)",
      "details": "Warp the green-pixel mask with the rough corners, align an ideal checkerboard template with <code>cv2.findTransformECC</code> (homography, coarse-to-fine blur 41 → 3), map the template corners back",
      "dependencies": ["Epic 3"],
      "status": "COMPLETED",
      "prLinks": [],
      "links": [{ "label": "OpenCV findTransformECC", "url": "https://docs.opencv.org/4.x/dc/d6b/group__video__track.html" }],
      "fullDetails": "<h3>How it works</h3><ol><li><b>Green mask:</b> HSV hue 35–95 and saturation &gt; 50. Dark squares are green; light squares, pieces, the white border and the floor are not.</li><li><b>Canvas:</b> warp the mask so the rough corners land on an 8×8 grid of 40 px squares with a 2-square margin.</li><li><b>Template:</b> ideal checkerboard, everything outside the 8×8 = 0, so border and floor count against a match. Both parities are tried because corner 0 can be a dark or light square.</li><li><b>Align:</b> ECC homography, blur 41 → 21 → 9 → 3. If the score is below 0.7, retry from starts rotated ±10° and ±20°.</li></ol><h3>Why not \"furthest dark point\"</h3><p>Only a1 and h8 are dark. The light corner squares (h1, a8) sit against the white border with no visible edge, so their position must come from the whole grid.</p>"
    },
    {
      "id": "4-2",
      "name": "One-square shift check + reliability flag",
      "details": "A checkerboard also matches one square off. Compare the fit with its 8 one-square shifts: 64 squares must alternate and the ring outside must be green-free (border / floor). Flag the result if not",
      "dependencies": ["Checkerboard alignment (ECC)"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>Scoring each shift</h3><ul><li><b>contrast</b> = |mean green on one parity − mean green on the other| over the 8×8</li><li><b>ring_green</b> = mean green over the 36 squares just outside</li><li>score = contrast − 2 × ring_green; best shift wins, then ECC re-polishes</li></ul><h3>Flag</h3><p><code>ok = contrast &gt; 0.3 and ring_green &lt; 0.1</code>. When not ok, keep the model's corners or skip the frame.</p><h3>Effect</h3><p>Photos recovered from starts up to 2 squares off went from 22 to 36 of 49.</p>"
    },
    {
      "id": "4-3",
      "name": "refine_corners.py module + wiring into corner_error.py",
      "details": "<code>refine(img, corners) → (corners, info)</code>; CLI draws model (red) vs refined (blue) on one photo",
      "dependencies": ["One-square shift check + reliability flag"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>Use</h3><pre>from refine_corners import refine\nfine, info = refine(img, rough_corners)   # same corner order\nif not info[\"ok\"]:\n    fine = rough_corners</pre><h3>CLI</h3><pre>.venv/bin/python refine_corners.py runs/corners-2/weights/last_recal.pt photo.jpg\n# writes photo_refined.jpg</pre>"
    },
    {
      "id": "4-4",
      "name": "Catch rotated / skewed failures",
      "details": "Most unflagged failures are rotated or sheared grids, not one-square shifts. Add checks that per-square colours match the checker pattern everywhere and that grid lines follow real green/white edges",
      "dependencies": ["refine_corners.py module + wiring into corner_error.py"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Ideas</h3><ul><li>Per-square agreement map: share of the 64 squares whose green fraction is on the correct side of 0.5 for its parity (pieces excluded by also requiring low black/white-piece pixels)</li><li>Edge support: sample the image gradient along each of the 18 grid lines; a skewed fit crosses edges instead of following them</li><li>Consistency: refine twice from slightly different starts; disagreement → flag</li></ul><h3>Measure</h3><p>Re-run the stress test and report flag recall (share of failures flagged) with zero false alarms.</p>"
    },
    {
      "id": "4-5",
      "name": "Handle the curled mat",
      "details": "A single homography can't follow a mat that curls at the edges (worst refined corners 0.25–0.4 squares are all near curls). Refine each corner locally after the global fit",
      "dependencies": ["refine_corners.py module + wiring into corner_error.py"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Options</h3><ol><li><b>Local corner fit:</b> around each corner, fit a small template (2×2 squares + border) with its own homography</li><li><b>Lattice points:</b> locate the 49 inner X-junctions with <code>cv2.cornerSubPix</code>, then fit a smooth warp (per-quadrant homographies or thin-plate spline) and extrapolate the outer corners</li></ol><p>Option 2 also gives per-square positions for piece mapping (Epic 8), where the mat's curvature matters most.</p>"
    },
    {
      "id": "4-6",
      "name": "Speed: under 0.5 s per photo",
      "details": "Now ~2 s with up to 10 ECC runs. Build the mask from a downscaled photo, try the likely parity first, stop early on a strong score",
      "dependencies": ["refine_corners.py module + wiring into corner_error.py"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Steps</h3><ul><li>Compute the green mask at ~1000 px long side (full 2480×3509 now)</li><li>Pick parity from the square-colour check (Epic 5) instead of trying both</li><li>Skip rotated starts when the first ECC score ≥ 0.8</li><li>Time it inside <code>corner_error.py</code> and report ms per photo</li></ul>"
    },
    {
      "id": "4-7",
      "name": "Colour-robust board mask",
      "details": "Hue thresholds are tuned to this green mat and the scanner's colours. Learn the dark-square colour per photo (e.g. 2-cluster k-means inside the rough quad) so other mats and lighting work",
      "dependencies": ["refine_corners.py module + wiring into corner_error.py"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Approach</h3><ol><li>Inside the rough board quad, cluster pixel colours (Lab) into squares-dark, squares-light, pieces</li><li>Use the dark-square cluster as the mask</li><li>Validate on Dataset v2 photos taken under different light (Epic 6)</li></ol>"
    }
  ]
};
