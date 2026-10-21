from flask import Flask, request
import os
import time

app = Flask(__name__)
SAVE_DIR = os.path.expanduser("~/Desktop/chessCamera/incoming/")
os.makedirs(SAVE_DIR, exist_ok=True)

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
    app.run(host='0.0.0.0', port=5001)