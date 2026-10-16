# Limitations

Written honestly, and read out at the demonstration. Every item here is
something a judge or examiner would find anyway; saying it first is both
more honest and more persuasive than being caught by it.

## What the system does not detect

- **Drop-offs, holes, open drains, kerbs and step edges.** Not in the class
  list, not attempted. The white cane remains the primary tool for ground
  hazards, and onboarding says so on every install.
- **Overhead obstacles** below head height that are outside the camera's
  downward-tilted field of view.
- **Glass doors and transparent obstacles** — these defeat the detector.
- **Anything behind the user.** The camera faces forward only.

## What the distance figures mean

- Distance is reported as **buckets** (right in front of you / a couple of
  steps / across the room / far), never in metres. There is no metric depth
  model in this build, so a metre figure would be a guess with a decimal point.
- Time-to-contact is estimated from bounding-box **growth**, which requires
  the object to be seen growing across several frames. A fast object that
  appears already close may be reported late or not at all.

## Measurement honesty

- Thermal figures are **battery temperature**, not skin temperature. Battery
  temperature lags and reads lower than the hottest point of the case. It is
  a proxy, reported as one.
- All latency figures are median and 95th percentile from the probe points
  listed in the implementation plan. The USB transfer latency between the
  camera sensor and the frame callback is **not** captured by our timestamps
  and is a known gap in the budget.
- Detector frame rate was measured on one phone model. It will differ on others.

## Language

- English only in this build. Sinhala and Tamil word error rates were
  benchmarked and are published in the results log — they are **not** good
  enough to call the system multilingual.
- The consent affirmative word lists for Sinhala and Tamil are short and have
  **not** been reviewed by a native speaker. That review is required before
  any trial with external volunteers.

## Person memory (if demonstrated)

- Matching is thresholded high, so the system will **miss** people it knows
  rather than risk naming the wrong person. A missed greeting is the
  deliberate trade.
- The false-match rate is reported over comparison pairs with a confidence
  interval. The volunteer set is small, so that interval is wide. It is not
  a claim that the rate is zero.
- Face embeddings are lexical-model-free but the embedding model's pretrained
  weights carry a licence recorded in `citations.md`. Check it before any use
  beyond this demonstration.

## Memory and recall

- The text embedder is **lexical, not semantic**. It matches shared character
  patterns, so "medication bottle" reaches "medicine bottle" but "my pills"
  does not reach "medication". Temporal questions ("where did I go after
  lunch") are not reliably answered. Specific failures are in the recall
  benchmark output.

## Security

- Prompt-injection tests were run against text on signs, posters and
  clothing. **Results and known issues are documented; no claim of immunity
  is made.** Specific failures are listed in the injection benchmark output.
- No claim of "zero vulnerabilities" is made anywhere, including verbally.

## Hardware stage

- This is the **Stage 1 phone-hub prototype**. The custom embedded hub and
  the carrier PCB are gated on measurements from this build and are not part
  of this demonstration.
- Push-to-talk and mute are bound to the phone's volume keys, which overrides
  their normal function while the app is in the foreground. Physical buttons
  are part of the Stage 2 justification.

## Evaluation stage

- No trials with visually impaired volunteers have been conducted. Ethics
  approval has not yet been obtained. All testing to date used team members
  on a controlled course.
- Therefore **no usability claim is made**. What is demonstrated is that the
  system works, not that it helps.

## Open defects at freeze

| Defect | Impact | Why not fixed |
|---|---|---|
| | | |
