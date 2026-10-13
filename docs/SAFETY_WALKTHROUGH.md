# Safety Walk-Through — Pre-Demonstration Checklist

**Project:** AI Personal Assistant for Visually Impaired Users
**Build / tag:** ____________________
**Date:** ____________  **Walked through by (owner C):** ____________________

Every box is ticked by physically checking the thing, not by remembering that
it was done. A unit that fails any item does not go to the stand.

---

## 1. Batteries and cells

| | Check |
|---|---|
| [ ] | Every lithium cell is a **protected** cell (integrated protection circuit) |
| [ ] | No cell shows swelling, dents, puncture marks or a damaged wrapper |
| [ ] | Every cell is seated so it cannot move or short against a conductor |
| [ ] | No cell is charged unattended, and none was charged overnight on a bench |
| [ ] | Charger IC matches the cell chemistry and capacity |
| [ ] | Spare cells are transported in individual insulated bags, terminals covered |

## 2. Fuses

| | Check |
|---|---|
| [ ] | Inline fuse present on the **hub** battery/power-bank path |
| [ ] | Inline fuse present on the **left band** power path |
| [ ] | Inline fuse present on the **right band** power path |
| [ ] | Each fuse is rated for its circuit (value recorded below, not guessed) |
| [ ] | Each fuse sits in a holder that can be opened and replaced at the stand |
| [ ] | Spare fuses of each value are in the kit |

Fuse values — hub: ______ A · left band: ______ A · right band: ______ A

## 3. Emergency stop

| | Check |
|---|---|
| [ ] | Hub has a physical e-stop that **cuts power**, verified by test |
| [ ] | Left band has an e-stop, verified by test |
| [ ] | Right band has an e-stop, verified by test |
| [ ] | Each e-stop is **findable by touch** without sight |
| [ ] | Each e-stop is labelled |
| [ ] | Each e-stop was operated at least once today and the unit powered down |

## 4. Wiring and mechanical

| | Check |
|---|---|
| [ ] | Strain relief on every cable entering an enclosure |
| [ ] | No exposed conductor anywhere on a worn unit |
| [ ] | USB tether routed so it cannot tug the glasses frame off the user's face |
| [ ] | No sharp edge or pinch point against skin |
| [ ] | Band straps intact; nothing that can tighten unintentionally |
| [ ] | Enclosures closed; no screw missing |

## 5. Thermal

| | Check |
|---|---|
| [ ] | 60-minute endurance run completed; temperature curve logged |
| [ ] | Nothing in skin contact exceeded the limit set from those measurements |
| [ ] | Limit used: ______ °C, basis: ______________________ (measurement + guidance, not a guess) |
| [ ] | Hub enclosure has its ventilation path clear |

## 6. Haptics

| | Check |
|---|---|
| [ ] | Firmware intensity cap present and verified against a max-intensity command |
| [ ] | Every pattern tried on a team member's wrist; none uncomfortable |
| [ ] | Left and right bands distinguishable **by touch**, verified blindfolded |
| [ ] | Bands flashed from the same source, differing only in the side flag |

## 7. Indicators

| | Check |
|---|---|
| [ ] | Hub: power, camera-active, link, battery, fault — all visible |
| [ ] | Camera-active indicator unambiguous, plus periodic audible chime |
| [ ] | Left band: LED + buzzer working |
| [ ] | Right band: LED + buzzer working |

## 8. Software safety gates

| | Check |
|---|---|
| [ ] | `phrasebook_lint` passes — no safety-assurance phrasing reachable |
| [ ] | Offline alert test passed on this build, radio off |
| [ ] | Cane-first onboarding plays on a fresh install |
| [ ] | All four fail-safes announce by **speech and haptic** |
| [ ] | `DemoHealthCheck` run on this hardware, result recorded |

## 9. Demonstration conduct

| | Check |
|---|---|
| [ ] | Demo course is controlled; no live traffic, no public road |
| [ ] | Only consenting **team members** wear or are recognised by the device |
| [ ] | Camera notice displayed at the stand |
| [ ] | Nobody is blindfolded and walked anywhere near a hazard |
| [ ] | Advisory-only wording rehearsed; nobody will say the device makes anything safe |

---

## Declaration

I have physically checked every item above on the units going to the
exhibition. Any item that failed has been fixed and re-checked, or the unit
has been withdrawn.

**Signed by (owner C):** ____________________  **Date:** __________

**Counter-signed (owner E):** ____________________  **Date:** __________

Items that failed and what was done:

```
```
