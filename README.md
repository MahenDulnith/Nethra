# PulsePath: Edge-AI Assistive Vision Prototype

> **Real-time edge computer vision and spatial haptic navigation for visually impaired and blind individuals.**

PulsePath delivers ears-free, low-latency obstacle awareness and contextual scene intelligence using Edge AI. Instead of flooding the user's ears with continuous audio announcements, the system translates spatial geometry directly into dual-wristband haptic vibrations (Left & Right PWM signals) while maintaining full environmental awareness.

---

## 🚀 Key Features

1. **Dual-Model Ensemble Detection**:
   - Runs **YOLO11 Nano (`yolo11n`)** for all 80 COCO classes (people, bottles, chairs, laptops, phones).
   - Fine-tuned `pulsepath_doors_yolo11n.pt` for dedicated indoor door detection (~9.1ms latency on M4 GPU via Apple Metal Performance Shaders / MPS).
   - IoU-based deduplication merges bounding boxes without catastrophic forgetting.

2. **Interactive Guided Search Mode ("Help me find the door")**:
   - Ask to find an object (**`F`** for door, **`B`** for bottle, **`P`** for person).
   - **Scene Memory & Look-Around Voice**: If the target isn't visible, natural voice prompts describe what *is* seen: *"I can't see a door yet. I can see a table and a laptop. Please turn your head slowly to the left and right."*
   - **Target Acquisition**: Plays a pleasant chime once the object is spotted and confirmed.

3. **MediaPipe Hand Tracking & Directional Steering**:
   - Uses MediaPipe Tasks `HandLandmarker` on Apple Silicon CPU via XNNPACK delegate.
   - Detects user's raised hand (index fingertip) and steers it:
     - Target to left of hand $\to$ Left wristband pulses.
     - Target to right of hand $\to$ Right wristband pulses.
     - Directional vector arrow draws between hand fingertip and target crosshair.
   - **On Target Pattern**: When pointed directly at target ($\pm 8\%$ tolerance), both wristbands pulse in a synchronised `"da-DUM"` pattern with audio confirmation: *"Your hand is pointing at the door. Walk that way."*

4. **Dual-Wristband Visual HUD**:
   - Tactile watch-strap widgets on the left and right display borders pulse with real-time PWM intensity ($0\% - 100\%$) and dynamic threat glow.
   - Color-coded bounding boxes (green $\to$ amber $\to$ red).

5. **Safety Priority Override**:
   - Any obstacle in the immediate walking path exceeding $80\%$ collision proximity immediately preempts guidance haptics with continuous obstacle warning.

6. **Contextual Scene & Wake-Up Intelligence**:
   - Bed detection triggers morning greeting: *"Good morning! You are in your bed right now."*
   - Location queries (**`W`** key): *"Where am I?"* (e.g., University of Sri Jayewardenepura campus context).

---

## 🛠️ Quick Start

### 1. Prerequisites
- macOS (tested on Apple Silicon M4 / M3 / M2 / M1)
- Python 3.11 - 3.13
- iPhone with Continuity Camera (optional; Mac FaceTime HD webcam or synthetic mock stream supported)

### 2. Setup Environment
```bash
# Clone the repository
git clone https://github.com/MahenDulnith/Nethra.git
cd Nethra

# Create virtual environment
python3 -m venv .venv

# Install dependencies
.venv/bin/pip install -r requirements.txt
```

### 3. Running the Prototype

#### Live Video (iPhone Continuity Camera):
```bash
.venv/bin/python main.py --camera 1
```

#### Live Video (Mac FaceTime HD Camera):
```bash
.venv/bin/python main.py --camera 0
```

#### Synthetic Mock Feed (Headless or test mode):
```bash
.venv/bin/python main.py --mock
```

### 4. Interactive Keyboard Controls
| Key | Action |
|:---:|:---|
| **`F`** | Start Guided Search for **Door** |
| **`B`** | Start Guided Search for **Bottle** |
| **`P`** | Start Guided Search for **Person** |
| **`X`** | Cancel search / return to obstacle navigation |
| **`C`** | Switch camera input (iPhone $\leftrightarrow$ Mac) |
| **`W`** | Where am I? (Contextual announcement) |
| **`M`** | Mute / Unmute voice audio |
| **`Q`** | Quit application |

---

## 🧪 Running Tests

Run the full unit test suite (guidance state machine + haptic pattern generator):
```bash
MPLCONFIGDIR=/tmp/matplotlib .venv/bin/python -m unittest discover tests
```

---

## 📂 Project Structure

```
├── main.py                     # Main application orchestrator
├── pulsepath/                  # Modular package
│   ├── detection.py            # Dual-model ensemble & spatial routing engine
│   ├── guidance.py             # Guided search state machine & look-around memory
│   ├── haptics.py              # Time-varying PWM haptic pattern engine
│   ├── hand_tracker.py         # MediaPipe Tasks index-fingertip hand tracker
│   ├── hud.py                  # High-contrast visual HUD & dual wristband widgets
│   ├── audio.py                # Non-blocking async TTS (say) & system chimes (afplay)
│   ├── camera.py               # Camera opening, fallback & synthetic stream generator
│   ├── context.py              # Scene tracker (bed wake-up, location query)
│   └── commands.py             # Key shortcuts & voice intent parser
├── tests/
│   ├── test_guidance.py        # 6 unit tests for guidance transitions & tolerance
│   └── test_haptics.py         # 7 unit tests for pulse modulation & safety overrides
├── requirements.txt            # Pinned dependencies
├── architecture_context.md     # System architecture & hardware roadmap
└── Document/
    └── Edge AI Glasses for Blind.pdf
```
