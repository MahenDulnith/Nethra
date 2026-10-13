# Code Implementation Plan — AI Personal Assistant for Visually Impaired Users

**Document ID:** `IMPLEMENTATION_PLAN.md`
**Revision:** 1.0
**Date:** Sunday, 11 October 2026
**Companion to:** `MASTER_SPECIFICATION.md` (revision 1.0) — that document decides **what** is built and **why**; this one decides **which files exist, what each one is responsible for, and in what order they get written**.
**Contains code:** **No.** No code blocks, no syntax, no function bodies. Interfaces are described in tables — name, inputs, outputs, errors — so a developer can implement them directly without this document guessing at their language.

---

## Table of Contents

| § | Section |
|---|---|
| 0 | How to use this document |
| 1 | The three codebases |
| 2 | Layering and dependency rules |
| 3 | Full repository tree |
| 4 | Conventions |
| 5 | Shared contracts layer — file catalogue |
| 6 | Android app — file catalogue |
| 7 | Python harness — file catalogue |
| 8 | ESP32 firmware — file catalogue |
| 9 | Configuration file schemas |
| 10 | Build sequence — S1-A (11–15 Oct) |
| 11 | Build sequence — S1-B (16–20 Oct) |
| 12 | Build sequence — S1-C (18–23 Oct) |
| 13 | Build sequence — S1-D (optional, gated 22 Oct) |
| 14 | Build sequence — S1-E / S1-F (23–29 Oct) |
| 15 | Test strategy per layer |
| 16 | Instrumentation and the latency measurement points |
| 17 | Horizon 2 — file additions per phase |
| 18 | Definition of done, per file |
| A | Appendix — file index by owner |
| B | Appendix — what deliberately has no file |

---

## 0. How to Use This Document

### 0.1 Reading order for a developer joining

1. §2 — the dependency rules. These are the only rules that, if broken, require a rewrite rather than a fix.
2. §3 — find your folder.
3. Your catalogue section (§5–§8) — find your files.
4. §10–§14 — find which day your files are due and what blocks them.
5. §18 — know what "done" means before starting.

### 0.2 What each catalogue row tells you

| Column | Meaning |
|---|---|
| **File** | Exact path, relative to the repository root |
| **Module** | Which master-spec module (M1–M11) it belongs to |
| **Responsibility** | One sentence. If a file needs two sentences, it is two files. |
| **Exposes** | The named types and operations other files are allowed to use |
| **Depends on** | Only files listed here may be imported. Anything else is a layering violation. |
| **Done when** | The specific observable behaviour that closes the file |

### 0.3 The rule that matters most

**A file may only depend on files in its own layer or a layer below it.** §2 defines the layers. Every architectural failure in the four source documents came from something high in the stack reaching down into something that must stay simple and fast — a cloud model sitting on the safety path. The dependency rules are how that is prevented mechanically rather than by remembering.

---

## 1. The Three Codebases

| Codebase | Language / platform | Runs on | Owner | Why it is separate |
|---|---|---|---|---|
| **`app/`** | Kotlin, Android | The phone (Stage 1 hub) | D (shell, adapters), A (voice/vision), B (safety) | The product. Ships. |
| **`harness/`** | Python | Laptop | E | Measures and replays. Must be able to run with **no phone and no hardware attached** — this is what makes an 18-day sprint survivable. |
| **`firmware/`** | C/C++, ESP32 | Wristbands | C | Different processor, different toolchain, different release cadence. The BLE command format (§5.4) is the only coupling. |

### 1.1 What crosses between them

Exactly three things, and nothing else:

| Crossing | Mechanism | Defined in |
|---|---|---|
| App ↔ Firmware | The BLE haptic command format — byte-identical, versioned | §5.4, §8.3 |
| App → Harness | Session recordings and structured log lines in a fixed format | §5.5, §7.3 |
| Harness → App | Recorded video/audio fixtures replayed through the fake adapters | §6.4, §7.2 |

Keeping the list this short is deliberate. The BLE format in particular is frozen early (S1-A) precisely so the firmware can stop changing while the app keeps moving.

---

## 2. Layering and Dependency Rules

### 2.1 The layers, bottom to top

```
  L0  contracts/          types, enums, schemas, error kinds        ← depends on NOTHING
  L1  adapters/           camera, audio, haptic, clock, storage     ← may use L0
  L2  services-local/     hygiene, safety-engine, arbiter, memory   ← may use L0, L1
  L3  services-cloud/     agent, vision tools, summariser           ← may use L0, L1, L2
  L4  features/           look-around, routines, people, onboarding ← may use L0..L3
  L5  app-shell/          lifecycle, power modes, wiring, UI        ← may use L0..L4
```

### 2.2 The four hard rules

| # | Rule | Why | How it is enforced |
|---|---|---|---|
| **R1** | **`L2` may never depend on `L3`.** No local service may import, reference or call anything in the cloud layer. | This is the offline guarantee made structural. If the safety engine cannot *see* the cloud layer, it cannot accidentally come to depend on it. | A module-dependency check in CI; one import-graph test that fails the build |
| **R2** | **`contracts/` depends on nothing.** No platform types, no Android types, no network types. | It is shared with the harness and conceptually with the firmware. A contract that imports a platform type cannot be reused or tested on a laptop. | CI check on the contracts module's dependency list |
| **R3** | **Wiring happens only in `L5`.** Services never construct their own dependencies; they receive them. | Lets the harness substitute a fake camera for a real one without touching any service. The whole fake-first principle rests on this. | Code review; a constructor-audit checklist item |
| **R4** | **No model of any kind in `L2`'s arbiter.** The arbiter reads thresholds from config and evaluates them. | Master spec N1 and §5.2. A learned arbiter is not auditable and not deterministic. | Review; the arbiter has no model-runtime dependency in its dependency list, checked in CI |

### 2.3 The import-graph test

One test, written in S1-A, worth more than most of the rest of the test suite:

| Aspect | Detail |
|---|---|
| **What it does** | Builds the module dependency graph and asserts the allowed-edge list from §2.1 |
| **Fails on** | Any `L2 → L3` edge; any `contracts → anything` edge; any model-runtime dependency reachable from the arbiter |
| **Why it exists** | These violations are invisible in review once the codebase is a few thousand lines, and they are the only mistakes in this project that cost a rewrite instead of a fix |
| **Owner** | D |
| **Due** | 11 Oct (foundation task F.1) |

---

## 3. Full Repository Tree

```text
ai-assistant-visually-impaired/
│
├── docs/
│   ├── MASTER_SPECIFICATION.md         # what and why — the authority
│   ├── IMPLEMENTATION_PLAN.md          # THIS FILE — which files, in what order
│   ├── decisions_log.md                # dated decisions + rationale
│   ├── results_log.md                  # every measured number + method
│   ├── interface_contracts.md          # generated from contracts/ — never hand-edited
│   ├── ethics_and_consent.md
│   ├── citations.md
│   ├── limitations.md
│   └── archive/                        # the four superseded source documents
│
├── config/                             # shared by app and harness — no code, data only
│   ├── thresholds.yaml                 # every threshold in the system
│   ├── phrasebook.yaml                 # every spoken string
│   ├── haptic_patterns.yaml            # pattern id → waveform description
│   ├── classes.yaml                    # detector class list + per-class tier hints
│   ├── model_selection.md              # which models, which versions, which licences
│   └── providers.yaml                  # cloud slots, endpoints, fallback order
│
├── contracts/                          # L0 — shared, platform-free
│   ├── frame.*                         # FrameData, LensStatus, SourceId
│   ├── audio.*                         # AudioChunk, VadState
│   ├── intent.*                        # Intent, RouteTarget, ProducedBy
│   ├── vision_result.*                 # VisionResult, DistanceBucket, CannotSeeReason
│   ├── safety_alert.*                  # SafetyAlert, Tier, DirectionSector
│   ├── haptic_command.*                # HapticCommand, PatternId, Target
│   ├── memory_record.*                 # Event, DaySummary, PrivacyClass, Source
│   ├── person_record.*                 # Person, Contact, ConsentMethod, PermissionScope
│   ├── telemetry.*                     # LinkHealth, BatteryState, FaultKind
│   ├── log_event.*                     # the structured log line format
│   └── errors.*                        # error kinds shared across layers
│
├── app/                                # Android, Kotlin — the Stage 1 product
│   ├── adapters/                       # L1
│   │   ├── camera/
│   │   │   ├── CameraSource            # the interface every source implements
│   │   │   ├── PhoneCameraSource
│   │   │   ├── UvcCameraSource         # USB-C glasses camera
│   │   │   └── FileCameraSource        # replay from MP4 — the fake
│   │   ├── audio/
│   │   │   ├── AudioIo                 # the interface
│   │   │   ├── PhoneAudioIo
│   │   │   ├── BluetoothAudioIo        # bone-conduction headset
│   │   │   └── FileAudioIo             # replay from WAV — the fake
│   │   ├── haptic/
│   │   │   ├── HapticOutput            # the interface
│   │   │   ├── BleHapticOutput
│   │   │   └── MockHapticOutput        # logs instead of vibrating — the fake
│   │   ├── clock/
│   │   │   └── MonotonicClock          # single source of timestamps
│   │   └── storage/
│   │       ├── EncryptedDatabase
│   │       └── KeystoreKeyProvider
│   │
│   ├── services/
│   │   ├── hygiene/                    # L2 — M4
│   │   │   ├── BlurScorer
│   │   │   ├── LuminanceChecker
│   │   │   ├── RedundancyFilter
│   │   │   ├── OcclusionHeuristic
│   │   │   └── FrameSelector           # the one entry point
│   │   ├── safety/                     # L2 — M5
│   │   │   ├── Detector                # interface
│   │   │   ├── QuantisedDetector       # the runtime-backed implementation
│   │   │   ├── Tracker
│   │   │   ├── GrowthEstimator         # bbox growth → time-to-contact
│   │   │   ├── DirectionMapper         # bbox centre → sector
│   │   │   ├── BucketMapper            # geometry → distance bucket
│   │   │   └── SafetyEngine            # the one entry point
│   │   ├── arbiter/                    # L2 — M6   [NO MODEL. EVER.]
│   │   │   ├── PriorityMatrix
│   │   │   ├── CooldownRegistry
│   │   │   ├── DuplicateSuppressor
│   │   │   ├── ChannelPolicy           # speech / haptic / both / silence
│   │   │   └── RuleArbiter             # the one entry point
│   │   ├── memory/                     # L2 — M7
│   │   │   ├── EventStore
│   │   │   ├── VectorIndex
│   │   │   ├── HybridRetriever         # filter first, then similarity
│   │   │   ├── PreferenceStore
│   │   │   └── MemoryService           # the one entry point
│   │   ├── agent/                      # L3 — M2
│   │   │   ├── AgentCore
│   │   │   ├── ToolRegistry
│   │   │   ├── Persona                 # loads from phrasebook.yaml
│   │   │   ├── LocalCommandClassifier  # offline fixed grammar
│   │   │   └── providers/
│   │   │       ├── MultimodalProvider  # interface — streaming voice+vision
│   │   │       ├── StreamingProvider   # primary
│   │   │       └── CascadeProvider     # VAD→STT→LLM→TTS fallback
│   │   ├── vision/                     # L3 — M3
│   │   │   ├── VisionToolset           # describe / find / read_text
│   │   │   ├── VlmClient               # interface
│   │   │   ├── SchemaValidator         # rejects non-conforming responses
│   │   │   └── OnDeviceOcr
│   │   ├── voice/                      # L3/L1 split — M1
│   │   │   ├── VadGate
│   │   │   ├── BargeInController
│   │   │   ├── OfflineTts
│   │   │   └── SpeechDispatcher        # the one speech exit point
│   │   └── routines/                   # L4 — M9
│   │       ├── ReminderParser
│   │       ├── ReminderScheduler
│   │       ├── MorningBrief
│   │       └── EveningReview
│   │
│   ├── features/                       # L4
│   │   ├── lookaround/
│   │   │   ├── LookAroundMachine        # the novelty claim
│   │   │   └── LookAroundPhrases
│   │   ├── people/                      # M8 — optional, gated
│   │   │   ├── ConsentFlow
│   │   │   ├── FaceEmbedder
│   │   │   ├── FaceMatcher
│   │   │   └── PeopleService
│   │   ├── failsafe/
│   │   │   ├── FaultDetector            # dark / blocked / link lost / low battery
│   │   │   └── FaultAnnouncer           # speech AND haptic, always both
│   │   └── onboarding/
│   │       └── CaneFirstOnboarding
│   │
│   ├── shell/                          # L5 — M10
│   │   ├── AppGraph                    # the ONLY place wiring happens
│   │   ├── PowerModeController         # Home / Street / Ask / Low-battery
│   │   ├── SessionRecorder             # writes harness-readable sessions
│   │   ├── TelemetryMonitor            # link health, battery, camera status
│   │   ├── PushToTalkController
│   │   └── ui/
│   │       ├── MainScreen              # large-type, high-contrast, minimal
│   │       └── StatusIndicators        # camera-active indicator lives here
│   │
│   └── instrumentation/
│       ├── LatencyProbe                # named measurement points (§16)
│       └── StructuredLogger
│
├── harness/                            # Python, laptop — M11
│   ├── replay/
│   │   ├── session_player              # feeds recorded video+audio to the chain
│   │   ├── session_format              # the on-disk session layout
│   │   └── fixture_builder             # turns raw clips into labelled fixtures
│   ├── bench/
│   │   ├── latency_bench               # median / p95 from probe logs
│   │   ├── detector_bench              # precision, recall, per class
│   │   ├── warning_time_bench          # alert → closest approach
│   │   ├── hallucination_bench         # includes bad + negative frames
│   │   ├── lookaround_bench            # success rate + average turns
│   │   ├── memory_recall_bench
│   │   ├── summary_faithfulness_bench  # traces every sentence to an event id
│   │   ├── falsematch_bench            # pairwise, with confidence interval
│   │   ├── offline_bench               # radio-off alert verification
│   │   └── injection_bench             # adversarial text in frame
│   ├── analysis/
│   │   ├── results_writer              # the ONLY writer of results_log.md rows
│   │   ├── confidence_interval         # so near-zero rates are reported honestly
│   │   └── traffic_inspector           # data-flow conformance vs actual traffic
│   ├── fixtures/
│   │   ├── indoor/                     # room clips + ground truth
│   │   ├── street/                     # local street clips + labels
│   │   ├── degraded/                   # blurred, dark, occluded — deliberately
│   │   ├── negative/                   # object genuinely absent
│   │   ├── injection/                  # signs and shirts with instructions
│   │   └── speech/                     # English, Sinhala, Tamil queries
│   └── tools/
│       ├── session_inspector           # step through a session frame by frame
│       └── threshold_sweeper           # sweeps thresholds.yaml, reports effect
│
├── firmware/
│   └── wristband-esp32/
│       ├── main                        # entry, mode machine
│       ├── ble_service                 # GATT service, the frozen command format
│       ├── command_decoder             # bytes → pattern request
│       ├── pattern_player              # scheduled playback, shared time base
│       ├── haptic_driver               # driver IC control
│       ├── intensity_limiter           # FIRMWARE-SIDE comfort cap
│       ├── indicators                  # LED + buzzer
│       ├── battery_monitor
│       └── side_identity               # LEFT or RIGHT, set at flash time
│
├── hardware/
│   ├── bom/                            # parts, suppliers, delivery dates
│   ├── power/                          # cell → charger → regulation → fuse → e-stop
│   └── enclosures/                     # wristband and belt-clip print sources
│
└── ci/
    ├── dependency_graph_check          # enforces R1–R4 (§2.3)
    ├── contract_sync_check             # contracts/ vs interface_contracts.md
    ├── phrasebook_lint                 # forbidden-phrase scan (N1)
    └── threshold_lint                  # every threshold referenced, none orphaned
```

### 3.1 Four structural choices worth defending

| Choice | Reason |
|---|---|
| **`contracts/` is its own top-level folder, not inside `app/`** | It is shared with the harness. Burying it in the Android project is what forces people to duplicate types, and duplicated types drift. |
| **`arbiter/` is a sibling of `safety/`, not a file inside it** | Separation makes R4 visible in the tree itself. A reviewer can see that the arbiter has no model dependency without reading any code. |
| **One entry point per service** (`FrameSelector`, `SafetyEngine`, `RuleArbiter`, `MemoryService`) | The shell wires to one object per service, not to seven. Keeps `AppGraph` readable and makes substitution for tests trivial. |
| **`config/` holds no code** | Thresholds and strings change during a sprint, often at 11pm before a demo. Having them in data files means a change is reviewable, diffable and revertable without a rebuild. |

---

## 4. Conventions

### 4.1 Naming

| Thing | Convention | Example intent |
|---|---|---|
| Interface + implementations | Interface takes the plain name; implementations prefix the source | `CameraSource` / `PhoneCameraSource`, `UvcCameraSource`, `FileCameraSource` |
| The fake implementation | Always `File…` for replay or `Mock…` for no-op | `FileAudioIo`, `MockHapticOutput` |
| Service entry point | Noun + `Service`/`Engine`/`Arbiter`/`Machine` | `MemoryService`, `SafetyEngine`, `RuleArbiter`, `LookAroundMachine` |
| Benchmarks | `<subject>_bench` | `warning_time_bench` |
| Config keys | Lowercase, dotted, grouped by subsystem | `safety.ttc.critical_seconds` |
| Phrasebook keys | `area.situation.variant` | `lookaround.guiding.turn_left` |
| Log event names | `layer.subject.verb` | `safety.alert.raised`, `arbiter.alert.suppressed` |

### 4.2 Timestamps

| Rule |
|---|
| **One clock.** `MonotonicClock` is the only source of timestamps anywhere in the app. |
| A frame's timestamp is set **at capture**, not at receipt. Every latency figure depends on this and it cannot be retrofitted. |
| Every contract that crosses a layer carries the originating frame's timestamp, so a stale answer is detectable as stale. |
| Wall-clock time is used only for the event timeline and reminders, never for latency. |

### 4.3 Errors and failure

| Rule |
|---|
| A failure in `L3` (cloud) must never propagate as a failure in `L2` (safety). Cloud failures degrade a feature; they never stop an alert. |
| Every failure that a user could mistake for "all clear" raises a fault through `FaultDetector` → `FaultAnnouncer`, which emits **speech and haptic** (N3). |
| No silent catch anywhere. A swallowed exception in this system means a user walks on believing the camera is watching. |
| Cloud schema violations are errors, not warnings: `SchemaValidator` rejects the response rather than parsing what it can. |

### 4.4 Configuration discipline

| Rule |
|---|
| No numeric threshold is written in a source file. Every one lives in `thresholds.yaml`. |
| No spoken string is written in a source file. Every one lives in `phrasebook.yaml`. |
| `threshold_lint` fails the build on a threshold referenced but undefined, or defined but unreferenced. |
| `phrasebook_lint` fails the build if any string matches the forbidden-phrase list (safety assurances — N1). |

That last one is the single cheapest safety control in the project: a build that will not compile if someone adds the sentence "it is safe to cross".

---

## 5. Shared Contracts Layer — File Catalogue (L0)

Written first, on 11 Oct, before anything else. These are platform-free data shapes with no behaviour beyond validation.

### 5.1 Sensor contracts

| File | Exposes | Fields / values | Notes |
|---|---|---|---|
| `contracts/frame.*` | `FrameData` | `bytes`, `timestampNs`, `width`, `height`, `format`, `sourceId`, `lensStatus` | `timestampNs` set **at capture** (§4.2) |
| | `SourceId` | `PHONE`, `GLASSES`, `FILE_REPLAY` | Lets a log line say which camera produced a result |
| | `LensStatus` | `OK`, `OCCLUDED`, `TOO_DARK`, `UNAVAILABLE` | Drives `FaultDetector` |
| `contracts/audio.*` | `AudioChunk` | `bytes`, `timestampNs`, `sampleRateHz`, `channels` | PCM 16 kHz 16-bit mono |
| | `VadState` | `SPEECH`, `SILENCE`, `UNKNOWN` | `UNKNOWN` exists so a VAD failure is not read as silence |

### 5.2 Decision contracts

| File | Exposes | Fields / values | Notes |
|---|---|---|---|
| `contracts/intent.*` | `Intent` | `QUICK_COMMAND`, `COMPLEX_QUERY`, `VISUAL_QUERY`, `MEMORY_QUERY`, `ROUTINE_COMMAND` | **No `SAFETY_ALERT` value.** Master spec §6.2 — safety never routes. |
| | `RouteTarget` | `LOCAL_HANDLER`, `CLOUD_AGENT` | |
| | `ProducedBy` | `FUNCTION_CALLING`, `LOCAL_CLASSIFIER`, `JEV_TRIAL` | Lets the Jev trial be measured without being trusted |
| `contracts/vision_result.*` | `VisionResult` | `found`, `directionClock?`, `distanceBucket`, `estimateBasis`, `uncertainty`, `cannotSeeReason?`, `frameTimestampNs` | **No metre field.** Master spec §6.3 |
| | `DistanceBucket` | `IMMEDIATE`, `NEAR`, `MID`, `FAR`, `UNKNOWN` | |
| | `EstimateBasis` | `BBOX_GEOMETRY`, `BBOX_GROWTH`, `VLM_REPORT` | Every distance claim carries its provenance |
| | `CannotSeeReason` | `TOO_DARK`, `BLURRED`, `OCCLUDED`, `OUT_OF_FRAME`, `NOT_PRESENT` | Maps to a phrasebook key, so the user hears *why* |
| `contracts/safety_alert.*` | `SafetyAlert` | `tier`, `objectClass`, `directionSector`, `distanceBucket`, `ttcSeconds?`, `trackAgeFrames`, `hapticPatternId`, `speechKey?`, `producedOffline`, `frameTimestampNs` | `speechKey` is a phrasebook key — **never free text on this path** |
| | `Tier` | `CRITICAL`, `ADVISORY`, `SOCIAL`, `IGNORE` | |
| | `DirectionSector` | `LEFT`, `CENTRE_LEFT`, `CENTRE`, `CENTRE_RIGHT`, `RIGHT` | Five sectors because the haptic vocabulary has three positions plus two intermediates |

### 5.3 Memory and people contracts

| File | Exposes | Fields | Notes |
|---|---|---|---|
| `contracts/memory_record.*` | `Event` | `eventId`, `timestamp`, `eventType`, `summary`, `locationLabel?`, `people[]`, `entities`, `embedding`, `privacyClass`, `source` | `source` separates stated from inferred — the fabrication audit depends on it |
| | `EventType` | `CONVERSATION`, `PLACE`, `ALERT`, `TASK`, `USER_NOTE` | |
| | `Source` | `AUTO_LOGGED`, `USER_STATED` | |
| | `PrivacyClass` | `DEVICE_ONLY`, `LIVE_REQUEST_ONLY`, `CONSENTED_SUMMARY` | |
| | `DaySummary` | `date`, `highlights`, `peopleMet[]`, `tomorrowSchedule`, `sourceEventIds[]` | `sourceEventIds` makes every summary sentence traceable |
| `contracts/person_record.*` | `Person` | `personUuid`, `alias?`, `faceEmbeddings[]`, `firstMet`, `lastSeen`, `notes`, `consentTimestamp`, `consentMethod`, `permissionScope` | **A record without `consentTimestamp` must be unconstructible.** Validation, not convention. |
| | `ConsentMethod` | `SPOKEN_CONFIRMED` | One value only, deliberately — there is no other acceptable method |
| | `PermissionScope` | `NAME_ONLY`, `FULL_PROFILE` | |

### 5.4 The haptic command contract — frozen 11 Oct

The one contract shared with a different processor and a different toolchain. It is frozen first and versioned, so firmware can stabilise while the app keeps changing.

| File | Exposes | Fields | Notes |
|---|---|---|---|
| `contracts/haptic_command.*` | `HapticCommand` | `formatVersion`, `target`, `patternId`, `intensity`, `pulseHz`, `durationMs`, `scheduledAtMs` | `formatVersion` first, so a mismatched band can refuse rather than misbehave |
| | `Target` | `LEFT`, `RIGHT`, `BOTH` | |
| | `PatternId` | `TURN_LEFT`, `TURN_RIGHT`, `FOUND`, `OBSTACLE_NEAR`, `URGENT`, `FAULT`, `LOW_BATTERY` | A small vocabulary is learnable; a large one is noise |

| Rule |
|---|
| The byte layout is written into `docs/interface_contracts.md` on 11 Oct and **does not change after S1-A** without a `formatVersion` bump and a firmware reflash of both bands. |
| `scheduledAtMs` uses a shared time base so left and right can be coordinated; the resulting offset is **measured**, target ≈15 ms. |
| `intensity` is advisory — the firmware caps it independently (§8.3). An app bug must not be able to drive a motor uncomfortably. |

### 5.5 Telemetry and logging contracts

| File | Exposes | Fields / values | Notes |
|---|---|---|---|
| `contracts/telemetry.*` | `LinkHealth` | `deviceKind`, `connected`, `lastSeenMs`, `rssi?` | Per wristband and per camera |
| | `BatteryState` | `deviceKind`, `percent`, `charging` | Hub and both bands |
| | `FaultKind` | `CAMERA_DARK`, `CAMERA_BLOCKED`, `CAMERA_LOST`, `LINK_LOST`, `LOW_BATTERY`, `DETECTOR_STALLED` | `DETECTOR_STALLED` matters: a frozen detector looks exactly like a clear road |
| `contracts/log_event.*` | `LogEvent` | `name`, `timestampNs`, `fields`, `buildId`, `sessionId` | The harness parses only this shape |
| `contracts/errors.*` | `ErrorKind` | `CLOUD_UNAVAILABLE`, `SCHEMA_INVALID`, `TIMEOUT`, `PERMISSION_DENIED`, `DEVICE_UNAVAILABLE`, `CONFIG_INVALID` | Shared so the harness can assert on failure modes |

---

## 6. Android App — File Catalogue

### 6.1 Adapters (L1)

| File | Module | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|---|
| `adapters/camera/CameraSource` | M10 | The one camera interface everything above uses | `start`, `stop`, `frames` stream, `currentLensStatus` | `contracts/frame` | Three implementations satisfy it without any caller change |
| `adapters/camera/PhoneCameraSource` | M10 | Phone camera, selectable resolution and frame rate | — | `CameraSource` | Delivers frames at a requested rate with capture-time timestamps |
| `adapters/camera/UvcCameraSource` | M10 | USB-C glasses camera as a standard USB video device | — | `CameraSource` | **Enumerates and streams on the target phone** (A.4 — the day-one risk) |
| `adapters/camera/FileCameraSource` | M11 | Replays an MP4 at a controlled rate, preserving original timestamps | `seek`, `rate` | `CameraSource` | The full chain runs on a laptop-recorded clip with no camera attached |
| `adapters/audio/AudioIo` | M1 | The one audio interface | `startCapture`, `play`, `stopPlayback`, `chunks` stream | `contracts/audio` | Barge-in can stop playback through this interface alone |
| `adapters/audio/PhoneAudioIo` | M1 | Phone mic and speaker | — | `AudioIo` | Captures and plays with capture-time timestamps |
| `adapters/audio/BluetoothAudioIo` | M1 | Bone-conduction headset routing | — | `AudioIo` | Audio routes to the headset; **falls back to phone audio within 1 s of a link drop** |
| `adapters/audio/FileAudioIo` | M11 | Replays WAV queries, captures output to file | — | `AudioIo` | A scripted spoken query produces a recorded reply, unattended |
| `adapters/haptic/HapticOutput` | M10 | The one haptic interface | `send`, `connectionState`, `connect`, `disconnect` | `contracts/haptic_command` | Identical call site for BLE and mock |
| `adapters/haptic/BleHapticOutput` | M10 | GATT client for both bands, scheduled sends | `linkHealth` per side | `HapticOutput` | Both bands receive a coordinated pattern; offset measured |
| `adapters/haptic/MockHapticOutput` | M11 | Logs commands instead of vibrating | — | `HapticOutput` | Harness asserts expected patterns with no hardware |
| `adapters/clock/MonotonicClock` | M10 | The only timestamp source | `nowNs` | — | No other file reads a system clock for latency |
| `adapters/storage/EncryptedDatabase` | M7 | Encrypted store, schema, migrations, purge | `transaction`, `purgeAll`, `vectorSearch` | `contracts/*` | A purge leaves no relational rows **and no vector entries**, verified at the storage layer |
| `adapters/storage/KeystoreKeyProvider` | M7 | Key from the hardware keystore | `key` | — | The key never appears in app storage or logs |

### 6.2 Local services (L2) — the offline core

**R1 applies to everything in this section: no file here may reference anything in `services/agent`, `services/vision` or `services/voice`'s cloud paths.**

#### Hygiene (M4)

| File | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|
| `services/hygiene/BlurScorer` | Laplacian-variance blur score for a frame | `score(frame)` | `contracts/frame` | Score separates walking-blurred from sharp frames on real footage |
| `services/hygiene/LuminanceChecker` | **Mean frame luminance, 0–255 scale**, one definition only | `meanLuminance(frame)`, `isTooDark(frame)` | `contracts/frame` | Threshold calibrated on the real camera, not borrowed |
| `services/hygiene/RedundancyFilter` | Rejects frames near-identical to the last accepted one | `isRedundant(frame)` | `contracts/frame` | Measurably reduces cloud calls during panning |
| `services/hygiene/OcclusionHeuristic` | Detects a covered or fogged lens | `isOccluded(frame)` | `contracts/frame` | A finger over the lens raises `OCCLUDED` within a few seconds |
| `services/hygiene/FrameSelector` | **Entry point.** Accept/reject with a reason; selects best recent frames for an Ask | `accept(frame)`, `bestRecent(n)` | the four above | Returns a reject reason that maps to a `CannotSeeReason` |

#### Safety engine (M5)

| File | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|
| `services/safety/Detector` | The detector interface | `detect(frame)` → boxes + classes + scores | `contracts/frame` | Swappable without touching the tracker |
| `services/safety/QuantisedDetector` | INT8 model execution on accepted frames | — | `Detector`, model runtime | Runs on the phone at the Street-mode target rate; FPS and temperature logged |
| `services/safety/Tracker` | Associates detections across frames, maintains track ids and age | `update(detections)` → tracks | `Detector` output | Track ids stay stable through brief occlusion on test clips |
| `services/safety/GrowthEstimator` | Bounding-box growth rate → time-to-contact | `ttc(track)` | `Tracker` | Returns null for a track younger than the configured minimum — **never guesses from one frame** |
| `services/safety/DirectionMapper` | Box centre → one of five sectors | `sector(box)` | `contracts/safety_alert` | Sector matches ground truth on labelled clips |
| `services/safety/BucketMapper` | Box geometry + growth → distance bucket | `bucket(track)` | `contracts/vision_result` | Buckets agree with tape-measured reality on a calibration set |
| `services/safety/SafetyEngine` | **Entry point.** Frame → zero or more candidate alerts, each with `producedOffline` set | `process(frame)` → `SafetyAlert[]` | all of the above | Produces correct tier and direction on replayed clips **with the radio off** |

#### Rule arbiter (M6) — R4 zone

| File | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|
| `services/arbiter/PriorityMatrix` | Maps class + bucket + TTC + track age → tier, purely from config | `tierFor(candidate)` | `contracts/safety_alert`, `thresholds.yaml` | The whole matrix is readable on one page and has no learned parameters |
| `services/arbiter/CooldownRegistry` | Per-class and per-tier cooldown timers | `isInCooldown`, `markFired` | `MonotonicClock` | Repeat alerts for the same hazard are suppressed; suppression is logged with a reason |
| `services/arbiter/DuplicateSuppressor` | Suppresses the same track re-alerting | `isDuplicate(alert)` | `Tracker` ids | A single approaching car produces one alert, not twelve |
| `services/arbiter/ChannelPolicy` | Chooses speech, haptic, both, or silence from tier and context | `channelsFor(alert, context)` | `thresholds.yaml` | A critical alert interrupts speech; a social one waits |
| `services/arbiter/RuleArbiter` | **Entry point.** Candidates + context → dispatch decisions | `arbitrate(candidates, context)` | the four above | Deterministic: identical input and config produce identical output, every time |

> **The arbiter's dependency list contains no model runtime, no network client and nothing from `L3`.** The CI dependency check asserts this. If it ever fails, something has gone wrong that review would not have caught.
>
> **How an alert reaches the speaker without breaking R1:** `RuleArbiter` *returns* dispatch decisions; it does not call anything to deliver them. `shell/AppGraph` subscribes to those decisions and routes them to `SpeechDispatcher` and `HapticOutput`. The arbiter therefore never holds a reference to anything that can speak, which is what keeps the `L2 → L3` edge absent. This is the one place in the codebase where the temptation to break R1 is strongest, so it is called out here explicitly rather than left to be inferred from §2.2.

#### Memory (M7)

| File | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|
| `services/memory/EventStore` | Append and query events | `append`, `queryByTime`, `queryByEntity`, `delete` | `EncryptedDatabase` | Events survive restart; deletion verified at the storage layer |
| `services/memory/VectorIndex` | Embedding storage and cosine search | `add`, `search`, `remove` | `EncryptedDatabase` | `remove` leaves no orphan vector |
| `services/memory/HybridRetriever` | **Filter by time/entity/type first, then rank by similarity** | `retrieve(query)` | `EventStore`, `VectorIndex` | Beats pure vector search on the "where did I leave my keys" fixture set |
| `services/memory/PreferenceStore` | Speech speed, verbosity, language, alert sensitivity, briefing style | `get`, `set`, `observe` | `EncryptedDatabase` | A preference change takes effect without a restart |
| `services/memory/MemoryService` | **Entry point.** Logging, recall, forget, retention expiry | `logEvent`, `recall`, `forget`, `expireOld` | the four above | `forget` removes rows **and** vectors; retention expiry runs unattended |

### 6.3 Cloud services (L3)

| File | Module | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|---|
| `services/agent/providers/MultimodalProvider` | M2 | The provider interface — streaming audio in/out plus keyframes | `openSession`, `sendAudio`, `sendKeyframe`, `interrupt`, `close` | `contracts/*` | Both providers satisfy it; switching is a config change |
| `services/agent/providers/StreamingProvider` | M2 | Primary real-time multimodal path | — | `MultimodalProvider` | Median and p95 response latency logged |
| `services/agent/providers/CascadeProvider` | M2 | VAD → STT → LLM → TTS fallback | — | `MultimodalProvider` | Works as the demo path if streaming is unreliable |
| `services/agent/ToolRegistry` | M2 | Declares the callable tools and validates their arguments | `tools`, `invoke` | `services/vision`, `services/memory`, `services/routines` | An unknown or malformed tool call is rejected, not guessed |
| `services/agent/Persona` | M2 | Builds the system prompt from `phrasebook.yaml`; enforces reply length and forbidden phrasing | `systemPrompt`, `shape(reply)` | `phrasebook.yaml` | No forbidden safety-assurance phrasing can be produced; brevity respected |
| `services/agent/LocalCommandClassifier` | M2 | Fixed offline grammar: stop, what's in front, remind me, quieter, forget that | `classify(text)` → `Intent` | `contracts/intent` | Works with the radio off |
| `services/agent/AgentCore` | M2 | Dialogue orchestration and tool routing via function calling | `handle(utterance)` | all of the above | A visual question reaches the vision toolset and returns a spoken answer |
| `services/vision/VlmClient` | M3 | Cloud VLM interface, schema-constrained requests | `describe`, `find`, `readHard` | `contracts/vision_result` | Two providers behind one interface |
| `services/vision/SchemaValidator` | M3 | **Rejects** any response not conforming to `VisionResult` | `validate(response)` | `contracts/vision_result` | A malformed response produces an honest "I'm not sure", never a parsed guess |
| `services/vision/OnDeviceOcr` | M3 | Local text recognition, tried first | `readText(frame)` | `contracts/frame` | Printed text reads **offline** |
| `services/vision/VisionToolset` | M3 | `describe_scene`, `find_object`, `read_text`; OCR-first escalation | the three tools | `FrameSelector`, `VlmClient`, `OnDeviceOcr`, `SchemaValidator` | Each tool returns a valid `VisionResult` or an honest failure |
| `services/voice/VadGate` | M1 | Voice activity detection over captured chunks | `state` stream | `AudioIo` | Produces `UNKNOWN` rather than `SILENCE` on failure |
| `services/voice/BargeInController` | M1 | Stops playback on user speech onset, locally, with no network round trip | `arm`, `disarm` | `VadGate`, `AudioIo` | Playback stops on speech onset; the delay is measured |
| `services/voice/OfflineTts` | M1 | On-device speech for alerts and faults | `speak(text)` | `AudioIo` | Fault announcements speak with the radio off |
| `services/voice/SpeechDispatcher` | M1 | **The single exit point for all speech**, with priority and interruption | `say(key, priority)`, `stop` | `OfflineTts`, cloud TTS, `phrasebook.yaml` | A critical alert interrupts an in-progress sentence |

> **Why `SpeechDispatcher` is a single choke point:** it is the only place that can enforce "a critical alert interrupts everything else", and the only place a reviewer has to read to confirm that nothing bypasses the phrasebook.

### 6.4 Features (L4)

| File | Module | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|---|
| `features/lookaround/LookAroundMachine` | M3 | The six-state guided search: `SEARCHING`, `GUIDING`, `FOUND`, `NOT_VISIBLE`, `BLOCKED`, `TIMEOUT` | `start(target)`, `state` stream, `cancel` | `VisionToolset`, `HapticOutput`, `SpeechDispatcher`, `thresholds.yaml` | **Always terminates.** Completes, times out, or reports blocked — never hangs with the user still turning |
| `features/lookaround/LookAroundPhrases` | M3 | Binds each state to phrasebook keys | `phraseFor(state)` | `phrasebook.yaml` | Wording reviewed by A and E before use |
| `features/people/ConsentFlow` | M8 | Post-conversation prompt, spoken consent capture, enrolment | `offerSave`, `enrol` | `MemoryService`, `SpeechDispatcher` | **No consent, no record** — not even a partial or pending one |
| `features/people/FaceEmbedder` | M8 | Embeddings from frames; discards crops immediately | `embed(frame)` | `contracts/person_record` | No image or crop persists anywhere after the call returns |
| `features/people/FaceMatcher` | M8 | Thresholded matching: high → name, medium → "someone you may know", low → silence | `match(embedding)` | `VectorIndex`, `thresholds.yaml` | A non-enrolled person produces **silence**, verified |
| `features/people/PeopleService` | M8 | Entry point: enrol, recognise, forget | `enrol`, `recognise`, `forget` | the three above | `forget [name]` purges embeddings and contact, verified in storage |
| `features/failsafe/FaultDetector` | M10 | Watches lens status, link health, battery, **and detector liveness** | `faults` stream | `contracts/telemetry` | Each fault raises within a few seconds of its condition |
| `features/failsafe/FaultAnnouncer` | M10 | Announces every fault by **speech and haptic, both, always** | — | `SpeechDispatcher`, `HapticOutput` | Distinct haptic pattern per fault; verified blindfolded |
| `features/onboarding/CaneFirstOnboarding` | M2 | The cane-first message on first launch | `showIfFirstRun` | `SpeechDispatcher`, `PreferenceStore` | Plays on first use of every install |
| `services/routines/ReminderParser` | M9 | Natural language → structured reminder, read back for confirmation | `parse(text)` | `AgentCore` | A recurring reminder is read back before it is saved |
| `services/routines/ReminderScheduler` | M9 | Local scheduling, firing, snooze, repeat | `schedule`, `cancel`, `snooze` | OS scheduler, `EncryptedDatabase` | Reminders fire **offline**; snooze does not lose an alert |
| `services/routines/MorningBrief` | M9 | Schedule + reminders + device status, short by default | `generate` | `MemoryService`, `ReminderScheduler` | Under the configured length; expands on "tell me more" |
| `services/routines/EveningReview` | M9 | Day summary from the event log, people met, tomorrow | `generate` | `MemoryService`, `AgentCore` | Every sentence traces to a `sourceEventId` — **zero fabricated events** |

### 6.5 Shell (L5) — M10

| File | Responsibility | Exposes | Depends on | Done when |
|---|---|---|---|---|
| `shell/AppGraph` | **The only place dependencies are wired.** Chooses real or fake adapters from a build flag | `build(config)` | everything | Swapping to fakes requires changing one flag and no other file |
| `shell/PowerModeController` | Home / Street / Ask / Low-battery; starts and stops camera and detector per mode | `mode`, `setMode`, `observe` | `CameraSource`, `SafetyEngine`, `BatteryState` | Mode switches work and are announced; per-mode battery use measured |
| `shell/SessionRecorder` | Writes a harness-readable session: frames, audio, log events, decisions | `startRecording`, `stop` | `contracts/log_event` | A recorded session replays in the harness and reproduces the same decisions |
| `shell/TelemetryMonitor` | Collects link health, battery and camera status into one observable state | `telemetry` stream | `contracts/telemetry` | Feeds `FaultDetector` and the status indicators |
| `shell/PushToTalkController` | Push-to-talk and mute; opens an Ask session | `press`, `release`, `muted` | `AudioIo`, `AgentCore`, `PowerModeController` | Usable without sight; no accidental activation |
| `shell/ui/MainScreen` | Minimal large-type, high-contrast screen; mode, status, transcript | — | `PowerModeController`, `TelemetryMonitor` | Usable by a low-vision user; nothing essential is screen-only |
| `shell/ui/StatusIndicators` | **The camera-active indicator** plus link and battery state | — | `TelemetryMonitor` | Camera-active is unambiguous on screen **and** reinforced by periodic audio |

### 6.6 Instrumentation

| File | Responsibility | Exposes | Done when |
|---|---|---|---|
| `instrumentation/LatencyProbe` | Named probe points (§16) emitting timestamped marks | `mark(name, frameTimestampNs)` | Every probe in §16 is emitted at least once in a real session |
| `instrumentation/StructuredLogger` | The one logger; emits `LogEvent` shapes only | `log(event)` | The harness parses a full session with no unparseable lines |

---

## 7. Python Harness — File Catalogue (M11)

Owner E. **Must run with no phone and no hardware attached.** This is what allows measurement to start on 11 Oct, before any parts arrive.

### 7.1 Replay

| File | Responsibility | Exposes | Done when |
|---|---|---|---|
| `harness/replay/session_format` | The on-disk session layout: video, audio, log events, decisions, build id | `read`, `write`, `validate` | A session written by the app reads here without conversion |
| `harness/replay/session_player` | Feeds a recorded session through the chain at a controlled rate | `play`, `step`, `seek` | A street clip produces the same alerts as it did on the phone |
| `harness/replay/fixture_builder` | Turns raw clips into labelled fixtures with ground truth | `build`, `label`, `verify` | Each fixture carries its ground truth and its consent note |

### 7.2 Benchmarks

| File | Measures | Reports | Fixtures |
|---|---|---|---|
| `bench/latency_bench` | Probe-point deltas across the chain | **Median and p95 per segment and total**, never a mean alone | any session |
| `bench/detector_bench` | Precision and recall per class | With denominators per class | `street/`, `indoor/` |
| `bench/warning_time_bench` | Alert time → closest approach | Distribution, not an average | `street/` |
| `bench/hallucination_bench` | Claims about things not present | Rate **on a set including `degraded/` and `negative/`** | `degraded/`, `negative/` |
| `bench/lookaround_bench` | Find-X success and turns needed | Success rate **and average turns**, ≥6 rooms | `indoor/` |
| `bench/memory_recall_bench` | Recall accuracy on a scripted day | Accuracy with denominator | scripted events |
| `bench/summary_faithfulness_bench` | Summary sentences vs `sourceEventIds` | **Count of unsupported sentences — a hard fail, not an average** | scripted events |
| `bench/falsematch_bench` | Face false-match rate | **Pairwise rate with a confidence interval** | consented volunteer set |
| `bench/offline_bench` | Urgent alerts with the radio off | **Pass/fail per alert type** | `street/` |
| `bench/injection_bench` | Whether text in frame changes behaviour | Results **and known issues** — never "immune" | `injection/` |

### 7.3 Analysis

| File | Responsibility | Done when |
|---|---|---|
| `analysis/results_writer` | **The only writer of `results_log.md` rows**, enforcing metric, value, method, trials, build, date | A row missing its method cannot be written |
| `analysis/confidence_interval` | Intervals for rates, especially near zero | Reproduces the "25 trials bounds error below ~12%" result |
| `analysis/traffic_inspector` | Compares observed network traffic against the §10.1 data classes | Any `DEVICE_ONLY` data leaving the device is flagged as a defect |

> `results_writer` being the only path into the results log is what makes "no number on a slide without a method" enforceable rather than aspirational.

### 7.4 Tools

| File | Responsibility | Done when |
|---|---|---|
| `tools/session_inspector` | Step through a session frame by frame with detections, tracks, TTC and arbiter decisions visible | A false alarm can be traced to the frame and rule that produced it |
| `tools/threshold_sweeper` | Sweeps values in `thresholds.yaml` and reports the effect on alerts | Produces a false-alarm-vs-warning-time trade-off curve |

`threshold_sweeper` is the file most likely to be skipped and most likely to be missed later: tuning alert thresholds by intuition is how a project ends up with either a chattering device or a silent one.

### 7.5 Fixtures

| Directory | Contents | Minimum for the sprint |
|---|---|---|
| `fixtures/indoor/` | Room clips + ground truth for find-X | **6 rooms** (B.9) |
| `fixtures/street/` | Local street clips, labelled: three-wheelers, motorcycles on footpaths, buses, pedestrians, poles | Enough for a false-alarms-per-15-minutes figure |
| `fixtures/degraded/` | Deliberately blurred, dark, occluded | Enough to exercise every `CannotSeeReason` |
| `fixtures/negative/` | Target genuinely absent | Required — a hallucination rate without these is meaningless |
| `fixtures/injection/` | Signs, posters, shirts carrying instructions | A handful, including a safety-assurance instruction |
| `fixtures/speech/` | Spoken queries in English, Sinhala, Tamil | Enough for a WER figure in each (A.9) |

Every fixture carries a consent note. Street footage with identifiable bystanders is treated as `DEVICE_ONLY` source material.

---

## 8. ESP32 Firmware — File Catalogue

Owner C. Frozen early so it stops changing while the app does not.

| File | Responsibility | Exposes / behaviour | Done when |
|---|---|---|---|
| `firmware/.../main` | Entry; boot, self-test, mode machine: idle, connected, fault, low-battery | — | Boots into a known state; self-test result shown on LED and buzzer |
| `firmware/.../ble_service` | GATT service implementing the frozen command format; advertises side identity | `formatVersion` negotiation | Rejects a mismatched `formatVersion` **audibly**, rather than misbehaving silently |
| `firmware/.../command_decoder` | Bytes → pattern request; validates every field | — | A malformed packet is dropped and counted, never played |
| `firmware/.../pattern_player` | Plays patterns on a shared time base so left and right coordinate | `play(request)`, `cancel` | Left/right offset measured; target ≈15 ms |
| `firmware/.../haptic_driver` | Driver IC control for the LRA | — | Crisp start and stop; patterns distinguishable blindfolded |
| `firmware/.../intensity_limiter` | **Firmware-side comfort cap, independent of the app** | — | An app sending maximum intensity cannot exceed the cap |
| `firmware/.../indicators` | LED and buzzer: power, link, battery, fault | — | Each state visually and audibly distinct |
| `firmware/.../battery_monitor` | Cell voltage → percent; low-battery pattern and report to the hub | — | Low battery announced on the band **and** at the hub |
| `firmware/.../side_identity` | LEFT or RIGHT, set at flash time, reported on connect | — | The hub cannot confuse the two; verified by swapping bands |

### 8.3 Firmware rules

| Rule | Why |
|---|---|
| The intensity cap lives in firmware, not in the app | A software bug on the phone must not be able to make a motor uncomfortable on someone's wrist |
| Side identity is set at flash time and reported on connect, never inferred | A directional cue delivered to the wrong wrist is worse than no cue |
| A malformed or version-mismatched packet is dropped **and reported**, never interpreted | Silent reinterpretation is how a "turn left" becomes an "urgent" |
| Both bands are flashed from the same source with one build flag differing | Divergent firmware is how a left/right asymmetry appears and takes a day to find |

---

## 9. Configuration File Schemas

Data, not code. Shared by the app and the harness, which is why they live outside both.

### 9.1 `config/thresholds.yaml`

Every numeric threshold in the system. Described by key group, not by value — **the values are set by measurement, not by this document.**

| Key group | Keys | Set by |
|---|---|---|
| `hygiene.blur` | `min_laplacian_variance` | Tuned on real walking footage (§6.2) |
| `hygiene.darkness` | `min_mean_luminance` (0–255 scale) | Calibrated on the actual camera |
| `hygiene.redundancy` | `min_frame_difference`, `min_interval_ms` | Tuned against cloud-call reduction |
| `hygiene.occlusion` | `max_edge_density`, `persist_frames` | Tuned with a finger over the lens |
| `safety.detector` | `input_width`, `input_height`, `target_fps_street`, `min_confidence` | Measured on the phone |
| `safety.tracker` | `max_age_frames`, `min_hits`, `iou_match_threshold` | Tuned on street clips |
| `safety.ttc` | `min_track_age_frames`, `critical_seconds`, `advisory_seconds` | **`min_track_age_frames` is the honesty control** — below it, TTC is null |
| `safety.buckets` | `immediate_ratio`, `near_ratio`, `mid_ratio` | Calibrated against tape-measured reality |
| `arbiter.cooldowns` | per tier and per class, in ms | Tuned against false-alarms-per-15-minutes |
| `arbiter.sensitivity` | `levels`, `default_level` | User-adjustable at runtime |
| `arbiter.context` | `suppress_while_user_speaking`, `suppress_in_conversation` | Behavioural, reviewed with users |
| `people.matching` | `high_confidence`, `medium_confidence` | **Set high.** A wrong name is the worst social failure |
| `lookaround` | `max_turns`, `turn_timeout_ms`, `total_timeout_ms` | Tuned in the 6-room test |
| `voice` | `barge_in_ms`, `max_reply_sentences`, `thinking_tone_after_ms` | Measured and reviewed |
| `power` | `low_battery_percent`, `street_fps`, `home_camera_off` | Measured per mode |
| `haptic` | `max_intensity_app_side`, `pulse_hz_by_bucket` | Firmware caps independently |

### 9.2 `config/phrasebook.yaml`

Every spoken string, so N1 compliance can be audited by reading one file.

| Key group | Covers |
|---|---|
| `onboarding.*` | Cane-first message, first-run explanation |
| `lookaround.*` | One entry per state: searching, guiding left/right, found, not visible, blocked, timeout |
| `vision.*` | Describe preamble, cannot-see reasons (one per `CannotSeeReason`), uncertainty |
| `safety.*` | One per tier and direction combination; **short, because these interrupt** |
| `fault.*` | Camera dark, camera blocked, camera lost, link lost, low battery, detector stalled |
| `people.*` | Consent prompt to the user, consent request wording for the other person, high/medium/low responses, forget confirmation |
| `routines.*` | Morning brief frame, evening review frame, reminder read-back |
| `offline.*` | What is unavailable and why — **honest, not apologetic** |
| `_forbidden` | The deny-list `phrasebook_lint` scans for: any form of safety assurance |

The `_forbidden` list is the reason this file exists as data. A build that fails when someone writes "it is safe to cross" is a stronger guarantee than a review culture that remembers not to.

### 9.3 `config/haptic_patterns.yaml`

| Per pattern id | Fields |
|---|---|
| `TURN_LEFT`, `TURN_RIGHT`, `FOUND`, `OBSTACLE_NEAR`, `URGENT`, `FAULT`, `LOW_BATTERY` | `pulse_count`, `pulse_ms`, `gap_ms`, `intensity`, `repeat`, `description` |

The `description` field is for the demo script and the comprehension test — a pattern nobody can describe in words is a pattern nobody will learn.

### 9.4 `config/classes.yaml`

| Per class | Fields |
|---|---|
| `car`, `motorcycle`, `three_wheeler`, `bus_truck`, `bicycle`, `person`, `pole_post`, `large_static_obstacle` | `detector_label`, `base_tier`, `is_dynamic`, `min_confidence` |

> This file is also the honest limits statement: **drop-offs, holes, kerbs and step edges are not in it**, and the slide that says so points here.

### 9.5 `config/providers.yaml`

| Per slot | Fields |
|---|---|
| `multimodal`, `vlm`, `stt`, `tts`, `summariser` | `primary`, `fallback`, `endpoint`, `timeout_ms`, `max_retries`, `retention_policy_note` |

`retention_policy_note` is required per provider, so §15's record of what each vendor keeps lives next to the configuration that sends it there.

---

## 10. Build Sequence — Phase S1-A (11–15 Oct)

**Goal:** the thin vertical slice exists, on recorded clips if necessary, and the 15 Oct evaluation has honest measured numbers.

### 10.1 Day 1 — Sunday 11 October (foundation)

Nothing else can be measured until this day is finished, which is why it is one day and not two weeks.

| Step | Files created | Owner | Blocks | Done when |
|---|---|---|---|---|
| **A1.1** | Repository, module skeleton, build config for all three codebases | D | everything | All three build empty and CI runs |
| **A1.2** | `ci/dependency_graph_check` | D | — | **Fails on a deliberately added `L2 → L3` import**, then passes when removed |
| **A1.3** | All of `contracts/` (§5) | D | all services | Compiles in app and harness; `interface_contracts.md` generated |
| **A1.4** | `contracts/haptic_command` byte layout **frozen** and documented | D, C | firmware | Written into `interface_contracts.md`; C can start firmware against it |
| **A1.5** | `adapters/clock/MonotonicClock` | D | all timing | Single clock in use; no other time source anywhere |
| **A1.6** | `config/thresholds.yaml`, `phrasebook.yaml`, `classes.yaml`, `haptic_patterns.yaml`, `providers.yaml` — sparse but real | A, B | all services | Read at runtime, not hard-coded |
| **A1.7** | `ci/threshold_lint`, `ci/phrasebook_lint` | E | — | `phrasebook_lint` **fails on a planted "it is safe to cross"** |
| **A1.8** | `adapters/camera/FileCameraSource`, `adapters/audio/FileAudioIo`, `adapters/haptic/MockHapticOutput` | D | all testing | Chain runs on a laptop with nothing attached |
| **A1.9** | `harness/replay/session_format`, `session_player` | E | all benchmarks | Replays a clip through the fakes |
| **A1.10** | `analysis/results_writer` + first row in `results_log.md` | E | every number | A row without a method is rejected |
| **A1.11** | `adapters/camera/UvcCameraSource` — **the day-one risk test** | D | the whole camera path | **USB camera enumerates as UVC and streams on the target phone**; result recorded pass or fail |
| **A1.12** | USB tether + charging coexistence test (no new file; a recorded result) | D, C | demo length | Result recorded; if it fails, a powered hub is sourced today |
| **A1.13** | `shell/AppGraph` with a real/fake build flag | D | all wiring | Flipping one flag switches the whole chain to fakes |

> **A1.11 and A1.12 are deliberately on day one.** If the glasses camera will not enumerate on the chosen phone, every downstream plan changes — and finding that out on 20 October instead of 11 October is the difference between a changed plan and a failed demo.

### 10.2 Day 2 — Monday 12 October (the thin slice)

| Step | Files created | Owner | Depends on | Done when |
|---|---|---|---|---|
| **A2.1** | `services/hygiene/BlurScorer`, `LuminanceChecker`, `FrameSelector` | B | A1.3, A1.6 | A blurred and a dark frame are both rejected with correct reasons |
| **A2.2** | `services/safety/Detector`, `QuantisedDetector` | B | A2.1 | Runs on recorded street clips; **FPS and phone temperature recorded** (A.5) |
| **A2.3** | `services/safety/Tracker`, `GrowthEstimator` | B | A2.2 | Track ids stable; TTC **null below `min_track_age_frames`** |
| **A2.4** | `services/safety/DirectionMapper`, `BucketMapper`, `SafetyEngine` | B | A2.3 | Correct tier and direction on replayed clips |
| **A2.5** | `services/arbiter/PriorityMatrix`, `CooldownRegistry`, `DuplicateSuppressor`, `ChannelPolicy`, `RuleArbiter` | B | A2.4 | One approaching car produces **one** alert; suppression logged with a reason |
| **A2.6** | `firmware/.../main`, `ble_service`, `command_decoder`, `haptic_driver`, `intensity_limiter`, `indicators` | C | A1.4 | **Motor vibrates on command from the phone** (A.7) |
| **A2.7** | `adapters/haptic/BleHapticOutput` | D | A2.6 | App drives the band; link health reported |
| **A2.8** | `instrumentation/LatencyProbe`, `StructuredLogger` | D | A1.5 | Probe marks appear in a session the harness can parse |
| **A2.9** | E-stop and fuse built for the demo unit (hardware, no file) | C | — | **E-stop verified to cut power** (A.8) |

**End of day 2 is the thin slice:** frame → hygiene → detector → tracker → arbiter → wristband, running on recorded clips. It is the most important milestone in the sprint, and it exists on day 2 rather than week 11 because that is the correction the master spec makes to the original plans.

### 10.3 Day 2–3 — the voice and vision slice (parallel)

| Step | Files created | Owner | Done when |
|---|---|---|---|
| **A3.1** | `adapters/audio/AudioIo`, `PhoneAudioIo` | A | Captures and plays with capture-time timestamps |
| **A3.2** | `services/voice/VadGate`, `BargeInController` | A | Playback stops on speech onset; delay measured |
| **A3.3** | `services/agent/providers/MultimodalProvider`, `StreamingProvider` | A | Voice question → spoken answer (A.2) |
| **A3.4** | `services/agent/providers/CascadeProvider` | A | **Works as the demo path** if streaming is unreliable |
| **A3.5** | `services/agent/Persona` | A | Replies within the length limit; no forbidden phrasing possible |
| **A3.6** | `services/voice/SpeechDispatcher`, `OfflineTts` | A | All speech exits here; a critical alert interrupts mid-sentence |
| **A3.7** | `services/vision/VlmClient`, `SchemaValidator`, `OnDeviceOcr`, `VisionToolset` | A | Describe / find / read text work on the phone camera (A.3) |
| **A3.8** | `services/agent/ToolRegistry`, `AgentCore` | A | A spoken visual question reaches the toolset and returns an answer |
| **A3.9** | `bench/latency_bench`, `detector_bench` | E | Median and p95 in the results log |
| **A3.10** | `fixtures/speech/` + Sinhala/Tamil WER spot-benchmark | A, E | **Three WER figures published, whatever they are** (A.9) |

### 10.4 Days 3–4 — Tuesday 13 / Wednesday 14 October (evaluation prep)

| Step | Work | Owner | Done when |
|---|---|---|---|
| **A4.1** | `fixtures/street/`, `degraded/`, `negative/` populated from recorded clips | E | Enough for a hallucination rate and a false-alarm figure |
| **A4.2** | `bench/hallucination_bench`, `warning_time_bench` | E | Rates in the results log, with denominators |
| **A4.3** | `tools/session_inspector` | E | A false alarm traceable to the frame and the rule |
| **A4.4** | Numbers slide, built **only** from `results_log.md` | E | Every figure traces to a logged row (A.11) |
| **A4.5** | Pitch and one-page safety position | E | Reviewed by the whole team (A.10) |
| **A4.6** | Backup demo video | E | Saved on two devices (A.12) |
| **A4.7** | Two dry runs | All | Timed and rehearsed (A.13) |

### 10.5 Day 5 — Thursday 15 October

| Step | Work |
|---|---|
| **A5.1** | 1st evaluation. Demo the thin slice honestly, state what is recorded-clip versus live. |
| **A5.2** | **Log every piece of feedback in `decisions_log.md` the same day**, while the wording is still remembered accurately. |

### 10.6 S1-A exit condition

| Must be true on 15 Oct |
|---|
| Thin slice exists: frame → hygiene → detector → tracker → arbiter → one wristband |
| Voice question → spoken answer works, on at least one of the two provider paths |
| Describe / find / read text work on the phone camera |
| Camera UVC and charging-coexistence questions are **answered**, pass or fail |
| E-stop verified to cut power |
| `results_log.md` has real rows with methods; the numbers slide uses only those rows |
| Dependency check, threshold lint and phrasebook lint all run in CI |

---

## 11. Build Sequence — Phase S1-B (16–20 Oct)

**Goal:** the novelty feature works, both bands work, and the system fails visibly.

| Step | Files created / changed | Owner | Depends on | Done when |
|---|---|---|---|---|
| **B1.1** | `features/lookaround/LookAroundPhrases` + the wording for all six states in `phrasebook.yaml` | A, E | A1.6 | Wording written and agreed **before** the state machine (B.1) |
| **B1.2** | `features/lookaround/LookAroundMachine` | A | A3.7, B1.1 | **Always terminates** — completes, times out, or reports blocked (B.2) |
| **B1.3** | Haptic steering integration in `LookAroundMachine` | A, C | A2.7 | **Correct wrist vibrates** for turn-left and turn-right (B.3) |
| **B1.4** | `firmware/.../pattern_player` scheduled playback; `side_identity` | C | A1.4 | Left/right offset **measured**, target ≈15 ms (B.4) |
| **B1.5** | Second band assembled, flashed, tactually distinguishable | C | B1.4 | **Verified blindfolded** (B.5) |
| **B1.6** | `features/failsafe/FaultDetector` | D | A1.3, `TelemetryMonitor` | Each of the five faults raises within a few seconds (B.6) |
| **B1.7** | `features/failsafe/FaultAnnouncer` | D | A3.6, A2.7 | Every fault announced by **speech and haptic, both** |
| **B1.8** | `services/hygiene/OcclusionHeuristic`, `RedundancyFilter` | B | A2.1 | Lens-cover raises `OCCLUDED`; cloud-call reduction measured |
| **B1.9** | `shell/TelemetryMonitor`, `PowerModeController` (Home, Street) | D | A1.13 | Mode switching works; **per-mode battery use measured** (B.7) |
| **B1.10** | `features/onboarding/CaneFirstOnboarding` | A | A3.6 | Plays on first use of a fresh install (B.8) |
| **B1.11** | `adapters/audio/BluetoothAudioIo` | A | A3.1 | Routes to the bone-conduction headset; **falls back to phone audio within 1 s** of a drop |
| **B1.12** | `shell/PushToTalkController` | D | A3.8 | Usable without sight; no accidental activation |
| **B1.13** | `fixtures/indoor/` — **6 rooms** with ground truth | E | A1.9 | Six rooms labelled |
| **B1.14** | `bench/lookaround_bench` | E | B1.13 | **Success rate and average turns** logged (B.9) |
| **B1.15** | `fixtures/injection/` + `bench/injection_bench` | A, E | A3.7 | Results **and known issues** recorded — never "immune" (B.10) |
| **B1.16** | `tools/threshold_sweeper` | E | A2.5 | Produces a false-alarm-vs-warning-time curve |
| **B1.17** | `shell/ui/MainScreen`, `StatusIndicators` | D | B1.9 | **Camera-active indicator unambiguous**, on screen and by periodic audio |

### 11.1 S1-B exit condition

| Must be true on 20 Oct |
|---|
| Look-around loop runs end to end with haptic steering and always terminates |
| Both bands work, are distinguishable by touch, offset measured |
| All five faults announce by speech and haptic |
| Home and Street modes switch, with measured battery use |
| Six-room look-around results in the results log |
| Injection test results and known issues documented |

---

## 12. Build Sequence — Phase S1-C (18–23 Oct)

**Overlaps S1-B deliberately.** Integration always takes longer than planned; starting it while core work finishes is how that is discovered with time left to react.

| Step | Files created / changed | Owner | Depends on | Done when |
|---|---|---|---|---|
| **C1.1** | `UvcCameraSource` promoted to the live source behind the adapter | D, B | A1.11 | **Safety engine runs on the glasses feed** (C.1) |
| **C1.2** | Full-chain wiring in `AppGraph`: camera → hygiene → safety → arbiter → speech + haptics | B, C, D | all of S1-A, S1-B | **Alerts reach the correct wrist on real hardware** (C.2) |
| **C1.3** | All §16 probe points emitted on the real chain | D, E | A2.8 | Every probe appears in a real session |
| **C1.4** | `bench/latency_bench` run on real hardware | E | C1.3 | **Median and p95 glass-to-haptic, with method, in the results log** (C.3) |
| **C1.5** | `shell/SessionRecorder` | D | A1.9 | A recorded session replays in the harness and **reproduces the same decisions** |
| **C1.6** | 60-minute continuous run; temperature, battery, frame rate logged | C, E | C1.2 | No shutdown; full curves logged (C.4) |
| **C1.7** | `bench/offline_bench` on real hardware, radio off | B | C1.2 | **Every urgent alert type passes with the radio off** (C.5) |
| **C1.8** | `FaultDetector` detector-liveness check (`DETECTOR_STALLED`) | D | B1.6 | A stalled detector raises a fault rather than looking like a clear road |
| **C1.9** | `analysis/traffic_inspector` run across all modes | E | C1.2 | Data-flow conformance verified against **actual traffic** |
| **C1.10** | Controlled demo course built and rehearsed | E, C | C1.2 | Rehearsed with teammates (C.6) |
| **C1.11** | `PowerModeController`: Ask and Low-battery modes | D | B1.9 | All four modes switch correctly |
| **C1.12** | Fix the biggest problems; log every decision | All | — | Issues closed or **explicitly listed in `limitations.md`** (C.7) |

> **C1.8 deserves its own row rather than hiding inside the fault work.** A detector that has silently stopped producing output is indistinguishable, to the user, from a road with nothing on it. That is the most dangerous failure mode in the system, and it is a failure mode no source document mentioned.

### 12.1 S1-C exit condition — and the 22 Oct gate

| Must be true on 22 Oct for S1-D to proceed |
|---|
| Full chain runs on real hardware, alerts reaching the correct wrist |
| Measured glass-to-haptic latency in the results log, with method |
| 60-minute run completed without shutdown |
| Offline alerts pass with the radio off |
| No open defect that could break the demo |

**If any of these is false, S1-D is dropped** and the effort goes into reliability. This is the decision the gate exists to make, and it is made on evidence rather than appetite.

---

## 13. Build Sequence — Phase S1-D (optional, gated 22 Oct)

Only if §12.1 passes. Everything here is in the should-have column, not the must-have column.

| Step | Files created | Owner | Done when |
|---|---|---|---|
| **D1.1** | `services/memory/EventStore`, `VectorIndex`, `HybridRetriever`, `PreferenceStore`, `MemoryService` | D | Events survive restart; `forget` removes rows **and** vectors |
| **D1.2** | `adapters/storage/EncryptedDatabase`, `KeystoreKeyProvider` | D | Key never appears in app storage or logs |
| **D1.3** | `bench/memory_recall_bench` + a scripted day fixture | E | **20+ recall questions** tested, accuracy logged (D.1) |
| **D1.4** | `features/people/ConsentFlow` + consent wording in `phrasebook.yaml` | D, A, E | Spoken consent works end to end; **no consent, no record** (D.2) |
| **D1.5** | `features/people/FaceEmbedder` | D | **No image or crop persists** after the call returns |
| **D1.6** | `features/people/FaceMatcher`, `PeopleService` | D | A non-enrolled person produces **silence** (D.3) |
| **D1.7** | `forget [name]` path verified at the storage layer | D | Deletion confirmed in the database, not just the UI (D.4) |
| **D1.8** | `bench/falsematch_bench` + `analysis/confidence_interval` | E | **Pairwise false-match rate with a confidence interval** |
| **D1.9** | `services/routines/EveningReview` + `bench/summary_faithfulness_bench` | D, E | **Zero unsupported summary sentences**, traced by `sourceEventIds` |

> If S1-D is dropped, `features/people/` and `services/memory/` simply do not exist in the 29 Oct build, and the demo script never mentions them. A dropped feature that is still half-wired into `AppGraph` is how a demo crashes, so dropping means removing the wiring, not disabling a flag.

---

## 14. Build Sequence — Phases S1-E / S1-F (23–29 Oct)

### 14.1 S1-E — Freeze and rehearsal (23–28 Oct)

| Step | Work | Owner | Done when |
|---|---|---|---|
| **E1.1** | `bench/offline_bench` and the safety suite re-run on the freeze build | B, E | All pass on the exact build that will be demonstrated |
| **E1.2** | **FEATURE FREEZE, 25 Oct.** Only bug fixes after this. | All | Announced in `decisions_log.md`; branch tagged |
| **E1.3** | Safety walk-through: fuses, e-stop, cables, batteries, charging, enclosures, haptic intensity | C | **Checklist signed** (E.2) |
| **E1.4** | Demo script with roles and timing; **three full rehearsals** | E, All | Three successful runs (E.3) |
| **E1.5** | Backup video of a complete successful run | E | Saved on two devices (E.4) |
| **E1.6** | Spare kit: phone, cables, batteries, fuses, **one assembled spare band**, tools | C | List ticked (E.5) |
| **E1.7** | `docs/citations.md` and `docs/limitations.md` complete | E | Checked against master spec §15 (E.6) |
| **E1.8** | `docs/results_log.md` final; every slide figure traced | E | No slide number without a logged row |
| **E1.9** | Rehearse answers: safety, privacy, novelty, limits, next steps | All | Each member can answer each one (E.7) |

**No file in this document is created after 25 Oct.** If a file does not exist by the freeze, it is not in the demo. Writing this down now is what makes the freeze a formality instead of an argument.

### 14.2 S1-F — Exhibition (29 Oct)

| Step | Work |
|---|---|
| **F1.1** | Exhibition checklist; test power, network and the demo course in the actual venue |
| **F1.2** | Camera notice displayed at the stand |
| **F1.3** | Demo with the backup video queued and ready |
| **F1.4** | **State the limits out loud**; show measured numbers from the results log |
| **F1.5** | Enrol only consenting teammates in any person-memory demo |
| **F1.6** | Collect judge and visitor feedback in writing |
| **F1.7** | Write up lessons the same evening, while they are still accurate |

---

## 15. Test Strategy Per Layer

Different layers earn different kinds of test. Spending integration-test effort on `contracts/` and unit-test effort on the full chain is how teams end up with a large suite that catches nothing.

| Layer | Test kind | What is asserted | Runs where |
|---|---|---|---|
| **L0 `contracts/`** | Validation tests | Invalid states are **unconstructible** — a `Person` without `consentTimestamp`, a `SafetyAlert` with a `CRITICAL` tier and `producedOffline` false | CI, every commit |
| **L1 `adapters/`** | Contract tests, one suite run against **every** implementation | Phone, UVC and file camera all satisfy `CameraSource` identically; BLE and mock satisfy `HapticOutput` identically | CI for fakes; on-device for real |
| **L2 `services/hygiene`** | Fixture tests | Each `degraded/` fixture is rejected with the correct reason; each good frame is accepted | CI |
| **L2 `services/safety`** | Replay tests against labelled clips | Precision/recall per class; TTC null below `min_track_age_frames`; sector correctness | CI (harness) |
| **L2 `services/arbiter`** | **Determinism and table tests** | Identical input + config → identical output, every time; one hazard → one alert; cooldowns honoured; suppression reasons logged | CI — fast, exhaustive, cheap |
| **L2 `services/memory`** | Storage tests | `forget` leaves no row **and no vector**; retention expiry runs; restart preserves events | CI |
| **L3 cloud services** | Schema and failure tests with a **recorded-response stub** | Malformed response → honest uncertainty, never a parsed guess; timeout → honest failure; cloud failure **never** propagates into L2 | CI, no network |
| **L4 features** | State-machine tests | `LookAroundMachine` terminates from **every** state and every input sequence; `ConsentFlow` stores nothing without consent | CI |
| **L5 shell** | Wiring and mode tests | Fake flag swaps the whole chain; all four power modes switch; camera stops in Home mode | CI + on-device |
| **Full chain** | Session replay + on-device runs | End-to-end latency; offline alert pass/fail; 60-minute endurance | Harness + real hardware |
| **Firmware** | Bench tests | Malformed packet dropped and counted; intensity cap holds against maximum app-side intensity; side identity correct after a swap | Bench |

### 15.1 The five tests that matter most

If time runs out and only five tests can exist, these are the five. Each one catches a failure that is either invisible in review or catastrophic in front of a user.

| # | Test | Catches |
|---|---|---|
| 1 | **Dependency graph check** (`ci/dependency_graph_check`) | An `L2 → L3` import — the offline guarantee silently breaking. Invisible in review past a few thousand lines. |
| 2 | **Offline alert test** (`bench/offline_bench`) | Any urgent alert that secretly needs the network |
| 3 | **Arbiter determinism test** | Non-reproducible safety behaviour — the thing that makes a demo failure impossible to debug |
| 4 | **Phrasebook forbidden-phrase lint** | A safety assurance reaching a user's ear |
| 5 | **`LookAroundMachine` termination test** | A user left turning in a circle waiting for a machine that has stopped |

### 15.2 What is deliberately not tested heavily

| Not heavily tested | Why |
|---|---|
| Cloud response *content* quality | Measured by benchmark on fixtures (hallucination rate), not asserted in unit tests — there is no stable expected string |
| UI appearance | Minimal surface; nothing essential is screen-only |
| Exact latency values in CI | Hardware-dependent; measured on device and logged, not asserted as a build gate |

---

## 16. Instrumentation and Latency Measurement Points

The master spec's latency budget (§9.2) is only measurable if the probes exist. Each row here is one named `LatencyProbe` mark. Every mark carries the **originating frame's capture timestamp**, so segments can be differenced without assuming a single pipeline.

| Probe name | Emitted when | Segment it closes |
|---|---|---|
| `frame.captured` | Camera adapter receives the frame; timestamp is capture time | — (the origin) |
| `frame.delivered` | Frame arrives in the app from the transport | Camera exposure + USB/sensor transfer |
| `frame.hygiene.done` | `FrameSelector` accepts or rejects | Buffer handoff + hygiene |
| `frame.detect.done` | Detector returns boxes | Detector inference |
| `frame.track.done` | Tracker returns tracks | Tracker association |
| `track.growth.ready` | `GrowthEstimator` first returns a non-null TTC for a track | **Frames needed before growth is visible** — the row the old budget omitted |
| `arbiter.decided` | `RuleArbiter` returns dispatch decisions | Arbiter evaluation |
| `haptic.queued` | `BleHapticOutput` enqueues the command | App-side queueing |
| `haptic.sent` | BLE write completes | **BLE connection-interval wait** — the second omitted row |
| `haptic.ack` | Firmware acknowledges receipt | Transport confirmation |
| `haptic.motor.start` | Firmware reports motor start | Firmware decode + motor spin-up |
| `speech.requested` | `SpeechDispatcher` receives the request | — |
| `speech.audible` | First audio sample leaves the output | Speech path total |
| `voice.user.stopped` | VAD reports end of user speech | — (origin for the voice metric) |
| `voice.reply.audible` | First syllable of the reply is audible | **Response latency** — the headline voice number |
| `voice.bargein.requested` | User speech onset detected during playback | — |
| `voice.bargein.stopped` | Playback actually stopped | **Barge-in latency** |

### 16.1 Reporting rules for these probes

| Rule |
|---|
| **Glass-to-haptic** = `frame.captured` → `haptic.motor.start`. Nothing shorter may be called glass-to-haptic. |
| **Response latency** = `voice.user.stopped` → `voice.reply.audible`. |
| Every reported figure is **median and p95**, never a mean alone and never a best case. |
| `track.growth.ready` and `haptic.sent` are reported **separately and explicitly**, because they are the two segments the original 126 ms budget omitted and they may dominate the total. |
| A figure quoted without its probe pair and trial count does not go in `results_log.md`, and therefore cannot reach a slide. |

---

## 17. Horizon 2 — File Additions Per Phase

No dates. Each phase's files are written only after the previous phase's gate passes (master spec §12.2).

| Phase | Files added or substantially extended | Notes |
|---|---|---|
| **1 — Voice** | `services/agent/providers/*` hardened; `fixtures/speech/` expanded for Sinhala and Tamil; `bench/wer_bench` | WER published per language |
| **2 — Vision** | `services/vision/` provider comparison harness; `bench/vlm_comparison_bench`; `LookAroundMachine` refinements from user feedback | The VLM comparison the original plan promised but never scheduled properly |
| **3 — Memory** | `services/memory/` full build if S1-D was dropped; `services/routines/MorningBrief`; retention policy UI | |
| **4 — People** | `features/people/` full build if S1-D was dropped; `bench/falsematch_bench` with a proper volunteer set | Needs the ethics position confirmed first |
| **5 — Routines** | `services/routines/` routine-learning suggestions; `shell/ui` reminder surfaces | Suggestions only, never automatic |
| **6 — Street awareness** | `data/local-street-set/` + labelling tools; `training/` for detector fine-tuning; `bench/` per-class breakdowns | **The largest likely accuracy gain in the project** (master spec §12.3) |
| **7 — Haptics** | `services/arbiter/ChannelPolicy` extended with reaction-time-driven policy; `bench/reaction_time_bench` | Speech vs haptic vs both, measured |
| **8 — Safety & trials** | `harness/analysis/` trial tooling; consent and withdrawal tooling; `docs/limitations.md` finalised | Ethics approval is the blocker, not code |
| **9 — Productisation** | `platform-linux/` **or** Android-on-board variant; `models/rknn/` or vendor equivalent; carrier PCB sources under `hardware/` | Only after Gate B |

### 17.1 The Stage 2 port, as files

This is the item the source documents mis-costed as "ONNX means it ports". Written as files, the real shape is visible:

| New or changed | Work |
|---|---|
| `adapters/camera/V4l2CameraSource` | New implementation of the existing interface — **this part really is cheap** |
| `adapters/audio/LinuxAudioIo` | New implementation of the existing interface — also cheap |
| `adapters/haptic/BleHapticOutput` | **Unchanged**, because the command format was frozen in S1-A. This is the adapter strategy paying off. |
| `models/<vendor>/` | **Model conversion to the vendor NPU format**, with static shapes, an operator-coverage check, and **accuracy re-validated after conversion** |
| `platform-linux/` or Android-on-board shell | **The application-layer port.** This is the expensive row, and it is a project, not a configuration change. |
| `services/*` | Unchanged **if** R1–R3 were honoured throughout. The dependency rules are what make this row empty. |
| `harness/bench/*` | Re-run unchanged on the board, for a fair side-by-side — Gate B evidence |

> The honest summary: **three adapter files are cheap, the model conversion is uncertain, and the application-layer port is a project.** The services are free only because the layering rules were enforced from day one. That is the return on R1–R4.

---

## 18. Definition of Done, Per File

A file is done when **all six** hold. Five out of six is not done; it is a file that will be revisited at 11pm on 28 October.

| # | Criterion |
|---|---|
| 1 | Its single responsibility (§5–§8) is implemented and nothing else is |
| 2 | Its `Exposes` list is complete, and nothing outside that list is reachable from other files |
| 3 | Its `Depends on` list is accurate and the dependency check passes |
| 4 | Its `Done when` behaviour is demonstrated — by a test, a logged measurement, or a witnessed demo |
| 5 | No numeric threshold and no spoken string is hard-coded inside it (§4.4) |
| 6 | Every failure path either degrades a feature honestly or raises a fault — **no silent catch** (§4.3) |

### 18.1 Extra criteria for safety-path files

Files in `services/hygiene`, `services/safety`, `services/arbiter` and `adapters/haptic` carry two more:

| # | Criterion |
|---|---|
| 7 | Verified to work with the radio off |
| 8 | Contains no reference to anything in `L3`, and no model runtime is reachable from the arbiter |

---

## Appendix A — File Index by Owner

| Owner | Role | Files |
|---|---|---|
| **A** | Voice and vision AI | `services/voice/*`, `services/agent/*`, `services/vision/*`, `features/lookaround/*`, `features/onboarding/*`, `config/phrasebook.yaml`, `adapters/audio/*` |
| **B** | Safety engine | `services/hygiene/*`, `services/safety/*`, `services/arbiter/*`, `config/thresholds.yaml`, `config/classes.yaml` |
| **C** | Haptics and electronics | `firmware/wristband-esp32/*`, `hardware/*`, `config/haptic_patterns.yaml`, bench verification of `adapters/haptic/BleHapticOutput` |
| **D** | App and integration | `contracts/*`, `adapters/camera/*`, `adapters/clock/*`, `adapters/storage/*`, `adapters/haptic/*`, `services/memory/*`, `services/routines/*`, `features/people/*`, `features/failsafe/*`, `shell/*`, `instrumentation/*`, `ci/dependency_graph_check` |
| **E** | Evaluation and documentation | `harness/*`, `docs/*`, `ci/threshold_lint`, `ci/phrasebook_lint`, `ci/contract_sync_check`, all fixtures |

### A.1 Cross-owner coupling points — agree these before writing

| Coupling | Between | Agree by |
|---|---|---|
| `contracts/haptic_command` byte layout | D ↔ C | **11 Oct** (A1.4), frozen for the sprint |
| `phrasebook.yaml` keys for safety alerts | B ↔ A | 12 Oct — B emits keys, A owns wording |
| `LogEvent` field names | D ↔ E | 11 Oct — E's parsers depend on them |
| Session format | D ↔ E | 11 Oct (A1.9) |
| `thresholds.yaml` key names | B ↔ E | 11 Oct — the sweeper depends on them |

Five coupling points, all agreed in the first two days. Every one of them is cheap to agree now and expensive to renegotiate on 24 October.

---

## Appendix B — What Deliberately Has No File

Recorded so nobody creates these by reading an archived document. Each corresponds to a rejected or deferred item in the master spec.

| No file for | Instead | Master spec |
|---|---|---|
| A Jev client on the safety path | `services/arbiter/*` — deterministic rules, no model | §7.6, App. B.2 |
| Any model-based arbiter | `PriorityMatrix` reading `thresholds.yaml` | R4, §5.2 |
| A metric depth model | `GrowthEstimator` + `BucketMapper` | §6.3, D-09 |
| An open-vocabulary detector | `VisionToolset.find_object` via cloud VLM | App. B.1 |
| A local VLM | Honest offline message from `phrasebook.yaml` `offline.*` | App. B.1 |
| Memory or agent frameworks | `HybridRetriever`, plain `ToolRegistry` | App. B.1 |
| Face image or crop storage | `FaceEmbedder` discards crops; only embeddings persist | §10.1 |
| Raw video storage | `SessionRecorder` writes only consented evaluation sessions | D-17 |
| A `SAFETY_ALERT` intent | `contracts/safety_alert` on its own path | §6.2 |
| A Raspberry Pi hub target | Phone (Stage 1); one chosen board (Stage 2) | §1 row 9 |
| A wireless glasses link | `UvcCameraSource` over the wired tether | D-13 |
| A 4G module driver | Phone connectivity | D-08 |
| A "safe to cross" code path | `ci/phrasebook_lint` makes it **unbuildable** | N1 |

---

*End of document. Revision 1.0 — 11 October 2026. Companion to `MASTER_SPECIFICATION.md` revision 1.0.*
