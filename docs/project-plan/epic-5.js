window.EPIC_5 = {
  "id": "epic-5",
  "number": 5,
  "name": "Board Orientation — Which Corner Is a1",
  "shortName": "Orientation",
  "description": "Name the 4 refined corners. Square colour narrows 4 orientations to 2 (a1/h8 are dark); a second cue picks between the remaining two, which are 180° apart.",
  "status": "IN_PROGRESS",
  "tasks": [
    {
      "id": "5-1",
      "name": "Square-colour diagonal check (prototype)",
      "details": "Flatten the board, measure green per square, compare the two diagonals: the greener one holds a1 and h8. Correct on 49 / 49 photos with hand-labelled corners",
      "dependencies": ["Epic 4"],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>Result (hand-labelled corners)</h3><table><thead><tr><th>Measure</th><th>Value</th></tr></thead><tbody><tr><td>Correct diagonal</td><td>49 / 49</td></tr><tr><td>Green on a1/h8 diagonal</td><td>~55%</td></tr><tr><td>Green on the other</td><td>2–12%</td></tr><tr><td>Smallest margin</td><td>0.41 (photo_17)</td></tr></tbody></table><p>Needs corners within ~⅓ square so the 8×8 lines up — which refinement now delivers on most photos.</p><p>Prototype: session scratchpad <code>color_check.py</code>; moves into the repo in 5-2.</p>"
    },
    {
      "id": "5-2",
      "name": "orientation.py module",
      "details": "<code>orient(img, corners) → corners reordered a1, h1, h8, a8 (+ confidence)</code>, using refined corners and the shared green mask from <code>refine_corners.py</code>",
      "dependencies": ["Square-colour diagonal check (prototype)"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Steps</h3><ol><li>Reuse <code>green_mask</code> and the warp from <code>refine_corners.py</code></li><li>Diagonal score as in 5-1 → two candidate orderings</li><li>Call the tie-breaker (5-3 / 5-4) to pick one</li><li>Return a confidence from both cues; below threshold → ask the user once per game (the camera usually doesn't move)</li></ol>"
    },
    {
      "id": "5-3",
      "name": "180° tie-breaker from the printed notation",
      "details": "The mat prints 1–8 and a–h on its border, readable from White's side. On the flattened board, classify the border strip beside each candidate rank 1",
      "dependencies": ["orientation.py module"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Approach</h3><ol><li>From the refined homography, extract the border strips (≈0.6 square wide) on all 4 sides, rotated to read upright</li><li>Tiny CNN or template matching: \"digits upright\" vs \"digits upside-down\"; every photo gives 4 rotations as training samples (49 × 4 = 196 before augmentation)</li><li>Evaluate with <code>labels_roboflow/</code> names (5-5)</li></ol><h3>Caveat</h3><p>Specific to boards with printed notation; 5-4 covers the rest.</p>"
    },
    {
      "id": "5-4",
      "name": "Tie-breaker from pieces",
      "details": "Openings: White's pieces are on ranks 1–2. Games: carry the orientation from the first frame, since the camera rarely moves",
      "dependencies": ["orientation.py module", "Epic 7"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Rules</h3><ul><li>Starting position: whichever side has the white pieces is rank 1</li><li>Mid-game single photo: majority of white pawns / king on one half is a weak hint</li><li>Video (Epic 9): decide once at the start, then track</li></ul><h3>Warning</h3><p>In some photos the pieces were set up sideways relative to the printed notation. Colour and notation are ground truth; pieces are only a fallback.</p>"
    },
    {
      "id": "5-5",
      "name": "Evaluate naming accuracy",
      "details": "Compare predicted a1/h1/h8/a8 with the Roboflow names in <code>labels_roboflow/</code> on all 49 photos, from refined model corners",
      "dependencies": ["orientation.py module"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Report</h3><ul><li>Diagonal correct (colour only)</li><li>Fully correct orientation (with tie-breaker)</li><li>Failures by cause: refinement failed / tie-breaker wrong</li></ul><p>Depends on fixing photo_09's mirrored label first (task 2-5).</p>"
    },
    {
      "id": "5-6",
      "name": "Optional: retrain a named-corner model for comparison",
      "details": "The first named-corner run had the nbs and stale-BN bugs, so it never got a fair test. Re-run with the fixed <code>train.py</code> on the a1…a8 labels and compare",
      "dependencies": ["Epic 3"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Steps</h3><ol><li>Export from Roboflow without running prep's reordering (or point at <code>labels_roboflow/</code>)</li><li>Train with the current <code>train.py</code></li><li>Score naming accuracy and position error</li></ol><p>If it names corners reliably, it could replace 5-2 … 5-4; if not, it confirms the two-step design.</p>"
    }
  ]
};
