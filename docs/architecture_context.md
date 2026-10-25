# Architecture & Project Context: Nethra Assistive Vision Prototype

## 1. Project Goal & Vision
Build an edge-AI wearable assistive device (**Nethra**) for visually impaired and blind individuals. The system provides real-time obstacle navigation via directional haptic feedback, comprehensive object recognition across daily life, and contextual voice assistance (e.g., wake-up greeting in bed, voice Q&A like "Where am I?", and campus/landmark recognition such as the University of Sri Jayewardenepura).

---

## 2. Hardware Architecture & Phased Roadmap

### Target Wearable System Architecture
- **Host Edge Compute Unit**: Apple Silicon MacBook (M1–M4 Mac with Metal Performance Shaders GPU acceleration, or Windows laptop) running the L0–L5 Nethra pipeline at 30+ FPS.
- **Wearable Head / Face Smartphone Mount**: A custom head-mounted glasses/face holder positions the smartphone at eye level for hands-free, first-person ultra-wide vision, streaming live camera video to the Mac via Continuity Camera, Wi-Fi IP stream, or USB.
- **Dual Wireless Haptic Wristbands (Left & Right)**: Two custom-built wristbands connected wirelessly (BLE / Wi-Fi) to the Mac. Each wristband integrates an **ESP32-C3 microcontroller**, a **3.7V rechargeable Li-Po battery**, a **charging controller module (TP4056 USB-C with protection)**, and a **vibration motor/driver** driven by real-time PWM and pattern commands.
- **Ears-Free Design Philosophy**: Spatial obstacle guidance is delivered via left/right tactile vibration rather than continuous spoken audio, preserving the user's natural hearing for traffic awareness and echolocation.

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
