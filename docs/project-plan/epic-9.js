window.EPIC_9 = {
  "id": "epic-9",
  "number": 9,
  "name": "Game Recording (Moves → PGN)",
  "shortName": "Game recording",
  "description": "Record a whole game from a fixed phone: detect when a move has been played, work out which legal move explains the change, and export PGN.",
  "status": "NOT_STARTED",
  "tasks": [
    {
      "id": "9-1",
      "name": "Capture and stable-frame detection",
      "details": "Phone on a stand filming the board; keep frames where nothing moves and no hand is over the board",
      "dependencies": ["Epic 8"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Approach</h3><ul><li>Frame differencing inside the board quad; a frame is stable after ~0.5 s with no change</li><li>Hand detection: skin-colour or a person/hand detector over the board region</li><li>Corners and orientation computed once at the start and re-checked occasionally (camera bumps)</li></ul>"
    },
    {
      "id": "9-2",
      "name": "Move inference from consecutive positions",
      "details": "For each stable frame, choose the legal move whose resulting position best matches the detected squares (handles castling, captures, en passant, promotion)",
      "dependencies": ["Capture and stable-frame detection"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "python-chess", "url": "https://python-chess.readthedocs.io/" }],
      "fullDetails": "<h3>Why this is robust</h3><p>Instead of trusting every square, score each legal move (~30 options) against the observed changes. A few misread squares don't matter if one move clearly explains the rest.</p><h3>Edge cases</h3><ul><li>No move matches well → keep waiting / flag</li><li>Two moves in one gap (missed frame) → search depth 2</li><li>Promotion piece from the detector</li></ul>"
    },
    {
      "id": "9-3",
      "name": "PGN export and review",
      "details": "Write PGN with timestamps; a simple review page shows each move beside its frame so errors can be fixed",
      "dependencies": ["Move inference from consecutive positions"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Deliverables</h3><ul><li><code>game.pgn</code> with a <code>%clk</code>-style timestamp per move</li><li>HTML review: frame thumbnail, detected position, chosen move; click to override</li></ul>"
    },
    {
      "id": "9-4",
      "name": "Live-game trial",
      "details": "Record 3 real games end to end; target: no manual corrections needed",
      "dependencies": ["PGN export and review"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Record per game</h3><ul><li>Moves recorded correctly / total</li><li>Manual corrections needed</li><li>Failure causes (occlusion, lighting, camera moved)</li></ul>"
    }
  ]
};
