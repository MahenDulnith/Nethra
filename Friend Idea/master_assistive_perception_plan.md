# Nethra: Master Assistive Perception, Edge AI & Geo-Spatial Architecture Plan

> **Mission:** Transform Nethra from a laboratory prototype into a production-grade, human-level assistive wearable that guarantees physical safety for visually impaired travelers through deterministic offline edge AI, augmented by geo-spatial hazard memory and opportunistic cloud Vision-Language Models (VLMs).

---

## 1. Executive Summary & Engineering Realities

For a sighted person, identifying an open drain, a descending flight of stairs, or an approaching three-wheeler is instinctive and instantaneous ($\le 200\text{ ms}$). For a visually impaired traveler relying on an assistive wearable:
* **A false negative on a critical hazard (e.g., missing an open storm drain or approaching vehicle) can cause severe injury or death.**
* **A high false positive rate leads to auditory and cognitive exhaustion**, causing the user to reject or turn off the device.
* **Network drops happen constantly outdoors**; therefore, core collision avoidance must **never** depend on the cloud.
* **Current prototype numbers (e.g., 35 ms latency, 94.7% recall) reflect best-case laptop GPU execution on synthetic/development clips.** They do not yet represent true glass-to-haptic latency on wearable edge hardware in real-world environments.

To reconcile these requirements, Nethra is structured around a **Dual-Loop Hybrid Architecture**:
1. **The Fast Loop (Edge Safety — 100% Offline, $\le 45\text{ ms}$ true end-to-end, 30 FPS):** Guarantees physical safety, obstacle clearance, depth mapping, ground drops, and haptic feedback.
2. **The Slow Loop (Cloud VLM & High-Level Services — Opportunistic & On-Demand, 1.0–2.5 s):** Delivers rich contextual descriptions, sign/text reading, spatial Q&A, and high-level scene reasoning whenever internet connectivity is available.

```
+---------------------------------------------------------------------------------------------------+
|                                   NETHRA WEARABLE ARCHITECTURE                                    |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ Camera Stream (CSI / USB / Low-Latency Phone) + IMU Sensor ]                                   |
|            │                                                                                      |
|            ▼                                                                                      |
|  [ L1 Hygiene Gate (Downscaled Grayscale Sharpness + Exposure + Occlusion Check) ]                |
|            │                                                                                      |
|            ├─────────────────────────────────────────┐                                            |
|            ▼                                         ▼ (Trigger / Keyframe)                       |
|  ======================================   ======================================================  |
|  FAST LOOP: Local Edge Safety (Offline)   SLOW LOOP: Context, Geo & Cloud VLM (Async Thread)      |
|  - Frame Budget: <= 45 ms glass-to-haptic - Latency: 1.0 - 2.5 s (Does not block safety)          |
|  - Target: Jetson Orin Nano / Pi 5+Hailo  - Target: Local SQLite + Cloud APIs (Gemini Flash)      |
|  ======================================   ======================================================  |
|  1. Decoupled Depth Worker (10 Hz)        1. Geo-Spatial Layer:                                   |
|     - Running baseline drop/wall check       - Offline OSM Sri Lanka + GPS                        |
|     - Class-agnostic obstacle fallback       - Geocached Hazard Memory (drains, stairs)           |
|  2. Single Custom YOLO 36-Class (30 Hz)      - 2.5D Ego-Centric Occupancy Grid                    |
|     - Quantized INT8 / TensorRT           2. Local Memory & Routines:                             |
|     - Class allow-list from taxonomy         - Daily reminders (medicine, keys)                   |
|  3. ByteTrack + Kalman Filter                - Social memory (enrolled people with consent)       |
|     - Track continuity through camera shake3. Cloud VLM & OCR Engine:                             |
|  4. Honest Pinhole Geometry (Distance)       - Scene Q&A ("Where am I?", "Read text")            |
|     - Real-world height per class            - Runtime Safety Guard (15 forbidden phrases)        |
|  5. Closing-Speed TTC Estimator              - Circuit breaker & local fallback                   |
|     - Fast window (8-12f) on rapid growth 4. Multilingual Speech:                                 |
|  6. Deterministic Rule Arbiter               - Sinhala, Tamil, English TTS                        |
|     - Priority Matrix (Critical 1st)         - Pre-recorded WAV earcons for instant alerts        |
|  ======================================   ======================================================  |
|            │                                         │                                            |
|            ▼                                         ▼                                            |
|  [ Dual BLE Wristbands (ESP32-C3) ]       [ Audio Engine (Bone-Conduction Headset) ]              |
|  - Left / Right directional vibration     - Instant pre-recorded critical earcons                 |
|  - PWM proportional to threat proximity   - Context-gated advisory spoken announcements           |
|  - 200 ms Heartbeat & "Cannot See" mode   - Barge-in: Critical safety interrupts cloud audio      |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Perception & Safety Fixes (Addressing Theoretical & Practical Bugs)

### 2.1 The Time-to-Collision (TTC) Correction
* **The Flaw:** Claiming that bounding-box expansion rate ($dh/dt$) differentiates between stationary and moving objects is mathematically incorrect. A stationary utility pole also expands in the camera frame as the traveler walks toward it.
* **The Real Measurement:** Box expansion measures **closing speed** (the combined relative approach vector of traveler and object).
* **Engineering Fix:**
  - Update all arbiter messages and phrasebooks: growth-only triggers produce **"Obstacle ahead"** or **"Closing in"**, never falsely claiming an object is "approaching you" unless background depth subtraction or IMU ego-motion subtraction explicitly confirms independent object velocity.
  - Implement an **adaptive TTC window**: Use an 8–12 frame window (instead of 30 frames) when growth rate is high, enabling rapid response to fast-moving motorbikes or bicycles.

### 2.2 Class-Specific Pinhole Geometry for Metric Distance
* **The Flaw:** Using a single bounding-box area ratio ($A_{\text{ratio}} = \frac{\text{box\_area}}{\text{frame\_area}} \ge 0.45 \approx 1\text{m}$) treats all objects identically. A door covers 45% of the frame at 2.5 m, a coffee cup at 20 cm, and a public bus at 8 m.
* **Engineering Fix:** Replace class-blind area thresholds with a pinhole camera model based on known physical heights:
  $$\text{Distance } d = \frac{h_{\text{real}} \cdot f_{\text{px}}}{h_{\text{box\_px}}}$$
  Where $f_{\text{px}} = \frac{H_{\text{img}} / 2}{\tan(\text{VFOV} / 2)}$.
* **Class Dimension Reference Table:**
  ```python
  REAL_HEIGHT_M = {
      "person": 1.70, "door": 2.00, "car": 1.50, "bus": 3.20,
      "motorcycle": 1.10, "three_wheeler": 1.70, "chair": 0.90,
      "table": 0.75, "utility_pole": 3.00, "stairs_down": 0.80
  }
  ```
* **Edge-Clipping Fallback:** If a bounding box touches the frame boundary, $h_{\text{box}}$ is truncated; mark pinhole distance as invalid and fall back immediately to the depth map.

### 2.3 Relative Depth Calibration & Negative Obstacles (Drains & Drop-offs)
* **The Flaw:** Models like MiDaS Small output relative inverse depth. Per-frame min-max normalization forces arbitrary 0.0 and 1.0 values, causing false wall alerts in empty corridors and missing thin, dark storm drains.
* **Engineering Fixes:**
  1. **Running Baseline Normalization:** Maintain an exponential moving average (EMA) of floor-strip depth during normal walking. Alert on a **sudden negative delta** rather than a static threshold.
  2. **Pitch Angle Compensation via IMU:** Phone/camera pitch angle dictates where the floor plane intersects the image. Dynamically adjust the "feet ground strip" bounding box based on gyro pitch readings.
  3. **Segmentation for Negative Obstacles:** Box detectors fail on ground voids. Train a dedicated lightweight segmentation head (YOLO11-seg) specifically for `open_drain`, `stairs_down`, and `curb`.
  4. **Multi-Zone ToF Sensor Fusion (Physical Hardware):** Add an inexpensive I2C time-of-flight sensor (e.g., VL53L5CX 8x8 multizone ToF) pointing downward. Two independent physical modalities (vision + ToF) eliminate single-point-of-failure risk.

### 2.4 Class Filtering & Allow-List
* Drop non-navigation COCO classes (`traffic light`, `clock`, `remote`, `hair drier`, `sofa`) **before** sending detections to the tracker.
* The 4-of-5 temporal voting filter remains active as a secondary defense, but the allow-list eliminates root-cause transient noise.

### 2.5 Motion-Aware Tracking (ByteTrack)
* Upgrade from pure IoU tracking to **ByteTrack** with a Kalman filter.
* Predicts bounding box locations during walking bob and rapid head turns, preventing ID switches that reset TTC accumulation windows.

### 2.6 Latency Honesty & True End-to-End Measurement
* The reported 35.45 ms median measured only CPU/GPU inference on an RTX 4060 with pre-buffered frames.
* **Frame-Age Logging:** Every frame is timestamped at physical capture time (`t_capture = time.monotonic()`). End-to-end latency is recorded as:
  $$\text{Latency}_{\text{glass-to-action}} = (t_{\text{action\_dispatched}} - t_{\text{capture}}) \times 1000\text{ ms}$$
* **Physical Measurement Harness:** Measure true glass-to-haptic latency by flashing an LED in front of the lens and measuring the onset of wristband vibration via a 240 FPS high-speed camera or accelerometer probe.

---

## 3. Edge AI Hardware & Honest Simulation Architecture

### 3.1 Target Hardware Reality & Selection
A Raspberry Pi 5 CPU alone cannot sustain dual YOLO + MiDaS inference at $\ge 20\text{ FPS}$ without hardware acceleration:

| Platform | Compute Architecture | Expected Pipeline Latency | Recommendation |
|---|---|---|---|
| **Raspberry Pi 5 (CPU only)** | 4x ARM Cortex-A76 (No GPU/NPU) | 120–180 ms (5–8 FPS) | Insufficient for safety |
| **Raspberry Pi 5 + Hailo-8L AI Kit** | 13 TOPS NPU via PCIe | 25–40 ms (25–30 FPS) | Excellent, low power (5W) |
| **NVIDIA Jetson Orin Nano (8GB)** | 1024-core Ampere GPU (40 TOPS) | 18–28 ms (35–45 FPS) | **Primary Target for Prototype** |
| **Laptop Simulation (RTX 4060)** | Desktop CUDA / PyTorch | 35 ms (Compute only) | Development & Testing only |

> [!IMPORTANT]
> **Prototype Hardware Path:** Use the **Jetson Orin Nano** for the first physical wearable prototype to maintain seamless CUDA/TensorRT code portability. Move to Pi 5 + Hailo-8L once models are frozen.

### 3.2 Honest Simulation Profile (`--profile pi5-sim`)
To prevent false confidence during laptop simulation, introduce an honest benchmark profile:
```powershell
python main.py --profile pi5-sim --camera-profile phone
```
1. Forces execution on **CPU only** (`CUDA_VISIBLE_DEVICES=""`).
2. Pins process execution to 4 CPU cores via OS affinity.
3. Reduces input resolution to 320x320.
4. Enforces a strict pass/fail rule: if sustained FPS drops below 15 FPS or p95 latency exceeds 65 ms, the test suite fails.

### 3.3 Asynchronous Threaded Pipeline Refactor
The pipeline is restructured from a synchronous loop into an asynchronous multi-worker architecture:

```
[ Camera Capture Thread ] ───(Drop-Tail Slot)───► [ LatestFrame Store ]
                                                         │
                             ┌───────────────────────────┴───────────────────────────┐
                             ▼ (30 Hz)                                               ▼ (10 Hz Async Worker)
                  [ YOLO11n + ByteTrack ]                                   [ MiDaS Depth Worker ]
                             │                                                       │
                             └───────────────────────────┬───────────────────────────┘
                                                         │ (Synchronized Latest State)
                                                         ▼
                                          [ Deterministic Rule Arbiter ]
                                                         │
                                             ┌───────────┴───────────┐
                                             ▼                       ▼
                                   [ BLE Haptic Worker ]   [ Speech Dispatcher ]
```

1. **`LatestFrame` Drop-Tail Buffer:** Never queues frames. Slow consumers always receive the newest available frame; expired frames are discarded instantly.
2. **Decoupled 10 Hz Depth Worker:** Depth maps (walls and ground planes) evolve slower than moving objects. Running depth every 3rd frame (10 Hz) in an asynchronous worker cuts overall perception compute overhead by ~60% without sacrificing navigation safety.
3. **Optimized Hygiene Gate:** Runs on downscaled grayscale (160x120); full Canny occlusion check executed only once every 3 frames, reducing hygiene overhead from 6.0 ms to $< 1.2\text{ ms}$.

---

## 4. Safety Net, Fail-Safe Modes & Haptic Communication

### 4.1 Class-Agnostic Safety Net
* A sighted guide does not need to identify that an obstacle is an "antique mahogany footstool" to avoid tripping over it.
* **The Safety Net Rule:** If the depth map or ToF sensor detects a solid obstacle occupying the walking corridor ($< 2.0\text{ m}$):
  - If YOLO classifies it $\to$ Spoken label: *"Table at 12 o'clock, 1 meter."*
  - If YOLO misses it $\to$ Spoken label: *"Obstacle ahead, 1 meter."*
* **Silence must never be the result of a missing classification.**

### 4.2 "I Cannot See" Fail-Safe Mode
* When the hygiene gate rejects consecutive frames for $> 0.5\text{ s}$ (e.g., lens covered by coat, severe camera blur, complete darkness, or disconnected video feed):
  - The system triggers a distinct, continuous **"I Cannot See" haptic pulse** (e.g., repeating double-tap on both wrists).
  - Audio dispatcher announces: *"Camera obscured. Walking assistance paused."*
  - **Rule: The absence of vibration must always signify a clear path, never a dead system.**

### 4.3 Wristband Heartbeat & Watchdog
* The host computer sends an 8-byte heartbeat packet to both ESP32 wristbands every **200 ms**.
* If an ESP32 receives no heartbeat for $> 1.0\text{ s}$ (Bluetooth disconnect, host app crash, dead battery):
  - The firmware automatically enters **Fail-Safe Alert Mode**, vibrating a distinct 3-pulse alarm and cutting off any stuck motor PWM.

### 4.4 Ultra-Fast Alerts (Pre-Recorded Earcons)
* Spoken TTS sentences take 1.2–1.8 seconds to pronounce—unacceptable when TTC is $< 2.0\text{ s}$.
* For critical collision alerts:
  1. Haptic PWM pulses **instantly** (0 ms audio latency).
  2. Simultaneously plays a pre-recorded, zero-latency WAV earcon (`critical_12.wav`, `critical_11.wav`, `drop_warning.wav`).
  3. Spoken TTS follows *after* the immediate alarm to provide semantic details.

### 4.5 OS-Agnostic Audio Architecture
* Isolate all TTS behind the `AudioEngine` interface.
* Support Windows SAPI5 for local laptop development and native **Piper / eSpeak-NG** for Linux edge deployment, eliminating Windows-specific `win32com` dependencies in core layers.

---

## 5. Geo-Spatial Perception & Local Memory Integration

### 5.1 Layer A: Geo Layer (Offline OpenStreetMap Sri Lanka + GPS)
* **Offline Mapping:** Bundle a compressed OpenStreetMap (OSM) regional extract for Sri Lanka using a local spatial engine (e.g., SQLite R*Tree or spatialite).
* **Capabilities:**
  - Offline "Where am I?" queries: *"On Galle Road, 50 meters before Bambalapitiya junction."*
  - Crosswalk & intersection priors: Automatically lowers detector confidence threshold for `pedestrian_crossing` and `traffic_light` when GPS confirms approaching a mapped intersection.
* **Hazard Geocaching Memory:**
  - Sri Lankan sidewalks feature permanent hazards (uncovered drains, missing manhole covers, broken slabs).
  - When Nethra confirms a high-confidence hazard, it stores the coordinate in an 11-meter grid cell (`lat/lon` rounded to 4 decimals):
  ```sql
  CREATE TABLE geocached_hazards (
      cell_id TEXT PRIMARY KEY,
      hazard_class TEXT,
      latitude REAL,
      longitude REAL,
      last_seen_ts REAL,
      confirmation_count INTEGER
  );
  ```
  - When returning along the same route, Nethra announces: *"Caution: Known open drain 10 meters ahead on your left."*

### 5.2 Layer B: Local 2.5D Ego-Centric Occupancy Grid
* Constructs a local top-down spatial grid ($5\text{ m} \times 5\text{ m}$ at 10 cm resolution) centered on the traveler:
  1. Back-projects depth map pixels to 3D camera coordinates using calibrated intrinsics.
  2. Applies IMU pitch/roll rotation to align with gravity and fits the ground plane.
  3. Projects above-ground points into a 2D occupancy grid.
  4. Decays grid cells with an exponential half-life of 3.0 seconds.
* **Key Benefits:**
  - **Obstacle Permanence:** If the traveler turns their head and an obstacle moves outside the camera FOV, it remains remembered in the grid.
  - **Free-Space Steering:** Dual wristbands vibrate not just to warn of obstacles, but to gently guide the traveler toward the **widest open navigable corridor**.

---

## 6. Assistive Intelligence Modules (L4 Context & Routines)

### 6.1 Daily Activity Memory & Context-Gated Reminders
* Fully local, encrypted SQLite database (`SQLCipher`) storing user notes, medication schedules, and daily routines.
* **The Context Gate Rule:** Routine reminders are the lowest priority in the system. They are strictly blocked whenever:
  - An advisory or critical hazard is active.
  - The traveler is walking at $> 0.8\text{ m/s}$ near a road.
  - Reminders queue silently until the user stops in a safe area.

### 6.2 People Recognition & Social Memory
* **Pipeline:** YOLO person detection $\to$ Face bounding box (YuNet/SCRFD) $\to$ Quality filter ($> 50\text{ px}$ width) $\to$ Feature extraction (MobileFaceNet) $\to$ Cosine similarity against local enrolled gallery.
* **Physical Limits:** At 640x480 resolution, faces can only be reliably recognized within **1.5 to 2.0 meters**.
* **Ethical & Legal Compliance (Sri Lanka PDPA No. 9 of 2022):**
  - **Local Only:** Face embeddings are stored locally; raw photos are never uploaded or retained.
  - **Strict Consent:** Requires explicit enrolment. Unknown faces are never tracked or cataloged.
  - **Honest Phrasing:** Always speaks with confidence-graded phrasing: *"Possibly Nimal at 1 o'clock"*, never claiming certainty from single-frame matches.

### 6.3 Sri Lankan Specific Assistive Features
1. **Multilingual Speech Synthesis & Recognition:** Full support for **Sinhala, Tamil, and English**. Critical warning WAV clips pre-recorded in all three languages.
2. **Offline Bus Number & Signboard Reading:** Integrated offline OCR (e.g., PaddleOCR mobile) running on trigger (`'r'`) to read Sri Lankan public bus route numbers (e.g., "138", "120", "177").
3. **Currency Recognition:** Offline classification for Sri Lankan Rupee (LKR) currency notes (Rs. 20, 50, 100, 500, 1000, 5000).
4. **Emergency SOS & Fall Detection:** IMU detects sudden vertical drop followed by inactivity $\to$ triggers wristband countdown $\to$ dispatches emergency SMS with GPS coordinates.

---

## 7. Cloud Slow Loop Architecture & Safety Guardrails

### 7.1 Separation of Concerns & CI Enforcement
* All cloud communication resides strictly in `services/cloud/` at Layer L3/L4.
* **CI Rule R5 (Network Isolation):** The AST static analyzer verifies that no modules in `contracts/`, `services/safety/`, `adapters/haptic/`, or `adapters/camera/` contain networking imports (`requests`, `httpx`, `aiohttp`, `urllib`).

### 7.2 Cloud Circuit Breaker & Asynchronous Worker
* Network calls run in an isolated background thread with a strict 3.0-second timeout.
* If 3 consecutive requests fail, a **Circuit Breaker** opens for 60 seconds, transparently routing queries to local offline fallback engines without lagging the main application.

### 7.3 Runtime Output Safety Guard
The static CI phrasebook lint only validates hardcoded strings. Cloud VLM outputs are dynamic and require a **Runtime Safety Filter**:
```python
FORBIDDEN_PHRASES = [
    "safe to cross", "it is safe", "all clear", "nothing in front",
    "clear to walk", "no obstacles", "path is clear", "no danger"
]

def vlm_runtime_guard(text: str) -> str | None:
    text_lower = text.lower()
    # Reject any hallucinatory safety guarantees
    if any(phrase in text_lower for phrase in FORBIDDEN_PHRASES):
        return None
    # Enforce maximum 2 sentences to prevent cognitive overload
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:2])
```

### 7.4 Edge Privacy Protection
* Before transmitting any frame to the cloud VLM, an on-device privacy filter detects and blurs bystander faces and vehicle license plates.
* Images are transmitted ephemerally over TLS and never stored on remote servers.

---

## 8. Data Engine & Custom 36-Class Model Training

Generic Western datasets fail to capture Sri Lankan road and sidewalk hazards. Relying on COCO-80 leaves travelers blind to tuk-tuks, open sewers, and vendor stalls.

### 8.1 Sri Lankan Dataset Collection Protocol
* Record 10+ hours of first-person walking video across 5 distinct environments:
  1. High-density commercial: Colombo Fort, Pettah markets (crowds, curbs, stalls).
  2. Arterial roads: Galle Road, Kandy Road (buses, three-wheelers, motorbikes).
  3. Residential lanes: Suburban Colombo & Kandy (open drains, gravel, dogs).
  4. Indoor transit: Railway stations, bus terminals, pedestrian footbridges.
  5. Low-light & rain: Dusk/night walking and monsoon rain conditions.
* Mount camera at chest height with an synchronized 6-axis IMU logger.

### 8.2 Labeling & Segmentation Strategy
* **Negative Obstacles (`open_drain`, `stairs_down`, `ground_drop`):** Must be annotated with **polygon segmentation masks** (YOLO11-seg), not bounding boxes.
* **Auto-Labeling Pipeline:** Pre-annotate candidate frames using zero-shot foundation models (Grounding DINO / YOLO-World), followed by 100% human verification and correction.

### 8.3 The Continuous Mining Data Engine
* Automatically save hard edge-case frames to a local debug buffer:
  - Frames where detector confidence falls in the ambiguous range ($0.25 \le \text{conf} \le 0.45$).
  - Frames where YOLO and Depth disagree (e.g., Depth detects an obstacle, but YOLO reports clear).
  - Frames where the user presses the "Report False Alert" wristband button.
* Re-train and deploy updated INT8 weights monthly.

---

## 9. Revised Master Roadmap (Phases 5A to 14) with Concrete Exit Gates

```
+---------------------------------------------------------------------------------------------------+
|                              NETHRA REVISED IMPLEMENTATION ROADMAP                                |
+---------------------------------------------------------------------------------------------------+
|  PHASE 5A: Honest Measurement & Profiling [IMMEDIATE]                                             |
|  - Frame-age logging (t_now - t_capture) in pipeline telemetry                                    |
|  - Implementation of --profile pi5-sim (CPU-only, 4 cores, 320x320)                               |
|  - Physical glass-to-haptic LED probe calibration                                                 |
|  * Exit Gate: True baseline latency logged in docs/results_log.md                                  |
+---------------------------------------------------------------------------------------------------+
|  PHASE 5B: Concurrency & Perception Performance Refactor                                          |
|  - Threaded pipeline: LatestFrame drop-tail buffer (zero queue lag)                               |
|  - Decoupled 10 Hz asynchronous Depth worker thread                                               |
|  - Pinhole camera metric distance calculation (REAL_HEIGHT_M)                                     |
|  - Running baseline depth delta for drop-off & wall detection                                     |
|  - Class allow-list & ByteTrack Kalman filter integration                                         |
|  - VLM Runtime Output Safety Guard (vlm_runtime_guard)                                            |
|  * Exit Gate: Sustained 30 FPS YOLO + 10 FPS Depth; p95 latency <= 45 ms on RTX 4060              |
+---------------------------------------------------------------------------------------------------+
|  PHASE 5C: Target Hardware Benchmarking                                                            |
|  - Deploy pipeline to Jetson Orin Nano (TensorRT FP16) and Raspberry Pi 5                         |
|  - Benchmark sustained thermal stability, power consumption, and FPS                             |
|  * Exit Gate: Validate >= 25 FPS sustained on target embedded board                               |
+---------------------------------------------------------------------------------------------------+
|  PHASE 6: Sri Lankan Dataset & Custom 36-Class Model                                              |
|  - Collect 10 hours of tagged walking video in Sri Lanka (Pettah, Galle Rd)                       |
|  - Train custom Nethra YOLO11n / YOLO11-seg (Critical hazards + three-wheelers)                   |
|  * Exit Gate: Recall >= 90% at 3m on held-out Sri Lankan test split                               |
+---------------------------------------------------------------------------------------------------+
|  PHASE 7: Spatial & Fail-Safe Upgrades                                                            |
|  - "I Cannot See" fail-safe haptic alarm on prolonged hygiene blockage                            |
|  - Class-agnostic obstacle safety net (depth corridor fallback)                                   |
|  - 2.5D Ego-Centric Occupancy Grid for obstacle memory & free-space steering                      |
|  * Exit Gate: Zero unannounced corridor obstacles in test replay suite                            |
+---------------------------------------------------------------------------------------------------+
|  PHASE 8: Physical Haptics & ESP32-C3 Firmware                                                    |
|  - Dual BLE GATT drivers with 200 ms bidirectional heartbeat watchdog                             |
|  - Physical wristband prototypes with coin vibration motors                                       |
|  * Exit Gate: 60-minute soak test without BLE disconnect or unhandled drop                        |
+---------------------------------------------------------------------------------------------------+
|  PHASE 9: User Co-Design (Early Blind User Evaluation)                                            |
|  - Supervised indoor navigation trials with 3–5 blind participants                                |
|  - Validate haptic vocabulary, auditory intelligibility, and cognitive load                       |
|  * Exit Gate: User comprehension of haptic patterns >= 95%; feedback logged                       |
+---------------------------------------------------------------------------------------------------+
|  PHASE 10: Local Context, Routines & Multilingual Audio                                           |
|  - Encrypted SQLite routine memory & context-gated reminder arbiter                               |
|  - Sinhala and Tamil offline TTS & pre-recorded critical earcons                                  |
|  * Exit Gate: Reminder engine 100% blocked during navigation hazard events                        |
+---------------------------------------------------------------------------------------------------+
|  PHASE 11: Cloud Slow Loop (VLM, OCR & Geocached Hazard Memory)                                   |
|  - Asynchronous Gemini Flash client with circuit breaker                                          |
|  - Offline bus route number OCR & OpenStreetMap hazard geocaching                                 |
|  * Exit Gate: Cloud failure or latency spike causes 0 ms jitter on Fast Loop safety               |
+---------------------------------------------------------------------------------------------------+
|  PHASE 12: People Recognition (Privacy-First)                                                     |
|  - YuNet face detector + MobileFaceNet local embeddings                                           |
|  - Consent manager & PDPA 2022 legal compliance audit                                             |
|  * Exit Gate: False match rate <= 1.0%; zero photos uploaded or unencrypted                       |
+---------------------------------------------------------------------------------------------------+
|  PHASE 13: Supervised Outdoor Field Trials                                                        |
|  - 10 blind participants walking real outdoor routes with white cane                              |
|  - Formal evaluation: Hazard recall, false alarm rate, NASA-TLX cognitive index                   |
|  * Exit Gate: Documented field safety report and peer-reviewed benchmark log                      |
+---------------------------------------------------------------------------------------------------+
```

---

## 10. Tactical 30 / 60 / 90 Day Execution Plan

* **Days 1–30 (Foundation & Concurrency):**
  - Implement Phase 5A: Frame-age logging and `--profile pi5-sim`.
  - Implement Phase 5B: Threaded `LatestFrame` buffer, 10 Hz async depth worker, pinhole geometry distances, and class allow-list.
  - Integrate `vlm_runtime_guard` and pre-recorded critical WAV earcons.
  - Procure target embedded hardware (Jetson Orin Nano / Raspberry Pi 5).

* **Days 31–60 (Hardware Validation & Dataset Engine):**
  - Execute Phase 5C: Target board benchmarking in `docs/results_log.md`.
  - Mount chest camera rig and record 10 hours of Sri Lankan mobility footage across Colombo.
  - Train custom YOLO11n on critical tier (`open_drain`, `three_wheeler`, `stairs_down`).
  - Implement ESP32-C3 BLE heartbeat and "I Cannot See" fail-safe haptics.
  - Conduct Phase 9: First supervised indoor test with 3 blind participants.

* **Days 61–90 (Context, Spatial Memory & Field Verification):**
  - Implement Phase 10 & 11: Sinhala/Tamil audio, offline OSM geocached hazards, and asynchronous Gemini Flash VLM client.
  - Implement 2.5D ego-centric occupancy grid for free-space steering.
  - Conduct Phase 13: Full supervised outdoor field trials with white cane users.
