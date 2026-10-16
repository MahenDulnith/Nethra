# Demo Script — 6 minutes

**Roles:** A = narrator · B = wearer · C = hardware standby · E = timekeeper + backup video

C stands within arm's reach of the e-stop for the whole demonstration.
E has the backup video queued and the results slide open.

---

## 0:00–0:30 — Frame the problem and the limits, in that order

> **A:** "This is a whole-day assistant for people with low vision. Before
> anything else — it is an **advisor, not a pilot**. It never tells anyone a
> road is safe to cross, and the white cane stays the primary tool for the
> ground. Everything you're about to see is on top of that, not instead of it."

Stating the limits first inoculates every claim that follows. Do not skip it
to save time.

## 0:30–1:15 — Cane-first onboarding, live

B launches a fresh install. The onboarding message plays.

> **A:** "That plays on every install. It isn't a disclaimer we added for
> judging — it's the first thing a user hears."

## 1:15–2:30 — Voice and vision

B holds volume-up: *"What's in front of me?"* → spoken answer.
B: *"Read that sign."* → on-device OCR reads it.

> **A:** "The reading was done on the phone, with no network. Watch." —
> B enables airplane mode, repeats the read-text request. It still works.

> **A:** "Scene description needs a connection, and it says so rather than
> guessing." — B asks for a description while offline; the system says it
> needs a connection.

That honest refusal is a feature. Point at it.

## 2:30–3:45 — The look-around loop (the novelty claim)

B, facing away from the target: *"Where is the door?"*

- Left wrist pulses → B turns left
- A narrates: "The wrist is steering. Speech only confirms — on a street,
  speech competes with traffic noise and with the user's own hearing."
- Target found → both wrists buzz once, system names the clock direction

> **A:** "And when it can't find something, it says so and stops. It doesn't
> leave someone turning in a circle." — B asks for an object that isn't
> there. The loop terminates and says it can't find it.

Demonstrating the failure path is more convincing than the success path.
Most systems only show the success.

## 3:45–5:00 — Hazard alerts, offline

**Airplane mode stays ON for this entire section.** Say so.

C rolls the prop vehicle toward B on the controlled course.

- Alert fires: speech + urgent haptic burst, correct side
- A: "Radio off. No cloud, no language model. A quantised detector, a
  tracker, and a rule table — all on the phone."

Repeat once from the other side to show direction.

> **A:** "Two things we deliberately do not do: we never give a distance in
> metres, because we have no depth model and a wrong metre figure is worse
> than an honest 'a couple of steps'. And a track too young to trust never
> raises an alert at all."

## 5:00–5:40 — Fail visibly

B covers the camera. Within seconds: spoken *"The camera is covered"* plus
the fault haptic pattern, on both wrists.

> **A:** "Silence is never allowed to mean all clear. If we stop watching,
> the user hears it and feels it."

C disconnects a band. Link-lost announcement fires.

## 5:40–6:00 — Numbers and limits

E shows the results slide.

> **A:** "Every figure here has a method behind it in our results log. The
> latencies are median and 95th percentile, not best case. We have not run
> trials with visually impaired volunteers and we have no ethics approval
> yet, so we make **no usability claim** — only that it works. Here's what it
> can't do." — E shows the limitations slide.

---

## Failure branches — decided now, not at the stand

| If | Then | Say |
|---|---|---|
| Glasses camera drops | Fallback to phone camera fires automatically | "That just fell back to the phone camera in under a second — that's the fail-visibly design working. Continuing on the phone." |
| A band disconnects | Continue single-sided | "I've lost the right band. Directional cues are degraded — I'll demo with the left only and show the fault announcement, which you just heard." |
| Detector gives no alert in 20 s | C triggers the replay clip path | "Switching to recorded street footage so you can see the alert behaviour. Same code path, same decisions." |
| Phone thermally throttles | Stop, state it | "It's throttling. That's a measured limit of the phone hub and it's exactly why Stage 2 custom hardware is gated on these measurements." |
| Anything smells, gets hot, or looks wrong | **C hits the e-stop. Demo over.** | "We're stopping. Our own safety rule is that we stop and fix rather than continue." |
| Two or more subsystems fail | E plays the backup video | "Our hardware is having a bad morning — here's a recorded full run, and the units are here for you to inspect." |

Stopping cleanly and saying why reads as competence. Pushing on through a
fault reads as not knowing it failed.
