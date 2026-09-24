"""Fine-tune a YOLO pose model to find the 4 board corners.

Usage: python train.py path/to/roboflow-export-folder [epochs]
Run prep_dataset.py on the folder first.
"""
import sys
from pathlib import Path
from ultralytics import YOLO

data = str(Path(sys.argv[1]).resolve() / "data.yaml")
epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 150

model = YOLO("yolo11s-pose.pt")  # COCO-pretrained; the head is rebuilt for 4 keypoints

model.train(
    data=data,
    epochs=epochs,
    imgsz=960,        # corners are small and precise; 640 loses pixels you need
    batch=8,          # drop to 4 if memory is tight
    device="mps",     # Apple GPU; use "cpu" if this errors
    patience=40,      # stop early if val stops improving
    fliplr=0.0,       # a mirrored chessboard is not a valid chessboard
    flipud=0.0,
    mosaic=0.3,       # board fills the frame, so heavy mosaic crops corners away
    degrees=10,       # small rotations only; large ones make corner identity ambiguous
    scale=0.4,
    hsv_v=0.5,        # lighting variation, cheaper than shooting more photos
    project="runs",
    name="corners",
)

print("\nbest weights: runs/corners/weights/best.pt")
print("val results:  runs/corners/")
