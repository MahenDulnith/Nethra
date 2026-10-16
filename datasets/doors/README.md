# Doors & Navigation Dataset Directory

Place your custom door dataset here to fine-tune YOLO11 Nano.

### Expected Directory Layout:
```
datasets/
└── doors/
    ├── data.yaml       # Class definitions and paths
    ├── train/
    │   ├── images/     # Training photos (.jpg, .png)
    │   └── labels/     # YOLO format bounding boxes (.txt)
    └── val/
        ├── images/     # Validation photos (.jpg, .png)
        └── labels/     # YOLO format bounding boxes (.txt)
```

---

## 📥 How to Get a Ready-to-Use Door Dataset:

### Option 1: Roboflow Universe (Easiest & Free)
1. Visit: **[Roboflow Universe Door Detection](https://universe.roboflow.com/search?q=door)**
2. Select any popular dataset (e.g., `Door-Detection` or `Doors and Stairs`).
3. Click **Export Dataset** $\to$ Select format: **YOLOv8** (fully compatible with YOLO11).
4. Select **Download ZIP to computer**.
5. Unzip the downloaded folder and place the `train/`, `valid/`, and `data.yaml` files inside this `datasets/doors/` folder.

---

### Option 2: Train on Your Own Room Doors
You can also take 20–30 photos of your own room doors (open, closed, from different angles) using your iPhone:
1. Upload photos to **[roboflow.com](https://roboflow.com)**.
2. Draw bounding boxes labeled `door` and `handle` (takes ~5 minutes).
3. Export as YOLOv8 format and place it here!

---

## 🚀 How to Start Training:

Once the dataset is in this folder, simply run:
```bash
.venv/bin/python train.py --epochs 30
```

Your M4 Mac will automatically use its GPU (Apple Silicon MPS) to train the model in ~10–15 minutes, producing `models/nethra_doors_yolo11n.pt`!
