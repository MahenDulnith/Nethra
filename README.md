# Nethra: Edge-AI Assistive Vision & Spatial Haptic Navigation

> **Real-time edge computer vision, spatial haptic navigation, and contextual scene intelligence for visually impaired and blind individuals.**

**Nethra** delivers ears-free, low-latency obstacle awareness and conversational scene understanding using Edge AI. Instead of overwhelming the user's ears with continuous spoken audio announcements, Nethra translates spatial obstacle geometry directly into **dual-wristband haptic vibrations (Left & Right PWM / BLE signals)** while reserving spoken announcements for high-priority safety alerts and on-demand scene queries.

> 📄 **Full project overview (problem, architecture, status, roadmap, evaluation, limitations):** [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)

---

## Key Features

1. **Dual-Model YOLO11 Nano Ensemble (`L2` Offline Safety Engine)**:
   - Runs **Base YOLO11 Nano (`models/yolo11n.pt`)** for all 80 COCO classes (`person`, `car`, `motorcycle`, `chair`, `bed`, `bottle`, etc.) alongside a **Fine-Tuned Assistive Model (`models/nethra_doors_yolo11n.pt`)** for structural navigation classes (`door`, `handle`, `stairs`, indoor hazards) with IoU Non-Maximum Suppression deduplication.
   - Automatically accelerates on **NVIDIA CUDA** (Windows/Linux), **Apple Silicon MPS** (M1–M4 Macs), or **CPU**.

2. **Spatial Haptic Routing (Left / Center / Right)**:
   - **Horizontal Zone Division**:
     - **Left Third (`LEFT`)**: Triggers Left Wristband vibration.
     - **Center Third (`CENTER`)**: Direct collision path ahead (triggers both Left & Right wristbands simultaneously).
     - **Right Third (`RIGHT`)**: Triggers Right Wristband vibration.
   - **Proximity PWM Modulation**: Bounding-box area ratio maps smoothly to vibration duty cycle ($0\% - 100\%$).

3. **Cross-Platform Camera HAL (`L1` Adapters)**:
   - **macOS + iPhone**: Continuity Camera (`--camera 1`, Ultra-Wide `0.5x`).
   - **Windows + Android**: USB ADB stream / DroidCam / IP Webcam (`--camera-url http://127.0.0.1:8080/video` or `--camera 1`).
   - **Synthetic Mock Feed**: Built-in oscillating obstacle corridor (`--mock`) for hardware-free testing and CI.

4. **Guided Search & Hand-to-Object Micro-Navigation (`L4` Features + `L2` HandTracker)**:
   - Interactive object search (`[F]` Find Door, `[B]` Find Bottle, `[X]` Cancel) with temporal confirmation, MediaPipe index-fingertip tracking, and error-scaled wristband pulse guidance (`0.8s` $\to$ `0.2s` period, `"da-DUM"` double-pulse on alignment).

5. **Contextual Scene, Room Classifier & Wake-Up Intelligence (`L4` Features)**:
   - Recognizes routine contexts (e.g., detecting a `bed` in view triggers a morning wake-up greeting) and classifies indoor rooms (`Computer Laboratory`, `Bedroom`, `Living Room`, `Kitchen Area`, `Outdoors`).
   - Interactive location & scene query (`[W]` key: *"Where am I?"*) backed by [`config/locations.json`](file:///Users/mahendulnith/Project/Assistive_Vision_Prototype/config/locations.json).

---

## Quick Start

### 1. Setup Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1
# Or Activate (macOS / Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Running Nethra

#### Option A: macOS with iPhone Continuity Camera
```bash
python main.py --camera 1
```

#### Option B: Windows with Android Phone Camera (USB ADB or IP Webcam / DroidCam)
```bash
# If using DroidCam / USB Virtual Webcam:
python main.py --camera 1

# If using IP Webcam over USB ADB forwarding (adb forward tcp:8080 tcp:8080) or Wi-Fi:
python main.py --camera-url http://127.0.0.1:8080/video
```

#### Option C: Synthetic Mock Stream (No camera required)
```bash
python main.py --mock
```

### 3. Interactive Controls
- **`v` / `Space`** — **Push-to-Talk Voice Agent** (speak naturally: *"Find my laptop"*, *"Where is the door?"*, *"What do you see?"*, *"Where am I?"*, *"Stop"*)
- **`d`** — Describe current scene & spatial object breakdown (*"What is in front of me?"*)
- **`f`** — Start Guided Search for a **Door** (`SEARCHING` $\to$ `HEAD_GUIDE` $\to$ `HAND_GUIDE` $\rightleftharpoons$ `ALIGNED`)
- **`b`** — Start Guided Search for a **Bottle**
- **`x`** — Cancel active Guided Search and return to normal navigation
- **`c`** — Cycle active cameras (Phone Camera ↔ Laptop Webcam)
- **`w`** — Trigger multi-modal location & room query (*"Where am I?"*)
- **`m`** — Mute / Unmute spoken TTS audio feedback
- **`q`** — Quit cleanly

---

## Running Unit Tests & Fine-Tuning

```bash
# Run unit test suite
python test_spatial.py
# or
python -m unittest discover -s tests

# Fine-tune custom doors/obstacles YOLO11n model (auto-detects CUDA / MPS / CPU)
python train.py --data datasets/doors/data.yaml --epochs 30
```

---

## Project Architecture & Directory Structure (L0 – L5)

```text
Nethra/
├── main.py                  # Root CLI launcher
├── train.py                 # Root CLI entry point for YOLO11n fine-tuning
├── test_spatial.py          # Root unit test runner
├── requirements.txt         # Cross-platform Python dependencies
├── config/                  # Thresholds, classes, phrasebook, haptic patterns, & providers
├── models/                  # Model weights (yolo11n.pt, nethra_doors_yolo11n.pt, buffalo_sc/)
├── contracts/               # L0: Platform-free data contracts (FrameData, Detection, SafetyAlert, HapticCommand)
├── adapters/                # L1: Hardware adapters (Camera HAL, Audio, BLE Haptics, MonotonicClock, Storage)
├── services/                # L2 (Offline Hygiene, YOLO Ensemble, Spatial Router, Arbiter, Memory) & L3 (Voice, Vision, Agent)
├── features/                # L4: User workflows (Context Scene Tracker, Guided Look-Around, People, Failsafe)
├── shell/                   # L5: AppGraph wiring, Power modes, & OpenCV HUD (shell/hud/opencv_hud.py)
├── instrumentation/         # Latency probes & structured JSONL logging
├── training/                # YOLO11n transfer learning & edge export scripts
├── datasets/                # Dataset configurations (HomeObjects-3K.yaml, doors/data.yaml)
├── tests/                   # Unit & invariant test suites
├── firmware/                # ESP32-C3 wristband C/C++ firmware
├── harness/                 # Session replay, benchmark suite, and results analysis
├── ci/                      # Architecture dependency & safety phrasebook linters
└── docs/                    # Master specification, implementation plan, and research papers
```
