# Q&A Preparation

Rehearse out loud. A hesitant honest answer beats a fluent evasive one, and
every answer below is one you can give without overclaiming.

---

## Safety

**"What if it misses a car and someone gets hurt?"**
> It will miss cars. We measured precision and recall and both are in our
> results log. That's exactly why the system is positioned as an advisor on
> top of the white cane, never a replacement, and why it never says anything
> is safe. The cane-first message plays on every install.

**"Why not just say 'it's safe to cross' when it's confident?"**
> Because our confidence isn't good enough to carry that sentence, and it
> never will be from one forward camera. We made it structurally impossible
> rather than discouraged — those phrases are in a deny-list that fails our
> build if anyone ever adds one.

**"What happens if the phone dies mid-walk?"**
> Everything stops and the user knows immediately — the band link drops and
> announces itself by sound and vibration. We treat silence as the dangerous
> failure, so every fault is announced on two channels.

**"Could someone become over-reliant on it?"**
> That's our biggest non-technical risk and it's in our risk register. Our
> mitigations are the cane-first onboarding, honest uncertainty phrasing, and
> fail-visibly design. Whether they're *sufficient* is a question for the
> volunteer trials we haven't run yet.

## Privacy

**"You're putting a camera on someone's face. What about bystanders?"**
> Video is processed locally and never stored. Face data is opt-in per person
> with spoken consent from that person, not just the user. We store a
> mathematical embedding, never an image, and "forget [name]" deletes it —
> we test that at the database level, including checking for orphaned
> embeddings a UI wouldn't show.

**"What goes to the cloud?"**
> Frames and audio, only while the user is actively asking a question, with
> a visible indicator and an audible chime. Hazard detection, the timeline,
> contacts and face matching never leave the device. We verified that against
> actual captured network traffic, not just against our intentions.

**"Can you prove deletion works?"**
> Yes — we can run it now. [Demonstrate "forget" and show the storage counts
> drop to zero, including the embedding table.]

## Technical

**"Why not use [newer model / depth estimation / cloud detection]?"**
> Depth estimation is on our deferred list with a written promotion criterion:
> it has to convert to the target runtime and be validated against tape-measure
> ground truth before we'd ship a metre figure. Cloud detection breaks the
> offline guarantee, which is the one property we won't trade.

**"What's your latency?"**
> Glass-to-haptic median and 95th percentile are in the results log with the
> method. I'd rather give you both numbers than a best case — and there's a
> segment our timestamps can't see, the USB transfer, which we've documented
> as a gap rather than pretending it's zero.

**"30 FPS?"**
> No. We target 5–10 fps at reduced resolution in street mode, and the
> measured figure is in the log. A higher number would need a sustained
> measurement, not a peak.

**"Why is the safety logic not machine learning?"**
> So it's deterministic and auditable. The whole arbitration is a threshold
> table you can read on one page, and we have a test asserting identical
> inputs give identical outputs. A learned arbiter would be neither.

## Novelty

**"How is this different from [existing assistive app]?"**
> Most tools answer a question about the current camera frame. Ours runs a
> closed loop with the user's own body as the actuator — the wrist steers,
> speech confirms, and it tells you when to stop. Our comparison table is in
> the citation register. [Name the specific products.]

**"Isn't this just YOLO plus a text-to-speech?"**
> The detector is one component of eleven. The parts that took the work are
> the arbitration — deciding when *not* to speak — the look-around loop, and
> making the whole hazard path work with the radio off.

## Project

**"What would you do with more time?"**
> Collect a local street dataset and fine-tune on it. A detector trained on
> Western street scenes under-performs on three-wheelers and motorcycles on
> footpaths, and those are the actual hazards here. That's probably the
> largest accuracy gain available to us, and it's cheaper than new hardware.

**"Why haven't you tested with blind users?"**
> We haven't got ethics approval, and we won't put someone in front of an
> unmeasured street-alert system for a demo. The paperwork starts the week
> after this. It's also why we're making no usability claim today.

**"What's your biggest weakness?"**
> We don't know whether it actually helps anyone. We've shown it works; we
> haven't shown it's useful. That requires the volunteer trials.

---

## Answers nobody should give

| Never say | Say instead |
|---|---|
| "It's 100% accurate" | The measured figure with its denominator |
| "It's completely secure" | "We ran injection tests; results and known issues are documented" |
| "It protects the user" | "It alerts the user" |
| "It detects everything" | The class list, and what's deliberately not in it |
| "We'll fix that later" | "That's on our deferred list, and here's the criterion for promoting it" |
| An invented number | "I don't have that measured — I'd be guessing" |

That last one is the most important. **"I don't know, we haven't measured
that"** is a strong answer. A fabricated figure is the one mistake that
retroactively discredits every real number on the slide.
