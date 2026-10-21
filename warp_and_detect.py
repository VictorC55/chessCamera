import sys
import numpy as np
import cv2
from chess_pipeline import load_models, detect_fen, detect_pieces

def main(img_path):
    print("Loading models...")
    pm, cm = load_models()

    print("Finding the board and computing homography...")
    # This uses your robust pipeline (YOLO + Hull fallback)
    res = detect_fen(img_path, pm, cm, verbose=True)
    
    if res["H"] is None:
        print("Failed to find board.")
        return

    H = res["H"]
    img = cv2.imread(img_path)

    # 1. Warp the image to a flat 800x800 square
    S = 100
    SZ = 8 * S
    warped = cv2.warpPerspective(img, H, (SZ, SZ))
    cv2.imwrite("warped_board.jpg", warped)
    print("\nSaved warped_board.jpg (The perfectly flat board!)")

    # 2. Run YOLO on the flat board
    print("\nRunning YOLO on the perfectly flat board...")
    flat_pieces = detect_pieces(warped, pm)

    # 3. Draw results and print squares
    out = warped.copy()
    for p in flat_pieces:
        x1, y1, x2, y2 = p["bbox"]
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(out, p["class"], (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Because it's flat, the square is just simple math!
        cx, cy = p["base_pt"]
        col = int(cx // S)
        row = int(cy // S)
        if 0 <= col <= 7 and 0 <= row <= 7:
            sq = f"{'abcdefgh'[col]}{8-row}"
            print(f"{p['class']} at {sq}")

    cv2.imwrite("warped_detected.jpg", out)
    print("\nSaved warped_detected.jpg (Red boxes on the flat board!)")

if __name__ == "__main__":
    main(sys.argv[1])