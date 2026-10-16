# AI Personal Assistant for Visually Impaired People — AI Phase Plan

> Scope of this document: **the AI part only** (agent, memory, vision, voice, proactive behaviour). Hardware (glasses, wristbands) is covered separately and appears here only as input/output channels.

---

## 1. Vision

A personal assistant that supports a visually impaired person through the **whole day**, not just on the street:

- **Morning:** wake-up, today's schedule, reminders.
- **Out and about:** describes the surroundings, warns about vehicles and hazards, answers "what's in front of me?" and "where is the door?".
- **Social:** after a conversation, asks *"You spoke with someone, should I save them to your contacts?"* Later, when that person is nearby: *"That person is close, you might want to say hello."*
- **Evening:** reviews how the day went and reminds the user of tomorrow's schedule.
- **Tone:** warm and friendly, "like a best friend", while staying honest about what it cannot see.

The assistant is **built around a timeline and memory**. Vision, voice, and haptics are tools it uses.

---

## 2. Design Principles

1. **Assistant first, detector second.** Object detection is one tool, not the product.
2. **Always honest.** Say "I'm not sure" or "I can't see that" instead of guessing.
3. **Consent for everything personal.** Nothing about a person is saved without the user's permission, and the user can delete anything.
4. **Safety-critical alerts work offline.** Vehicle and obstacle warnings must not depend on internet or the cloud.
5. **Advisor, not pilot.** Report what is detected. Never say "it's safe to cross."
6. **Privacy by default.** Process video locally; do not store raw video; keep face data on the device.
7. **Don't overwhelm.** Few, well-timed messages beat constant chatter.

---

## 3. AI Architecture Overview

```
                       USER (voice, glasses camera, wristbands)
                                      |
                  +-------------------+-------------------+
                  |                                       |
          Input layer                              Output layer
   Mic -> STT   Camera frames                  TTS   Haptic commands
                  |                                       ^
                  v                                       |
        +--------------------------------------------------------+
        |                  ASSISTANT AGENT (LLM)                 |
        |  - Dialogue manager and persona                        |
        |  - Tool router (decides what to call)                  |
        |  - Interruption / priority manager                     |
        +----+-----------+-----------+-----------+-----------+---+
             |           |           |           |           |
        Vision tools  Memory     Calendar &   Contacts &   Proactive
        (VLM, OCR,    store      reminders    face memory  monitor
        detector)     (timeline)               (consent)   (local, always-on)
```

### Core components

| Component | Role |
|---|---|
| **Agent (LLM)** | Understands requests, chooses tools, writes short spoken replies. |
| **Vision tools** | VLM for scene description and "find X"; OCR for reading; small local detector for vehicles/obstacles. |
| **Memory store** | Timeline of events, places, people, preferences; supports search ("who did I meet yesterday?"). |
| **Calendar/reminders** | Schedule, daily routine, reminders. |
| **Contacts and face memory** | Consent-based storage of people and their face embeddings. |
| **Proactive monitor** | Runs locally, watches for events worth interrupting for (vehicle approaching, known person nearby). |
| **Interruption manager** | Decides *whether* and *how* to speak or vibrate, based on priority, cooldowns, and context. |

### Suggested data model (simplified)

| Entity | Key fields |
|---|---|
| `Event` | id, timestamp, type (conversation, place, alert, task), summary, location (optional), people[] |
| `Person` | id, name (optional until given), face embedding(s), first met, last seen, notes, consent flag |
| `Contact` | person_id, name, phone (optional), where met, notes |
| `Reminder` | id, text, time, repeat rule, status |
| `Preference` | key, value (speech speed, verbosity, language, alert sensitivity) |
| `DaySummary` | date, highlights, people met, tomorrow's schedule |

---

## 4. Phase-by-Phase Plan

Timings are indicative (about 15 weeks); adjust to your semester.

---

### Phase 1 — Voice Conversation Loop (weeks 1–3)

**Goal:** A hands-free assistant you can talk to naturally.

**AI components**
- Speech-to-text (STT) with streaming and voice-activity detection
- LLM dialogue with a "friendly assistant" system prompt
- Text-to-speech (TTS) with adjustable speed and interruption (barge-in)
- Short-answer style tuned for audio (no long paragraphs, no markdown)

**Inputs / outputs**
- Input: user speech
- Output: spoken reply

**Key design questions**
- How short should replies be by default? (Make it a user setting.)
- How do we signal "thinking" during delays? (A short tone or "let me check.")
- Which languages first? (English first; test Sinhala and Tamil early.)

**How to test**
- Latency from end of speech to start of reply (median, 95th percentile)
- STT word error rate on your own voices and accents
- User rating of naturalness and clarity

**Deliverable:** Working voice assistant prototype (phone app or script) plus a latency and accuracy report.

---

### Phase 2 — Vision as a Tool (weeks 3–6)

**Goal:** The assistant can look and answer questions about what it sees.

**AI components**
- Frame capture tool (sample the best recent frames, not every frame)
- Vision-language model (VLM) for: "what's in front of me?", "describe this scene", "what colour is this?"
- OCR for signs, labels, and documents
- "Find X" skill, for example *"Where is the door?"*, returning structured output: `found / not found`, direction, rough distance, confidence
- **Look-around loop:** if not found or confidence is low, ask the user to turn (*"I can't see it yet, please turn slowly to your left"*)

**Inputs / outputs**
- Input: voice query + recent frames
- Output: spoken description or instruction

**Key design questions**
- Which VLM gives the best accuracy/latency/cost? (Compare cloud and small local models.)
- How many frames, and at what resolution, per question?
- How should the assistant phrase directions? (Clock positions, "left/right", landmarks.)

**How to test**
- Fixed image/video set (rooms and streets) with questions and ground truth
- Accuracy of "found / not found" and direction
- Hallucination rate: how often it states something that isn't there
- Average number of turns the look-around loop needs

**Deliverable:** Vision tool set + comparison table of VLMs (accuracy, latency, cost) + look-around loop demo.

---

### Phase 3 — Daily Timeline and Memory (weeks 5–9)

**Goal:** The assistant remembers the user's day and can answer questions about it.

**AI components**
- Event logging: places visited, conversations, alerts, tasks completed
- Memory store with retrieval (search by time, person, place, or meaning)
- Summarisation of the day from the event log
- Preferences memory (speech speed, how much detail the user likes)

**Inputs / outputs**
- Input: events from other tools and the user's statements ("remember that my keys are on the hall table")
- Output: answers to *"What did I do today?"*, *"Where did I leave my keys?"*, *"Who did I meet yesterday?"*

**Key design questions**
- What gets logged automatically and what needs the user's say-so?
- How long is data kept, and how can the user review or delete it?
- Where does it live? (Local database first; optional encrypted sync.)

**How to test**
- Recall accuracy on a scripted "day" of events
- Retrieval quality for vague questions
- User control tests (delete, edit, "forget this")

**Deliverable:** Memory service + timeline log + recall test results.

---

### Phase 4 — Contacts and Face Memory with Consent (weeks 7–10)

**Goal:** Save people the user chooses to remember, and recognise them later.

**AI components**
- Detect that a conversation happened (speech from another person + a face in view)
- After the conversation, ask: *"You spoke with someone, should I save them?"*
- On approval: ask for a name, then save face embedding(s) and a contact record
- Recognition: match faces against saved embeddings; announce name and position (*"Nimal is ahead, on your left"*)
- Confidence handling: if unsure, **do not name anyone**; say "someone is nearby" or stay silent

**Inputs / outputs**
- Input: camera frames, conversation signal, user's yes/no and name
- Output: saved contact, or a spoken notification

**Key design questions**
- How many face samples per person are needed for reliable matching?
- What is the right threshold for naming someone? (A wrong name is worse than a missed one.)
- How does the user remove a person? (Voice command: "forget Nimal.")

**How to test**
- Match accuracy across lighting, angle, distance, glasses/masks
- False match rate (should be very low)
- End-to-end test of the "save → meet again → alert" flow with consenting volunteers

**Privacy rules**
- Face data stays on the device, encrypted; store embeddings, not photos
- Opt-in for each person; easy deletion
- Only evaluate with consenting volunteers in lab-style tests
- Check what applies under Sri Lanka's data protection law before any real-world use

**Deliverable:** Consent-based contact flow + recognition module + accuracy/false-match report.

---

### Phase 5 — Morning and Evening Routines (weeks 9–12)

**Goal:** The assistant manages the day's structure, from wake-up to bedtime.

**AI components**
- Calendar and reminders with natural language ("remind me to take the 8 am bus tomorrow")
- **Morning briefing:** today's schedule, reminders, and optionally weather and transport info
- **Evening review:** summarise the day from the timeline, mention who the user met, ask about saving new contacts, list tomorrow's schedule
- Routine learning: suggest reminders from repeated patterns (always as a suggestion, never automatic)

**Inputs / outputs**
- Input: user requests, calendar, timeline
- Output: spoken briefings and reminders at the right time

**Key design questions**
- How does the assistant know "I'm home" and "it's evening"? (Time, location, or the user saying so.)
- How long should the briefings be? (Short by default, "tell me more" on request.)
- What should it do if the user ignores a reminder?

**How to test**
- Correctness of schedule extraction from speech
- Summary quality: does the day summary match the event log, with no invented events?
- User feedback on length and usefulness

**Deliverable:** Calendar/reminder skill + morning and evening routine flows + sample summaries compared with the real logs.

---

### Phase 6 — Proactive Street Awareness (weeks 11–14)

**Goal:** The assistant speaks up on its own, but only when it matters.

**AI components**
- Local detector (small YOLO-type model) for vehicles, people, steps, poles; runs on the pocket hub without internet
- Tracking and simple motion reasoning (approaching vs. passing)
- Priority tiers:
  - **Urgent** (fast-approaching vehicle, head-height obstacle): immediate, local only
  - **Advisory** (bus ahead, steps ahead): short message
  - **Social** (known person nearby): gentle message
  - **Descriptive:** only when asked
- **Interruption manager:** cooldowns, "don't repeat", quiet when the user is in conversation, adjustable sensitivity

**Inputs / outputs**
- Input: camera stream, recognition results, context
- Output: speech and/or haptic cues, with direction

**Key design questions**
- What distance and speed thresholds trigger an alert?
- How much is too much? (Measure false alarms and user annoyance.)
- How should the assistant behave when the camera view is poor? (Say so.)

**How to test**
- Detection precision and recall on local street data
- Alert timing (is there enough warning?) and false alarm rate
- Offline test: urgent alerts must still work with the network off

**Deliverable:** Proactive monitor + interruption manager + evaluation on recorded street clips.

---

### Phase 7 — Haptics and Multi-Channel Output (weeks 12–14, overlapping)

**Goal:** Let the agent choose the best way to communicate.

**AI components**
- Output policy: speech, haptic, or both, based on urgency and environment (noisy street, in conversation)
- Haptic vocabulary (small set): left, right, ahead, distance by pulse rate, urgent
- Short spoken text that matches the haptic cue

**How to test**
- Comprehension of haptic patterns after a short learning session
- Reaction time: speech only vs. haptic only vs. both

**Deliverable:** Output policy module + haptic pattern set + comparison results.

---

### Phase 8 — Safety, Offline Behaviour, and User Testing (weeks 14–16)

**Goal:** Make it trustworthy and test it with real people.

**AI components and checks**
- **Uncertainty handling:** confidence thresholds everywhere; "I'm not sure" responses
- **Fail-safes:** audible/haptic "connection lost" or "camera blocked" warnings so the user never assumes it is still watching
- **Offline mode:** list what works with no internet (urgent alerts, saved contacts, local reminders) and what does not (rich scene descriptions)
- **Guardrails:** never claim it is safe to cross a road or walk somewhere; remind users that their cane/guide skills remain primary
- **Prompt and tool safety:** the agent must not act on instructions that appear in text it reads from signs or documents
- **Privacy review:** no raw video stored, data deletion works, clear indicator when the camera is active

**Testing**
- Controlled trials first, then supervised real-world trials
- Ethics approval and informed consent for any human participants
- Co-design sessions with visually impaired volunteers and local support organisations
- Measures: task success, response time, trust, workload (for example NASA-TLX), comfort

**Deliverable:** Safety report, user study results, and a list of limitations stated honestly.

---

## 5. Suggested Technology Choices (starting points, verify current options)

| Need | Options to evaluate |
|---|---|
| STT | Whisper-family models (local), cloud STT; test Sinhala/Tamil separately |
| TTS | Cloud TTS, on-device TTS for offline fallback |
| LLM agent | Cloud LLM with tool calling; small local model for simple offline commands |
| VLM | Cloud VLM APIs; small local VLMs for experiments |
| OCR | On-device OCR; VLM for complex layouts |
| Detector | YOLO nano/small family exported to TFLite/NCNN/ONNX (check licence) |
| Face embeddings | ArcFace-style embeddings (for example InsightFace) |
| Storage | SQLite (events, contacts, reminders) + a local vector index for memory search |
| Orchestration | Simple tool-calling loop first; add an agent framework only if needed |

---

## 6. Evaluation Summary

| Area | Metrics |
|---|---|
| Voice | Latency, word error rate, naturalness |
| Vision | Accuracy, hallucination rate, look-around turns |
| Memory | Recall accuracy, summary faithfulness |
| Face memory | Match accuracy, **false match rate** |
| Proactive alerts | Precision/recall, warning time, false alarms |
| Overall | Task success, trust, workload, battery life |

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LLM/VLM hallucination | Structured outputs, confidence thresholds, "I'm not sure" replies, never use VLM for urgent alerts |
| Wrong person recognised | High threshold, never name when unsure, consent-only storage |
| Too many interruptions | Interruption manager, user-adjustable sensitivity |
| Over-trust by users | Clear onboarding, honest limits, cane-first messaging |
| Network loss | Local urgent alerts, "connection lost" warning |
| Privacy of bystanders | Local processing, no raw video storage, opt-in contacts |
| Scope too large | Build phases in order; Phases 1–5 already form a complete day-assistant, Phase 6 onward adds street awareness |
| Sinhala/Tamil quality | Test early, report honestly, English-first with a path to local languages |

---

## 8. Open Questions to Decide

1. **Target users for the first version:** fully blind, or low-vision/cane users as your advisor suggested? (The day-assistant features can serve both; street alerts carry the most risk.)
2. **Languages:** English only for the prototype, or Sinhala from the start?
3. **Where the agent runs:** cloud LLM with local safety layer (recommended), or as local as possible?
4. **Hardware for the first demo:** phone camera and earphones, or custom glasses?
5. **Evaluation:** how many volunteers, and which organisation can help recruit them?

---

## 9. Next Steps

- [ ] Confirm the phase order and the open questions above
- [ ] Build the Phase 1 voice loop and measure latency
- [ ] Run a small VLM comparison (30 images, "find the door" prompts)
- [ ] Draft the memory data model and consent flows
- [ ] Prepare ethics and consent paperwork early
- [ ] Share progress at the Colombo builder meetup
