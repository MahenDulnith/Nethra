# Approved Master Synchronization Plan: 3-Stage Hardware Strategy + 8-Phase AI Roadmap

**Approval Status:** ✅ **APPROVED (With 3 Critical Synchronization Rules)**  
**Project:** AI Personal Assistant for Visually Impaired Users  
**Scope:** Synchronizing the 8-Phase AI Plan with the 3-Stage Custom Pocket Hub & Wearable Hardware Strategy  

---

## 1. Executive Approval Verdict

**Yes, this plan is officially approved and architecturally sound**, provided you enforce **three synchronization adjustments** between the AI team and the Hardware team so neither blocks the other during the 16-week window.

### Why This Combined Plan Works
1. **Zero Day-1 Blocking:** The AI team starts immediately in Week 1 using an off-the-shelf Android phone and laptop while hardware components are being sourced.
2. **Portable AI Runtime:** Because the AI stack uses cross-platform engines (**ONNX Runtime**, **SQLite + `sqlite-vec`**, and **WebSockets**), the code written in Stage 1 ports directly to the Stage 2 **RK3588S / Qualcomm Dev Board** without rewriting.
3. **Clear Risk Isolation:** If a custom PCB shipment is delayed in customs, the entire system still runs at 100% capability on the Stage 1 (Phone) or Stage 2 (3D-printed Dev Board Hub) for the final presentation and volunteer trials.

---

## 2. The 3 Critical Adjustments Required for Approval

### ⚠️ Adjustment 1: Align YOLO11 & Wristbands with the Correct Stage
* **The Issue:** Your Stage 1 draft listed *"Test YOLO11 and Bluetooth wristbands in Weeks 1–6"*, whereas your AI Phase Plan schedules **Proactive Street Awareness (YOLO)** in **Phase 6 (Weeks 11–14)** and **Haptics** in **Phase 7 (Weeks 12–14)**.
* **The Fix:**
  * In **Stage 1 (Weeks 1–6)**, the AI team focuses strictly on **Phase 1 (Voice)**, **Phase 2 (VLM & Look-around)**, and **Phase 3 (Memory)** on the Android phone.
  * Meanwhile, the Hardware team builds the **ESP32-C3 Haptic Wristbands** in parallel during Weeks 3–6 so they are ready for early BLE ping tests, even before the full Interruption Manager is built in Phase 6/7.

### ⚠️ Adjustment 2: PCB Manufacturing Lead-Time Realism (Stage 3)
* **The Issue:** Designing a 4-layer SoM carrier PCB, fabricating at JLCPCB/PCBWay, international shipping + customs clearance (to Sri Lanka), and board bring-up takes **5 to 8 weeks**. Starting PCB design in Week 13 means it will not arrive before Week 16 (Phase 8 User Testing).
* **The Fix:**
  * **Phase 8 User Testing (Weeks 14–16)** must be conducted using the **Stage 2 Embedded Prototype** (Off-the-shelf RK3588S Dev Board + 4G module + physical tactile GPIO buttons housed inside a clean, 3D-printed belt-clip enclosure) + Custom Smart Glasses + Custom ESP32 Wristbands.
  * **Stage 3 (Custom 4-Layer Carrier PCB)** should either begin schematic capture in **Week 6** (by a dedicated hardware member) OR be positioned as the **Phase 9 Commercialization / Final-Year Production Milestone**.

### ⚠️ Adjustment 3: Hardware Abstraction Layer (HAL) in Week 1
* To switch smoothly from the Android Phone (Stage 1) to the RK3588S Dev Board (Stage 2), define 3 strict software adapters in Week 1:
  * `CameraInputAdapter`: Reads either Android CameraX OR Linux V4L2 USB-C UVC stream.
  * `AudioIOAdapter`: Reads either Android Mic/Speaker OR Linux ALSA/PulseAudio Bluetooth headset.
  * `HapticOutputAdapter`: Sends identical 8-byte BLE GATT payloads to the ESP32-C3 wristbands.

---

## 3. Master Synchronized Timeline (AI Phases vs. Hardware Stages)

```
+=====================================================================================================+
| WEEKS  | AI PHASE PLAN (SOFTWARE & MODELS)          | HARDWARE 3-STAGE PLAN (PHYSICAL DEVICES)      |
+========+============================================+===============================================+
|        |                                            | [ STAGE 1: PHONE HUB & PERIPHERAL PROTO ]     |
| Wk 1–3 | Phase 1: Voice Conversation Loop           | • Use Android Phone as Pocket Hub             |
|        | • Streaming STT/TTS & Live API             | • Pair bone-conduction BT earphones           |
|        | • Barge-in & warm spoken persona           | • Breadboard ESP32-C3 + LRA vibration motors  |
+--------+--------------------------------------------+-----------------------------------------------+
|        | Phase 2: Vision as a Tool                  | • Assemble Smart Glasses prototype            |
| Wk 3–6 | • Cloud VLM + local OCR + "Find X"         |   (1080p UVC camera mounted on frame)         |
|        | • Guided look-around loop                  | • Connect glasses to phone via USB-C cable    |
|        | • Laplacian blur filter                    | • Finalize 3D-printed wristband enclosures    |
+========+============================================+===============================================+
|        | Phase 3: Daily Timeline & Memory (Wk 5–9)  | [ STAGE 2: EMBEDDED BENCH HUB PROTOTYPE ]     |
| Wk 7–9 | • SQLite + sqlite-vec episodic log         | • Boot RK3588S / Qualcomm Dev Board (Linux)   |
|        | • "Where did I leave my keys?" search      | • Attach 4G LTE USB/M.2 cellular module       |
+--------+--------------------------------------------+-----------------------------------------------+
| Wk 8–10| Phase 4: Contacts & Face Memory            | • Wire physical tactile buttons (Push-to-Talk,|
|        | • Consent prompt after conversation        |   Volume wheel, Mute switch) to Dev Board GPIO|
|        | • On-device ArcFace embeddings (encrypted) | • Connect 5,000 mAh Li-Po + BMS charger board |
+--------+--------------------------------------------+-----------------------------------------------+
| Wk 9–12| Phase 5: Morning & Evening Routines        | • Port ONNX Runtime & sqlite-vec to Dev Board |
|        | • Natural language reminders               | • 3D-print ergonomic belt-clip enclosure with |
|        | • Async LangGraph morning/evening summary  |   aluminum passive cooling plate              |
+========+============================================+===============================================+
|        | Phase 6: Proactive Street Awareness        | [ STAGE 3: FULL WEARABLE INTEGRATION & PCB ]  |
|Wk 11–14| • Local YOLO11-nano (30 FPS on NPU INT8)   | • Run YOLO11-nano on RK3588S NPU (6 TOPS)     |
|        | • Approaching tracking + Depth Anything v2 | • Test full tether: Glasses -> Custom Hub ->  |
|        | • Jev Mode Interruption Manager            |   BLE Wristbands + Bone-Conduction Audio      |
+--------+--------------------------------------------+-----------------------------------------------+
|Wk 12–14| Phase 7: Haptics & Multi-Channel Output    | • Verify <15ms BLE timestamp sync across      |
|        | • Speech vs Haptic dispatch policy         |   Left & Right ESP32-C3 wristbands            |
|        | • Left/Right/Pulse-rate distance cues      | • Schematic/Layout of 4-layer custom PCB      |
+--------+--------------------------------------------+-----------------------------------------------+
|Wk 14–16| Phase 8: Safety, Offline & User Testing    | • Conduct supervised indoor & outdoor trials  |
|        | • Airplane-mode offline hazard test        |   using the 3D-printed Custom Hub + Wearables |
|        | • Prompt-injection & darkness fail-safe    | • Measure battery life, heat (<40°C), comfort |
|        | • Co-design trials with blind volunteers   | • Final Demo at Colombo Builder Meetup        |
+=====================================================================================================+
```

---

## 4. Answers to Section 8 Open Questions (Recommended Defaults to Lock In Now)

To ensure your team starts Week 1 with zero ambiguity, here are the recommended decisions for Section 8 of your AI Phase Plan:

1. **Target users for the first version:**  
   👉 **Decision:** **Low-vision and experienced white-cane users** (as your advisor suggested). The day-assistant features (Phases 1–5) benefit everyone immediately, and cane users already have ground-obstacle protection while testing Phase 6 street alerts.
2. **Languages:**  
   👉 **Decision:** **English-first for core architecture (Weeks 1–6)**, with an early benchmark test of **Sinhala and Tamil** in Week 2 using Gemini Multimodal Live and Whisper/Cloud STT to document exact word error rates honestly.
3. **Where the agent runs:**  
   👉 **Decision:** **Cloud LLM/VLM for conversational intelligence + 100% Local Safety Layer** (YOLO11 + Jev Mode + ArcFace + `sqlite-vec` running on the Pocket Hub).
4. **Hardware for the first demo (Week 6 vs Week 16):**  
   👉 **Decision:** **Week 6 Demo:** Android Phone + Earphones + USB-C Glasses Camera. **Week 14–16 Final Demo:** Custom 3D-Printed Pocket Hub (RK3588S + Tactile Buttons) + Smart Glasses + Dual ESP32 Haptic Wristbands.
5. **Evaluation:**  
   👉 **Decision:** **5–8 consenting volunteers** in controlled campus/indoor corridors first, partnered with a local Sri Lankan visually impaired organization (e.g., Sri Lanka Council for the Blind or University Disability Support Unit) under university ethics approval.
