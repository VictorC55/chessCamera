from flask import Flask, request
import os
import socket
import time

app = Flask(__name__)
# incoming/ next to this script, wherever the repo is cloned
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "incoming")
os.makedirs(SAVE_DIR, exist_ok=True)


def lan_ip():
    """This Mac's Wi-Fi/LAN address (what a real phone needs as macIp). Sends no packets."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "unknown"

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
    return "Success", 200

if __name__ == '__main__':
    print(f"Saving photos to {SAVE_DIR}")
    print(f"Emulator: nothing to set (uses 10.0.2.2). Real phone: type {lan_ip()} in the app's IP box")
    app.run(host='0.0.0.0', port=5001)