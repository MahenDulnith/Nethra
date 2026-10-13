# Exhibition Checklist — 29 October

## Pack the night before (28 Oct) — owner C

### Primary kit
- [ ] Phone hub, charged to 100%, app build `freeze-25oct` installed
- [ ] Glasses with USB-C camera, cable strain-relieved
- [ ] Bone-conduction headset, charged
- [ ] Left band — charged, e-stop verified, fuse in place
- [ ] Right band — charged, e-stop verified, fuse in place
- [ ] Power bank, charged, with inline fuse on its path

### Spares (the demo-insurance list)
- [ ] **Spare phone** with the same build installed and tested
- [ ] One assembled spare wristband, flashed and tested
- [ ] Spare USB-C cables ×2, spare OTG hub
- [ ] Spare cells, individually bagged, terminals covered
- [ ] Spare fuses of every value used
- [ ] Multimeter, small screwdriver set, tape, zip ties
- [ ] Laptop with the harness, for showing logs if asked

### Documents
- [ ] Printed results slide (the numbers, with methods)
- [ ] Printed limitations page
- [ ] Printed one-page safety position
- [ ] Signed `SAFETY_WALKTHROUGH.md`
- [ ] Camera notice for the stand
- [ ] Demo script, one copy per role

### Media
- [ ] Backup video on device 1
- [ ] Backup video on device 2
- [ ] Both verified to actually play, with sound, today

---

## On arrival

- [ ] Locate power. Plug in and start charging immediately.
- [ ] Test the venue network. Assume it is bad.
- [ ] Set up the controlled demo course; walk it once
- [ ] Display the camera notice
- [ ] Set up the prop vehicle / obstacle, check clearances
- [ ] **Run `DemoHealthCheck`.** Record the result.
- [ ] Fire one test alert and one test look-around end to end
- [ ] Confirm C can reach every e-stop from where they will stand
- [ ] Let the phone cool before the first demo if it is warm

## Before each demonstration

- [ ] Re-run `DemoHealthCheck` — it takes fifteen seconds
- [ ] Check band batteries; swap below 30%
- [ ] Check phone thermal state; wait if throttling
- [ ] Backup video queued and ready
- [ ] C in position, within reach of the e-stop

## During

- [ ] State the limits **first**, before any capability
- [ ] Say which camera is live (glasses or phone) — do not let it be assumed
- [ ] Say when the radio is off, and that alerts still work
- [ ] Show the failure paths, not only the successes
- [ ] Only team members wear the device or are recognised by it
- [ ] If anything is hot, smells, or looks wrong: **e-stop, stop, explain**

## After each demonstration

- [ ] Write down what the judge or visitor asked, verbatim where possible
- [ ] Note anything that failed and when
- [ ] Charge whatever needs charging

## End of day — same evening, not the morning after

- [ ] Pull every session log off the phone to the laptop
- [ ] Write up what failed, what was asked, and what surprised you
- [ ] Record the Gate A inputs: did the phone throttle? was battery a real
      constraint? did anything need hardware the phone cannot give?
- [ ] Log every decision and piece of feedback in `decisions_log.md`

That last item is the one everybody skips and nobody can reconstruct later.
Gate A — whether Stage 2 hardware deserves to exist at all — is decided on
the measurements you take today, and the honest answer is much more likely
to be "stay on the phone and go run user trials" than anyone expects.
