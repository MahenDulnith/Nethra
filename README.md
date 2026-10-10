# PulsePath: Edge-AI Assistive Vision Prototype

> **Real-time edge computer vision and spatial haptic navigation for visually impaired and blind individuals.**

PulsePath delivers ears-free, low-latency obstacle awareness and contextual scene intelligence using Edge AI. Instead of flooding the user's ears with continuous audio announcements, the system translates spatial geometry directly into dual-wristband haptic vibrations (Left & Right PWM signals) while maintaining full environmental awareness.

---

## 🚀 Key Features

1. **Full-Class Environmental Understanding**:
   - Runs **YOLO11 Nano (`yolo11n`)** on local Apple Silicon (MPS / Apple Neural Engine) or edge accelerators.
   - Identifies all 80 COCO classes (beds, chairs, doors, people, laptops, phones, bottles, etc.) without filtering.

2. **Spatial Haptic Routing (Left / Center / Right)**:
   - **Horizontal Division**: Maps bounding box positions across the field of view:
     - Left Third: Triggers Left Wristband vibration.
     - Center Third: Direct collision path (dual-wristband warning).
     - Right Third: Triggers Right Wristband vibration.
   - **Proximity PWM Modulation**: Bounding box area ratio maps directly to vibration intensity ($0\% - 100\%$). As obstacles approach, tactile pulses intensify.

3. **Contextual Scene & Wake-Up Intelligence**:
   - Recognizes routine contexts (e.g. detecting a `bed` in view triggers a morning greeting: *"Good morning! You are in your bed right now."*).
   - Conversational query hook (`'w'` key) for location queries: *"Where am I?"* (e.g., University of Sri Jayewardenepura campus context).

4. **Designed for Wearables & Low Heat**:
   - Current Phase: M4 Mac + iPhone Ultra-Wide Camera (macOS Continuity Camera at 0.5x).
   - Hardware Roadmap: Pocket-sized compute unit (Raspberry Pi 5 + Hailo AI HAT+) + camera glasses + vibration wristbands.

---

## 🛠️ Quick Start

### 1. Prerequisites
- macOS (tested on Apple Silicon M4 / M3 / M2 / M1)
- Python 3.11 - 3.13
- iPhone with Continuity Camera (optional; webcam or synthetic mock stream supported)

### 2. Setup Environment
```bash
# Clone the repository
git clone https://github.com/your-username/PulsePath.git
cd PulsePath

# Create virtual environment
python3 -m venv .venv

# Install dependencies
.venv/bin/pip install -r requirements.txt
```

### 3. Running the Prototype

#### With iPhone Ultra-Wide (Continuity Camera):
1. Connect your iPhone via USB-C or Wi-Fi to your Mac.
2. In macOS Control Center -> **Video Effects**, disable *Center Stage* and set zoom to **0.5x** (Ultra-Wide).
3. Run:
```bash
.venv/bin/python main.py --camera 1
```
*(If camera index 1 is not your iPhone, try `--camera 2` or `--camera 0`)*

#### With Synthetic Mock Feed (No camera required):
```bash
.venv/bin/python main.py --mock
```

### 4. Interactive Controls
- Press **`q`** to quit cleanly.
- Press **`w`** to trigger location query (*"Where am I?"*).
- Press **`m`** to toggle audio/voice announcements.

---

## 🧪 Running Tests

```bash
.venv/bin/python test_spatial.py
```

---

## 📂 Project Structure

```
├── architecture_context.md  # Detailed architecture context & hardware roadmap
├── main.py                  # Core real-time vision, spatial routing & HUD pipeline
├── test_spatial.py          # Unit tests for spatial calculations & context logic
├── requirements.txt         # Pinned Python dependencies
├── .gitignore               # Git ignore configuration
└── Document/
    └── Edge AI Glasses for Blind.pdf  # Original research and specification brief
```
