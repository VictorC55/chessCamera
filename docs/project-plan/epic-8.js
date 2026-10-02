window.EPIC_8 = {
  "id": "epic-8",
  "number": 8,
  "name": "Board State → FEN",
  "shortName": "Board state",
  "description": "Combine corners, orientation and pieces into an 8×8 position, export FEN, and measure the whole pipeline end to end on photos with known positions.",
  "status": "NOT_STARTED",
  "tasks": [
    {
      "id": "8-1",
      "name": "Single-photo pipeline (photo_to_fen.py)",
      "details": "photo → corners (model) → refine → orient → pieces → squares → FEN, with a picture showing the grid and every assigned piece",
      "dependencies": ["Epic 5", "Epic 7"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "python-chess", "url": "https://python-chess.readthedocs.io/" }],
      "fullDetails": "<h3>Interface</h3><pre>.venv/bin/python photo_to_fen.py photo.jpg\n# rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1\n# writes photo_board.jpg</pre><h3>Output picture</h3><p>Refined grid, a1 marked, each piece's base point and assigned square.</p>"
    },
    {
      "id": "8-2",
      "name": "Legality and sanity checks",
      "details": "Use python-chess to flag impossible positions (two kings, pawns on rank 1/8, > 16 pieces per side) and low-confidence squares",
      "dependencies": ["Single-photo pipeline (photo_to_fen.py)"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Checks</h3><ul><li>Exactly one king per side</li><li>No pawns on the first or last rank</li><li>Piece counts possible given promotions</li><li>List the lowest-confidence squares for manual review</li></ul>"
    },
    {
      "id": "8-3",
      "name": "End-to-end benchmark",
      "details": "Record the true FEN for every test photo; report square accuracy (of 64) and whole-board accuracy",
      "dependencies": ["Single-photo pipeline (photo_to_fen.py)", "Epic 6"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Metrics</h3><ul><li>Square accuracy: share of the 64 squares right (empty counts)</li><li>Board accuracy: share of photos with every square right</li><li>Error breakdown: corner / orientation / detection / mapping</li></ul><h3>Target</h3><p>≥ 99% square accuracy on the test split before starting Epic 9.</p>"
    }
  ]
};
