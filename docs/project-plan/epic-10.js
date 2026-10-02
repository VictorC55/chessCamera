window.EPIC_10 = {
  "id": "epic-10",
  "number": 10,
  "name": "Docs & Housekeeping",
  "shortName": "Docs",
  "description": "Keep the README, this plan and the repository tidy as the pipeline changes.",
  "status": "IN_PROGRESS",
  "tasks": [
    {
      "id": "10-1",
      "name": "Project plan (this page)",
      "details": "<code>docs/project-plan/</code>: epics, tasks, results and links, same format as the Chess Opus plan",
      "dependencies": [],
      "status": "COMPLETED",
      "prLinks": [],
      "fullDetails": "<h3>View</h3><pre>open docs/project-plan/index.html\n# or\ncd docs/project-plan && python3 -m http.server 8000   # http://localhost:8000</pre><h3>Edit</h3><ul><li>One file per epic: <code>epic-N.js</code> (tasks, statuses, links)</li><li>Title, date and key decisions: <code>metadata.js</code></li><li>Statuses: <code>COMPLETED</code>, <code>IN_PROGRESS</code>, <code>REQUIRE_HUMAN_REVIEW</code>, <code>NOT_STARTED</code></li><li><code>prLinks</code> accepts PR or commit URLs; <code>links</code> takes <code>{label, url}</code> for docs and resources</li></ul>"
    },
    {
      "id": "10-2",
      "name": "Update the README",
      "details": "Keypoint order (positional for the model, a1 → h1 → h8 → a8 in Roboflow), new scripts, training settings, how to read corner error",
      "dependencies": [],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "README.md", "url": "https://github.com/VictorC55/chessCamera/blob/main/README.md" }],
      "fullDetails": "<h3>Out of date now</h3><ul><li>Says the pose model uses a1, h1, a8, h8; ours uses positional order and the Roboflow names are a1, h1, h8, a8</li><li>Layout table lacks <code>corner_error.py</code>, <code>refine_corners.py</code>, <code>docs/</code></li><li>Usage should point to <code>last_recal.pt</code> and <code>corner_preds/zoom_sheet.jpg</code></li></ul>"
    },
    {
      "id": "10-3",
      "name": "Clean up runs and caches",
      "details": "Delete the broken runs (<code>runs/corners</code>, <code>runs/pose</code>), drop committed <code>labels.cache</code> files and ignore them",
      "dependencies": [],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Steps</h3><ul><li><code>runs/corners</code>: the stopped sigma-0.05 run; <code>runs/pose</code>: the first MPS run; both unusable</li><li><code>git rm --cached</code> the <code>labels.cache</code> files under <code>pictures/</code> and add <code>*.cache</code> to <code>.gitignore</code></li></ul>"
    }
  ]
};
