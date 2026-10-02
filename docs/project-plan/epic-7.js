window.EPIC_7 = {
  "id": "epic-7",
  "number": 7,
  "name": "Piece Detection",
  "shortName": "Pieces",
  "description": "Detect the 12 piece types (white/black × pawn, rook, knight, bishop, queen, king) on our board and camera angles, starting from the pretrained YOLOv8m model already used in detect.py.",
  "status": "NOT_STARTED",
  "tasks": [
    {
      "id": "7-1",
      "name": "Evaluate the pretrained piece model",
      "details": "Label pieces on the 10 validation photos and measure precision / recall per class for <code>KanisornPutta/chess-model-yolov8m</code>",
      "dependencies": [],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "Piece model (HF)", "url": "https://huggingface.co/KanisornPutta/chess-model-yolov8m" }],
      "fullDetails": "<h3>Why first</h3><p>If the pretrained model is already good on our photos, piece work shrinks to mapping (7-4). If not, the numbers show which classes and angles need data.</p><h3>Watch for</h3><ul><li>Low camera angles where pieces overlap</li><li>Bishop vs pawn and queen vs king confusion</li><li>Cream vs white pieces under warm light</li></ul>"
    },
    {
      "id": "7-2",
      "name": "Annotate pieces",
      "details": "Add a 12-class piece project in Roboflow over Dataset v1 + v2; pre-annotate with the pretrained model and correct",
      "dependencies": ["Evaluate the pretrained piece model", "Epic 6"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Notes</h3><ul><li>Board state is known for opening photos; generate their labels from the FEN plus the refined grid to save time</li><li>Box each piece's full silhouette; the base point used for mapping is derived later</li></ul>"
    },
    {
      "id": "7-3",
      "name": "Fine-tune the piece detector",
      "details": "YOLO detect fine-tune with the same small-dataset settings as Epic 3 (update every batch, BN recalibration, setup-based split)",
      "dependencies": ["Annotate pieces"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "links": [{ "label": "Ultralytics detect task", "url": "https://docs.ultralytics.com/tasks/detect/" }],
      "fullDetails": "<h3>Plan</h3><ul><li>Start from the pretrained YOLOv8m weights (or yolo11m)</li><li>Flips are fine here (pieces are symmetric enough), unlike corners</li><li>Report mAP50 per class and a confusion matrix</li></ul>"
    },
    {
      "id": "7-4",
      "name": "Piece → square mapping",
      "details": "Take each piece's base point (bottom-centre of the box, corrected for camera tilt), map it through the refined homography, assign the square",
      "dependencies": ["Epic 4", "Epic 5"],
      "status": "NOT_STARTED",
      "prLinks": [],
      "fullDetails": "<h3>Why not the box centre</h3><p>From a low angle, tall pieces lean away from the camera, so the box centre lands one or two ranks back. The base (where the piece meets the board) is what sits on the square.</p><h3>Steps</h3><ol><li>Base point = bottom-centre of the box, nudged up by a fraction of box height that depends on viewing angle</li><li>Map through the inverse homography to board coordinates (0–8, 0–8)</li><li>Resolve two pieces on one square by confidence and neighbouring empty squares</li></ol>"
    }
  ]
};
