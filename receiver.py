import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "yoloTesting"))

from flask import Flask, request, jsonify
import socket
import time
import json
import cv2
import numpy as np

app = Flask(__name__)
# incoming/ next to this script, wherever the repo is cloned
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "incoming")
os.makedirs(SAVE_DIR, exist_ok=True)

# Load models at startup
from chess_pipeline import load_models
print("Loading models...")
piece_model, corner_model = load_models()
print("Models loaded!")


def lan_ip():
    """This Mac's Wi-Fi/LAN address (what a real phone needs as macIp). Sends no packets."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "unknown"

@app.route("/detect_corners", methods=["POST"])
def detect_corners_route():
    f = request.files["image"]
    path = os.path.join(SAVE_DIR, f"setup_{int(time.time())}.jpg")
    f.save(path)

    img = cv2.imread(path)                  # applies EXIF rotation, same as the phone's upright view
    if img is None:
        return jsonify(ok=False)
    h, w = img.shape[:2]

    from chess_pipeline import (detect_pieces, detect_corners_yolo, detect_corners_piece_hull,
                                corners_contain_pieces, pick_orientation, CANDIDATES)
    from refine_any_color import refine_color

    pieces = detect_pieces(path, piece_model)
    rough = detect_corners_yolo(path, corner_model)
    if rough is None or (pieces and not corners_contain_pieces(rough, pieces)):
        rough = detect_corners_piece_hull(img, pieces)
    if rough is None:
        return jsonify(ok=False)

    result = refine_color(img, rough)
    fine = result[0] if isinstance(result, tuple) else result

    # image-order corners -> chess order (a8, h8, h1, a1)
    name, _H, _score = pick_orientation(fine, pieces)
    order = dict(CANDIDATES)[name]
    ordered = np.array([fine[i] for i in order], dtype=float) / [w, h]
    return jsonify(ok=True, corners=ordered.tolist())

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return "No image found", 400
    file = request.files['image']

    # Add a timestamp so we don't overwrite previous photos
    timestamp = int(time.time())
    filename = f"capture_{timestamp}.jpg"
    filepath = os.path.join(SAVE_DIR, filename)

    file.save(filepath)
    print(f"\n✅ RECEIVED PHOTO: {filename}")

    # Check if corners were provided
    corners_json = request.form.get("corners")
    if corners_json:
        print(f"📐 CORNERS PROVIDED: {corners_json}")
        try:
            img = cv2.imread(filepath)
            h, w = img.shape[:2]
            rough = np.array(json.loads(corners_json), dtype=np.float32) * [w, h]

            from refine_any_color import refine_color
            result = refine_color(img, rough)              # snap to the grid; order is preserved
            fine = result[0] if isinstance(result, tuple) else result
            info = result[1] if isinstance(result, tuple) else None
            if info is not None and not info.get("ok", True):
                fine = rough                               # refinement failed, trust the user's dots

            print(f"🎯 REFINED CORNERS: {fine}")

            # TODO: Use the refined corners with the pipeline
            # from chess_pipeline import make_homography, detect_pieces, dedupe_and_map, fen_from_squares
            # H = make_homography(fine)                      # already a8,h8,h1,a1, so skip pick_orientation
            # pieces = detect_pieces(filepath, piece_model)
            # fen = fen_from_squares(dedupe_and_map(pieces, H))
        except Exception as e:
            print(f"⚠️  Error processing corners: {e}")

    return "Success", 200

if __name__ == '__main__':
    print(f"Saving photos to {SAVE_DIR}")
    print(f"Emulator: nothing to set (uses 10.0.2.2). Real phone: type {lan_ip()} in the app's IP box")
    app.run(host='0.0.0.0', port=5001)