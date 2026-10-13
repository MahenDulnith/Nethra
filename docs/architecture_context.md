# Architecture & Project Context: Nethra Assistive Vision Prototype

## 1. Project Goal & Vision
Build an edge-AI wearable assistive device (**Nethra**) for visually impaired and blind individuals. The system provides real-time obstacle navigation via directional haptic feedback, comprehensive object recognition across daily life, and contextual voice assistance (e.g., wake-up greeting in bed, voice Q&A like "Where am I?", and campus/landmark recognition such as the University of Sri Jayewardenepura).

---

## 2. Hardware Architecture & Phased Roadmap

### Phase 1: Desktop / Laptop Prototype (Current Phase)
- **Host Compute**: Cross-platform Laptop (Windows with NVIDIA CUDA / CPU or Apple M1–M4 Mac with MPS) running Python, OpenCV, and YOLO11 Nano (`yolo11n`).
- **Vision Capture**:
  - **macOS + iPhone**: iPhone Ultra-Wide lens streaming via native macOS Continuity Camera (0.5x zoom mode) at 640×480 resolution.
  - **Windows + Android**: Android camera streaming over USB ADB port-forwarding (`adb forward`) or DroidCam / IP Webcam at 640×480 resolution.
- **Haptic Simulation & BLE Output**: Real-time HUD visual telemetry bars with PWM duty cycles (0% to 100%) for Left and Right wristbands, plus BLE GATT output to ESP32-C3 wristbands.
- **Ears-Free Design Philosophy**: Visual/spatial guidance is delivered via tactile vibration rather than continuous spoken audio, preserving the user's natural hearing for spatial awareness and echolocation.

### Phase 2: Wearable Pocket Unit (Future Production Phase)
- **Pocket Compute Unit**: Power-bank-sized device (e.g., Raspberry Pi 5 with Hailo AI HAT+ neural accelerator running at 30+ FPS, or dedicated Snapdragon/Apple NPU motherboard) worn in a pocket or on a belt.
- **Wearable Glasses**: Ultra-lightweight glasses containing an ultra-wide camera, microphone, and bone-conduction speaker. Zero heavy compute or hot batteries on the head.
- **Haptic Wristbands**: Left and right wristbands equipped with vibration motors driven by PWM signals corresponding to obstacle proximity and direction.

---

## 3. Computer Vision & Machine Learning Pipeline

- **Model Selection**: **YOLO11 Nano (`yolo11n`)** — the newest and fastest edge-optimized model from Ultralytics.
- **Class Scope**: **All 80 COCO classes enabled** (furniture, persons, vehicles, doors/exits, everyday objects like beds, chairs, cups, phones, laptops).
- **Quantization & Edge Compilation**:
  - Phase 1: PyTorch (`.pt`) running on M4 Mac (with Apple MPS / CoreML support).
  - Phase 2: Export to **ONNX** or **LiteRT (TFLite INT8)** to compile directly onto the Hailo AI accelerator chip or mobile NPU without retraining.

---

## 4. Spatial Routing & Haptic Motor Control Logic

Object bounding boxes from YOLO11n drive dual-wristband vibration:

### Horizontal Spatial Routing (X-Axis)
The horizontal video frame ($W$) is divided into three zones:
- **Left Zone** ($0 \le x_{center} < \frac{1}{3} W$): Triggers Left Wristband vibration.
- **Center Zone** ($\frac{1}{3} W \le x_{center} \le \frac{2}{3} W$): Object directly in path; triggers simultaneous dual-wristband alert or front warning.
- **Right Zone** ($x_{center} > \frac{2}{3} W$): Triggers Right Wristband vibration.

### Proximity Estimation (Area $\to$ PWM Intensity)
- **Bounding Box Area**:
  $$\text{Area Ratio} = \frac{\text{width} \times \text{height}}{W \times H}$$
- **PWM Intensity ($0\% - 100\%$)**:
  As the user approaches an obstacle or door, its bounding box takes up a larger fraction of the field of view. The area ratio maps to motor PWM vibration intensity. Distant objects produce subtle or no vibration; imminent obstacles trigger strong pulses.

---

## 5. Scene Context & Conversational Roadmap

Beyond obstacle avoidance, the system maintains environmental awareness:
- **Wake-Up & Morning Routine**: Detects when the user is in bed (e.g., prominent `bed` detection upon start) and simulates a morning greeting: *"Good morning, you are in your bed right now."*
- **Conversational Queries**: Audio hook to answer questions such as *"Where am I?"* through geolocation, WiFi fingerprinting, and landmark vision (e.g., identifying buildings at the University of Sri Jayewardenepura).
