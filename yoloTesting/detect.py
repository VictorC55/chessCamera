import sys
from huggingface_hub import hf_hub_download
from ultralytics import YOLO
import cv2

img_path = sys.argv[1] if len(sys.argv) > 1 else "../pictures/test1.png"

# Pretrained YOLOv8m chess-piece detector (12 classes: white/black x pawn/rook/knight/bishop/queen/king)
piece_model = YOLO(hf_hub_download("KanisornPutta/chess-model-yolov8m", "chess-model-yolov8m.pt"))

# Pretrained YOLO11s-pose model: 1 class (chessboard) with 4 keypoints = square corners a1, h1, a8, h8
board_model = YOLO(hf_hub_download("surawut/chess-move-tracking-yolo11", "models/yolo11s_pose_chessboard.pt"))
CORNERS = ["a1", "h1", "a8", "h8"]  # keypoint order the model was trained with

res = piece_model(img_path, conf=0.4)[0]
img = res.plot()  # draws piece boxes + labels

bres = board_model(img_path, conf=0.2, max_det=1)[0]
if len(bres.boxes):
    pts = bres.keypoints.xy[0].cpu().numpy().astype(int)      # shape (4, 2): x,y per corner
    kconf = bres.keypoints.conf[0].cpu().numpy()               # per-keypoint confidence
    quad = pts[[0, 1, 3, 2]]                                   # a1 -> h1 -> h8 -> a8 makes a closed loop
    cv2.polylines(img, [quad.reshape(-1, 1, 2)], True, (0, 0, 255), 3)
    for name, (x, y), c in zip(CORNERS, pts, kconf):
        cv2.circle(img, (x, y), 8, (0, 0, 255), -1)
        cv2.putText(img, name, (x + 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        print(f"corner {name} {c:.2f} [{x}, {y}]")
else:
    print("board: not found")

for b in res.boxes:
    print(piece_model.names[int(b.cls)], f"{float(b.conf):.2f}", [int(v) for v in b.xyxy[0]])

cv2.imwrite("out.png", img)
print("saved out.png")
