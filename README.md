# chessCamera

Recovering chess board state from a photograph: locate the board's four corner
squares, detect the pieces, and map each piece to a square.

## Pipeline

1. **Board corners** — a YOLO11s-pose model treats the board as a single class
   with 4 keypoints (`a1`, `h1`, `a8`, `h8`). Keypoints carry a visibility flag
   so corners hidden behind pieces or hands stay usable.
2. **Pieces** — a YOLOv8m detector over 12 classes (white/black x pawn, rook,
   knight, bishop, queen, king).
3. The corner quad gives the homography needed to turn piece boxes into squares.

## Layout

| Path | Purpose |
| --- | --- |
| `yoloTesting/detect.py` | Run both pretrained models on an image, draw the corner quad and piece boxes, write `out.png` |
| `yoloTesting/prep_dataset.py` | Validate a Roboflow keypoint export before training and rewrite `data.yaml` with absolute paths |
| `yoloTesting/train.py` | Fine-tune a YOLO pose model on the 4-corner dataset |
| `helpers/pdfToJPGs.py` | Extract photos from a scanned PDF into `pictures/50test/` |
| `plan.txt` | Capture plan: 10 board setups x 5 camera angles, varying corner occlusion |

## Usage

```bash
python yoloTesting/detect.py pictures/test1.png

python yoloTesting/prep_dataset.py path/to/roboflow-export
python yoloTesting/train.py path/to/roboflow-export 150
```

`train.py` defaults to `device="mps"` (Apple GPU); switch to `"cpu"` if that errors.

## Not in this repo

Model weights (`*.pt`), the image dataset, render outputs, and the source PDF are
excluded by `.gitignore` — they are large and either downloaded at runtime via
`huggingface_hub` or produced by `train.py`.
