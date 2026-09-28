window.EPIC_1 = {
  "id": "epic-1",
  "number": 1,
  "name": "Foundation & Tooling",
  "shortName": "Foundation",
  "description": "Repository, environment and a pretrained baseline that runs end to end: board corners and pieces drawn on a photo.",
  "status": "COMPLETED",
  "tasks": [
    {
      "id": "1-1",
      "name": "Repository scaffold",
      "details": "GitHub repo <code>VictorC55/chessCamera</code>, README, <code>.gitignore</code> for weights, runs, PDFs and large photo sets",
      "dependencies": [],
      "status": "COMPLETED",
      "prLinks": ["https://github.com/VictorC55/chessCamera/commit/7181d29d458a0131c452ee5f86e40655c7593fb7"],
      "links": [{ "label": "Repository", "url": "https://github.com/VictorC55/chessCamera" }],
      "fullDetails": "<h3>What was delivered</h3><p>Initial repository with the detection pipeline, a README describing the approach, and a <code>.gitignore</code> that keeps large or generated files out of git.</p><h3>Layout</h3><pre>Syslab/\n├── README.md\n├── requirements.txt\n├── plan.txt                 # capture plan (Epic 2)\n├── helpers/pdfToJPGs.py\n├── docs/project-plan/       # this plan\n├── pictures/                # datasets (mostly Drive-only)\n└── yoloTesting/\n    ├── detect.py\n    ├── prep_dataset.py\n    ├── train.py\n    ├── corner_error.py\n    └── refine_corners.py</pre><h3>Ignored</h3><ul><li><code>*.pt</code>, <code>weights/</code>, <code>runs/</code>: model files and training output</li><li><code>*.pdf</code>, <code>pictures/50test</code>, <code>results/</code>: source scans and scratch output</li></ul>"
    },
    {
      "id": "1-2",
      "name": "Pretrained baseline (detect.py)",
      "details": "Runs a Hugging Face YOLO11s-pose board model and a YOLOv8m 12-class piece detector on one image and writes <code>out.png</code>",
      "dependencies": [],
      "status": "COMPLETED",
      "prLinks": ["https://github.com/VictorC55/chessCamera/commit/7181d29d458a0131c452ee5f86e40655c7593fb7"],
      "links": [
        { "label": "detect.py", "url": "https://github.com/VictorC55/chessCamera/blob/main/yoloTesting/detect.py" },
        { "label": "Board model (HF)", "url": "https://huggingface.co/surawut/chess-move-tracking-yolo11" },
        { "label": "Piece model (HF)", "url": "https://huggingface.co/KanisornPutta/chess-model-yolov8m" }
      ],
      "fullDetails": "<h3>What was delivered</h3><p>A baseline that downloads two pretrained models and draws their output on a photo.</p><h3>Run</h3><pre>cd yoloTesting\n.venv/bin/python detect.py ../pictures/test1.png   # writes out.png</pre><h3>What we learned about the board model</h3><table><thead><tr><th>Measure (our 49 photos)</th><th>Result</th></tr></thead><tbody><tr><td>Board found</td><td>27 / 49</td></tr><tr><td>Corner error, names ignored</td><td>median 2.9 squares</td></tr><tr><td>Corner naming</td><td>by image position (kp0 far side in 25/27), not true a1</td></tr></tbody></table><p>It was probably trained with a fixed camera behind White, so its a1/h1/a8/h8 names are only right from that side. Our own model (Epic 3) replaces it for corners. The piece model has not been evaluated yet (Epic 7).</p>"
    },
    {
      "id": "1-3",
      "name": "PDF → JPG helper",
      "details": "<code>helpers/pdfToJPGs.py</code> extracts the photos from the CamScanner PDF into <code>pictures/50test/</code>",
      "dependencies": [],
      "status": "COMPLETED",
      "prLinks": ["https://github.com/VictorC55/chessCamera/commit/7181d29d458a0131c452ee5f86e40655c7593fb7"],
      "links": [{ "label": "pdfToJPGs.py", "url": "https://github.com/VictorC55/chessCamera/blob/main/helpers/pdfToJPGs.py" }],
      "fullDetails": "<h3>What was delivered</h3><p>A PyMuPDF script that pulls each page image out of the scanned PDF.</p><h3>Notes</h3><ul><li>The scans are 2480×3509 portrait pages with a white margin and a CamScanner watermark at the bottom right. Colours are also enhanced by the scanner.</li><li>Dataset v2 (Epic 6) should use the phone's original photos instead, so training data looks like what the camera will produce during a game.</li></ul>"
    },
    {
      "id": "1-4",
      "name": "requirements.txt for the whole project",
      "details": "One install for every script: ultralytics 8.4.155, PyYAML, OpenCV, huggingface_hub, pymupdf; torch left unpinned so Colab keeps its CUDA build",
      "dependencies": [],
      "status": "COMPLETED",
      "prLinks": [
        "https://github.com/VictorC55/chessCamera/commit/e9b210c86a7fcc7130976d8877da65e0c54436a4",
        "https://github.com/VictorC55/chessCamera/commit/9561045da6a8f857b0c8279003f5bd16c72c33aa"
      ],
      "links": [{ "label": "requirements.txt", "url": "https://github.com/VictorC55/chessCamera/blob/main/requirements.txt" }],
      "fullDetails": "<h3>What was delivered</h3><pre>pip install -r requirements.txt</pre><p>Covers <code>yoloTesting/</code> and <code>helpers/</code>. torch is not listed: ultralytics installs it when missing, and pinning it would replace Colab's GPU build.</p><h3>Two virtual environments</h3><ul><li><code>yoloTesting/.venv</code>: has everything; use <code>.venv/bin/python</code></li><li><code>Syslab/.venv</code>: nearly empty; a shell that activates it gives \"No module named yaml\"</li></ul>"
    },
    {
      "id": "1-5",
      "name": "Colab training recipe",
      "details": "Mount Drive, install requirements, run prep and train from the same folder; no uploads needed because the project already lives in Drive",
      "dependencies": ["requirements.txt for the whole project"],
      "status": "COMPLETED",
      "prLinks": [],
      "links": [{ "label": "Google Colab", "url": "https://colab.research.google.com/" }],
      "fullDetails": "<h3>Recipe</h3><p>Runtime → Change runtime type → T4 GPU, then:</p><pre>from google.colab import drive\ndrive.mount('/content/drive')\n\n%cd \"/content/drive/MyDrive/Syslab\"\n!pip install -q -r requirements.txt\n\n%cd yoloTesting\n!python prep_dataset.py ../pictures/50testEdited\n!python train.py ../pictures/50testEdited</pre><h3>Notes</h3><ul><li><code>train.py</code> picks CUDA automatically, so no editing is needed.</li><li>Re-run <code>prep_dataset.py</code> on each machine: it writes that machine's absolute path into <code>data.yaml</code>.</li><li>A saved notebook is task 3-10.</li></ul>"
    }
  ]
};
