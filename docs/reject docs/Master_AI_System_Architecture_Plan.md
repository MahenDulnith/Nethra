# Master AI System Architecture & Phase Plan

**Project:** AI Personal Assistant for Visually Impaired Users  
**System Paradigm:** Dual-Engine Architecture (System 1 "Jev Mode" + System 2 Multimodal GenAI) with Targeted LangGraph Orchestration  
**Deployment Target:** Android Pocket Hub (Snapdragon/Dimensity NPU) + Smart Glasses + Dual BLE Haptic Wristbands + Open-Ear Bone Conduction Audio  
**Companion Documents:** `docs/hardware_ai_mismatches_and_solutions.md`, `docs/AI_Personal_Assistant_Phase_Plan.md`  

---

## 1. Executive Summary & Architectural Philosophy

The objective of this system is to provide an end-to-end, whole-day personal assistant for visually impaired individuals. It bridges **low-latency physical safety** on the street with **context-rich conversational assistance** throughout the user's daily life.

### The Three Architectural Pillars

```
+----------------------------------------------------------------------------------------------------+
|                                    THREE ARCHITECTURAL PILLARS                                     |
+------------------------------------+----------------------------------+----------------------------+
| 1. LOCAL PHYSICAL SAFETY           | 2. REAL-TIME MULTIMODAL DIALOGUE | 3. ASYNC COGNITIVE ROUTINES|
| (100% Offline / Sub-100ms)         | (Full-Duplex Streaming / <400ms) | (Cloud LangGraph / Complex)|
| - YOLO11-nano + YOLO-World         | - Gemini Multimodal Live API     | - Multi-step day summary   |
| - Depth Anything v2 (Metric)       | - Native Speech-to-Speech        | - Calendar conflict repair |
| - Jev Mode Typed Arbiter           | - Edge SmolVLM (Offline Backup)  | - Offline LangSmith Eval   |
+------------------------------------+----------------------------------+----------------------------+
```

1. **Local-First Safety Invariance:**  
   Hazard warnings (approaching vehicles, head-height obstacles, drop-offs) run 100% on the mobile hub NPU. They never touch the cloud and operate with zero internet connectivity.
2. **Real-Time Multimodal Streaming (System 2 Core):**  
   Conversational scene description, "find X", and dialogue utilize full-duplex WebSocket audio/vision streaming. This eliminates the sluggish cascaded delay of `STT -> LLM -> TTS`, achieving human conversational latency (~300ms–500ms) with instant spoken barge-in.
3. **Targeted Agentic Graphing (LangGraph & LangSmith):**  
   Frameworks like LangGraph are intentionally **excluded** from the real-time audio/safety loops due to serialization overhead and latency bloat. Instead, LangGraph is deployed selectively as an **asynchronous cloud worker** for complex, multi-turn reasoning tasks (morning schedule reconciliation, evening timeline diary synthesis), while LangSmith powers the offline evaluation harness.

---

## 2. Targeted Framework Integration: Where LangGraph & LangSmith Fit (And Where They Do Not)

### Architectural Boundary Matrix

| System Component | Framework Choice | Why This Choice Was Made | What Was Explicitly Rejected |
|---|---|---|---|
| **Real-Time Voice Loop** | Native WebSockets / WebRTC (Live API) | Direct PCM audio-in / audio-out delivers ~350ms glass-to-ear latency and sub-100ms barge-in. | **Rejected LangChain/LangGraph:** Turn-based state graphs add 1.5s–3.0s of JSON serialization and graph traversal latency. |
| **Safety & Threat Arbitration** | **Jev Mode** (TypeSafe AI) + C++ NDK | Deterministic, sub-80ms typed decision engine returning typed enums (`CRITICAL`, `ADVISORY`, `IGNORE`) with calibrated probabilities. | **Rejected LLM Agents:** Probabilistic generative models are too slow and prone to unpredictable hallucinations in life-safety paths. |
| **Local Object & Depth Engine** | ONNX Runtime / SNPE (INT8) | Runs YOLO11-nano (30 FPS) and Depth Anything v2 directly on the phone's NPU in C++. | **Rejected Python Runtimes:** Heavy Python memory footprint (>300MB) causes severe thermal throttling inside pockets. |
| **Morning / Evening Routine Planner** | **LangGraph (Cloud Worker)** | **SELECTED:** Complex, multi-step asynchronous workflow that queries calendars, resolves conflicting appointments, and synthesizes 50+ memory events into an evening story. Latency of 2–4 seconds is completely acceptable here. | Rejected rigid linear scripts that cannot handle fuzzy calendar ambiguities. |
| **Benchmark & Safety Harness** | **LangSmith (Laptop Dev-Console)** | **SELECTED:** Evaluates VLM accuracy, measures hallucination rates against recorded street datasets, and logs prompt regression scorecards during Phase 0–2 development. | Rejected running LangSmith on live user video/audio feeds due to strict biometric privacy (GDPR / ethical compliance). |
| **On-Device Memory & Biometrics** | SQLite with **`sqlite-vec`** + ArcFace | C-based in-process vector database embedded inside encrypted SQLite (SQLCipher). Instant vector cosine distance lookup on-device. | Rejected remote cloud vector databases (Pinecone/Weaviate) that expose face embeddings and violate offline privacy. |

---

## 3. High-Level System Architecture & Hardware-AI Mapping

```
                                  [ USER PERIPHERALS ]
                                           |
             +-----------------------------+-----------------------------+
             |                                                           |
             v (Eye-Level 1080p Video via USB-C Tether)                 v (Open-Ear Audio & Mic via BT 5.3)
    [ Smart Glasses Camera ]                                   [ Bone-Conduction Headset ]
   (120° DFOV, High Shutter Speed)                             (Ambient traffic hearing open)
             |                                                           ^
             |                                                           | Spoken Guidance & Tones
             v                                                           |
+----------------------------------------------------------------------------------------------------+
|                                    ANDROID POCKET HUB (NPU / CPU)                                  |
|                                                                                                    |
|  [ LAYER 1: SENSOR ACQUISITION & HARDWARE DEFENSE ]                                                |
|    - Laplacian Motion Blur Filter (discards jerky frames during cane walking)                      |
|    - Ambient Luminance Fail-Safe (warns if lighting <15 lux: "Camera too dark")                    |
|                                                                                                    |
|  [ LAYER 2: LOCAL SAFETY ENGINE (100% OFFLINE / NPU INT8) ]                                        |
|    - YOLO11-nano (30 FPS Hazard Detector: Vehicles, Poles, Obstacles)                             |
|    - YOLO-World (Open-Vocabulary Zero-Shot Object Grounding for "Find X")                          |
|    - Depth Anything v2 Metric (Triggered conditionally when bounding box expands)                  |
|                                                                                                    |
|  [ LAYER 3: SYSTEM 1 ORCHESTRATOR ("JEV MODE" GATEKEEPER) ]                                        |
|    - Fast Intent Router (<80ms) -> Decides: Local Safety | Device Command | Cloud Live Stream     |
|    - Interruption & Cooldown Arbiter -> Decides: Immediate Speech | Haptic Pulse | Suppress         |
|                                                                                                    |
|  [ LAYER 4: LOCAL MEMORY & BIOMETRICS (SQLCIPHER) ]                                                |
|    - ArcFace 512-d Facial Embeddings (Consent-based recognition)                                   |
|    - sqlite-vec Local Vector Table (Episodic daily timeline & key-value preferences)               |
+----------------------------------+------------------------------------+----------------------------+
                                   |                                    |
            (Microsecond-Sync BLE) |                                    | (4G/5G Cellular WebSocket)
                                   v                                    v
                 [ Dual Haptic Wristbands ]               [ CLOUD INTELLIGENCE LAYER ]
                  - Left Wrist = Left Obstacle             - Gemini Multimodal Live Gateway
                  - Right Wrist = Right Obstacle             (Real-time speech-to-speech dialogue)
                  - Pulse Rate = Distance Metric           - Edge SmolVLM (On-device offline backup)
                                                           - Async LangGraph Routine Engine
                                                             (Morning briefs, Evening diary)
```

---

## 4. Hardware-Software Bottleneck Mitigations Matrix

To prevent hardware failure during physical trials, the following engineering mitigations are hardcoded into the pipeline:

| Hardware Bottleneck | Root Cause | Engineering Solution Implemented |
|---|---|---|
| **1. Glasses Battery Depletion (<45 mins)** | RF Wi-Fi video streaming consumes 1.5W–2.0W on small 250mAh glasses battery. | **Wired USB-C Tether:** Powers camera directly from the phone’s 4500mAh battery with zero wireless dropouts and zero RF temple heating. |
| **2. Walking Motion Blur** | Head swaying during cane walking causes rolling-shutter tearing, breaking OCR & YOLO. | **High Shutter Speed (1/250s) + Laplacian Sharpness Filter:** Automatically analyzes $\text{Var}(\nabla^2 I)$ and drops blurred frames. |
| **3. Phone Thermal Throttling in Pocket** | Running continuous vision models in an unventilated pocket overheats phone in 15 mins. | **INT8 Quantization + Conditional Depth:** Runs YOLO11 continuously, but triggers Depth Anything v2 *only* on approaching bounding boxes. |
| **4. Ground-Level Blind Spot (Drains & Steps)**| Eye-level glasses cannot view the ground within 1.5m of the user's feet. | **120° Wide-Angle Lens + Cane-First Principle:** Assistant explicitly delegates ground surface and drop-offs to the user's white cane. |
| **5. Night & Low-Light Blindness** | CMOS sensors produce noise in low light; AI goes silent, giving a false sense of safety. | **Luminance Threshold Guard:** If frame luminance drops below 15/255 for >2s, assistant announces: *"Too dark to see; rely on your cane."* |
| **6. Dual Wristband Desync** | Android BLE stack queues packets, causing one wrist to vibrate 80ms after the other. | **Timestamped Synchronized Packets:** Messages carry `trigger_epoch_ms: T + 80ms`; wristband MCUs fire motors in microsecond synchrony. |

---

## 5. End-to-End Latency & Reaction Budget

```
Target Safety Alert Budget: < 200 ms (Glass-to-Haptic)
Target Conversational Audio Budget: < 400 ms (Glass-to-Ear Speech)

[ CAMERA FRAME ] 
   │ (33ms - 30 FPS Exposure)
   ▼
[ USB-C TRANSFER ] 
   │ (10ms - UVC Buffer)
   ▼
[ YOLO11-NANO INT8 (NPU) ] 
   │ (18ms - Obstacle Detection)
   ▼
[ BYTE-TRACK MOTION VECTOR ] 
   │ (5ms - Distance Delta Calculation)
   ▼
[ JEV MODE SYSTEM 1 ARBITER ] 
   │ (15ms - Typed Priority Classification: TIER 1 ALERT)
   ▼
[ BLE SYNC PACKET DISPATCH ] 
   │ (25ms - GATT Transmission)
   ▼
[ LRA HAPTIC MOTOR ONSET ] 
   │ (20ms - Resonant Motor Spin-Up)
   ▼
[ USER FEELS HAPTIC WARNING ] ───► TOTAL: ~126 ms  (PASS: Well within safety margin)
```

---

## 6. Comprehensive Phase-by-Phase Roadmap

### Phase 0 — Foundation, Typed Contracts & Evaluation Harness (Weeks 1–2)
* **Objective:** Establish the development environment, simulate hardware streams, freeze data contracts, and launch evaluation tracking.
* **Workstreams:**
  - Define structured schemas for `CameraFrame`, `JevIntent`, `MultimodalChunk`, `SafetyAlert`, and `MemoryRecord`.
  - Build Dev-Console to replay synchronized 1080p walking video, multi-accent audio, and mock GPS sessions.
  - Setup **LangSmith** on laptop strictly for benchmark dataset evaluation (scoring baseline models on offline test clips).
  - Acquire Phase 0 dataset: 40 indoor scenes, 40 street scenes (traffic, open drains, tuk-tuks, street vendors).
* **Exit Gate:** Fake end-to-end replay pipeline operational on laptop; latency and API cost tracker functional.

### Phase 1 — Real-Time Voice Conversation Loop (Weeks 2–4)
* **Objective:** Deliver human-speed conversational speech (<400ms delay) with instant barge-in capabilities.
* **Workstreams:**
  - Integrate Gemini Multimodal Live API over WebSockets (bidirectional PCM audio).
  - Benchmark against traditional cascaded pipeline (`Silero VAD -> Whisper -> LLM -> Piper TTS`).
  - Implement client-side barge-in: voice activity stops audio playback within 100ms.
  - Tune spoken persona: warm, friendly, audio-optimized (1–2 concise sentences, clock-face directions, no markdown).
* **Exit Gate:** 95th percentile conversation response latency < 450ms; barge-in works reliably in street noise.

### Phase 2 — Hybrid Vision as a Tool & Look-Around Loop (Weeks 4–7)
* **Objective:** Enable the assistant to inspect the environment, locate target items, and admit uncertainty honestly.
* **Workstreams:**
  - Deploy **Jev Mode Frame Filter** on phone: drops blurry/dark frames before cloud dispatch, cutting API costs by >40%.
  - Integrate on-device **SmolVLM (2B)** via ONNX as an offline fallback for basic room inspection.
  - Implement visual tool functions: `describe_scene()`, `find_object(name)`, and `read_text()` (Google ML Kit OCR first).
  - Engineer the Look-Around State Machine: guides the user to scan (*"Turn slowly to your left... stop, door is at 10 o'clock"*).
* **Exit Gate:** "Find the door" success rate >= 85% across 6 rooms; hallucination rate < 3% on degraded images.

### Phase 3 — Daily Timeline & On-Device Memory (Weeks 6–9)
* **Objective:** Allow the assistant to maintain a personal episodic memory of the user's day with zero cloud data leaks.
* **Workstreams:**
  - Initialize encrypted **`sqlite-vec`** database on phone.
  - Implement episodic event logger: records place changes, conversations, completed tasks, and user memos.
  - Build natural language retrieval for fuzzy queries (*"Where did I leave my medication?"*).
  - Provide voice-driven privacy controls: *"Remember this fact"* and *"Forget what happened this afternoon"*.
* **Exit Gate:** Recall accuracy >= 90% across a 40-event test day; zero fabricated events in summary logs.

### Phase 4 — People Service & Consensual Face Recognition (Weeks 8–11)
* **Objective:** Recognize saved acquaintances reliably while enforcing strict consent-first ethics.
* **Workstreams:**
  - Implement conversation termination detector (audio silence + face presence).
  - Conversational consent prompt: *"You spoke with someone. Would you like me to remember them?"*
  - Extract 512-d face feature vectors using on-device **ArcFace**; immediately discard raw camera images.
  - Store vectors in `sqlite-vec` with strict cosine distance thresholds.
  - Enforce confidence tiers: High (>0.85) = Name spoken; Medium = "Someone is nearby"; Low = Absolute silence.
* **Exit Gate:** Zero false-positive identifications in 25 volunteer trials; deletion command permanently purges vectors.

### Phase 5 — Asynchronous Daily Routines via LangGraph (Weeks 9–12)
* **Objective:** Structure the user's daily life through automated morning previews, calendar management, and evening reviews.
* **Workstreams:**
  - Deploy **LangGraph Cloud Worker** for multi-step reasoning:
    * Reconciles conflicting calendar invites and builds optimal morning transit schedules.
    * Parses the day's `sqlite-vec` event timeline and synthesizes an emotional, coherent evening diary.
  - Implement natural language reminder scheduler with repeat rules and snooze handling.
  - Briefing duration toggle: "Quick Highlights" (30 seconds) vs "Detailed Review" (90 seconds).
* **Exit Gate:** 100% parsing accuracy on 30 complex spoken schedule requests; evening review verified 100% faithful to raw logs.

### Phase 6 — Local Safety Detector & Proactive Street Awareness (Weeks 11–14)
* **Objective:** Protect the user from moving vehicles and obstacles with sub-150ms offline response.
* **Workstreams:**
  - Deploy **YOLO11-nano** (30 FPS INT8) and **YOLO-World** (zero-shot target finder) on Snapdragon NPU.
  - Run **Depth Anything v2 (Metric)** conditionally on approaching bounding boxes.
  - Implement **Jev Mode Interruption Arbiter**: suppresses non-urgent speech during active hazard avoidance.
  - Verify complete offline operation: 100% of Critical Tier alerts function in airplane mode.
* **Exit Gate:** Threat detection-to-haptic dispatch < 150ms; false alarm rate < 1 alert per 15 minutes of walking.

### Phase 7 — Hardware Integration & Dual-Wristband Haptics (Weeks 13–15)
* **Objective:** Unify physical smart glasses, bone-conduction audio, and synchronized haptic wristbands into a wearable system.
* **Workstreams:**
  - Connect smart glasses 1080p camera feed via flexible braided USB-C tether.
  - Implement microsecond-synchronized BLE haptic alerts across left and right wristbands.
  - Map spatial vectors to intuitive haptic pulse cadences (high pulse frequency = immediate collision).
  - Add hardware health monitors: spoken telemetry for camera occlusion, BLE disconnects, and low battery (<15%).
* **Exit Gate:** Full wearable system operates continuously for 45+ minutes without thermal throttling or frame drops.

### Phase 8 — Safety Audits, Adversarial Testing & Volunteer Trials (Weeks 14–16)
* **Objective:** Validate real-world safety, test prompt-injection immunity, and conduct supervised user trials.
* **Workstreams:**
  - Test adversarial visual injections (malicious instructions on road signs or t-shirts); verify immunity.
  - Enforce strict non-negotiables: the assistant **never** states *"it is safe to cross"* and defers to the white cane.
  - Conduct supervised mobility trials with visually impaired volunteers across indoor and outdoor courses under institutional ethics approval.
  - Measure Task Completion Rate, System Usability Scale (SUS), cognitive workload (NASA-TLX), and subjective comfort.
* **Exit Gate:** Zero security vulnerabilities found; user study report completed; presentation demo rehearsed.

---

## 7. Deliverables & Presentation Artifacts Checklist

- [x] **Consolidated Master AI Architecture Plan** (`docs/Master_AI_System_Architecture_Plan.md`)
- [x] **Hardware-AI Mismatch & Mitigation Guide** (`docs/hardware_ai_mismatches_and_solutions.md`)
- [x] **AI Phase Plan** (`docs/AI_Personal_Assistant_Phase_Plan.md`)
- [x] **System Architecture Presentation Diagram** (Interactive Visual Slide Artifact)
