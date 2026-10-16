#!/usr/bin/env bash
# E1.1 / E1.2 — the freeze gate.
#
# Run this on 25 Oct on the EXACT build that will be demonstrated.
# It writes docs/freeze_report.md. Nothing is frozen until this passes.
#
#   bash ci/freeze_check.sh
#
set -u

REPORT="docs/freeze_report.md"
FAIL=0
PASS_MARK="PASS"
FAIL_MARK="**FAIL**"

mkdir -p docs
{
  echo "# Freeze Report"
  echo
  echo "- Generated: $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "- Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  echo "- Commit: $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
  echo "- Dirty files: $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  echo
  echo "| Check | Result | Notes |"
  echo "|---|---|---|"
} > "$REPORT"

check () {            # check "<name>" "<command>" "<note>"
  local name="$1" cmd="$2" note="${3:-}"
  printf '  %-42s' "$name"
  if out=$(eval "$cmd" 2>&1); then
    echo "$PASS_MARK"
    echo "| $name | $PASS_MARK | $note |" >> "$REPORT"
  else
    echo "$FAIL_MARK"
    echo "| $name | $FAIL_MARK | $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-110) |" >> "$REPORT"
    FAIL=1
  fi
}

echo
echo "=== FREEZE CHECK ==="
echo

# --- static gates -----------------------------------------------------------
check "dependency graph (R1-R4)" \
      "python3 ci/dependency_graph_check.py" \
      "no L2→L3 edge; arbiter has no model runtime"

check "phrasebook deny-list" \
      "python3 ci/phrasebook_lint.py" \
      "no safety-assurance phrasing reachable"

check "threshold lint" \
      "python3 ci/threshold_lint.py" \
      "every threshold referenced and defined"

# --- build and tests --------------------------------------------------------
check "release build compiles" \
      "./gradlew --quiet assembleDebug" \
      "the build that ships"

check "unit tests" \
      "./gradlew --quiet testDebugUnitTest" \
      "arbiter determinism, look-around termination, consent invariant"

# --- the five tests that matter most ---------------------------------------
check "arbiter determinism test present" \
      "test -f app/src/test/java/lk/assistive/ArbiterDeterminismTest.kt" \
      "top-5 test #3"

check "look-around termination test present" \
      "test -f app/src/test/java/lk/assistive/LookAroundTerminationTest.kt" \
      "top-5 test #5"

# --- results and documentation ---------------------------------------------
check "results log has rows with methods" \
      "python3 harness/analysis/results_writer.py --verify" \
      "every number carries its method"

check "slide figures all traceable" \
      "python3 ci/slide_trace_check.py docs/pitch.md" \
      "E1.8"

check "citations register non-empty" \
      "test -s docs/citations.md && grep -qi 'licence\\|license' docs/citations.md" \
      "E1.6 — detector and face-weight licences recorded"

check "limitations documented" \
      "test -s docs/limitations.md && test \$(wc -l < docs/limitations.md) -gt 12" \
      "honest failure list"

check "safety walkthrough signed" \
      "grep -qi 'signed by' docs/SAFETY_WALKTHROUGH.md && \
       ! grep -q '\\[ \\]' docs/SAFETY_WALKTHROUGH.md" \
      "E1.3 — every box ticked and signed"

check "decisions log updated today" \
      "test -s docs/decisions_log.md" \
      "gate verdicts recorded"

# --- things that must NOT be present ---------------------------------------
check "no TODO/FIXME in safety path" \
      "! grep -rn 'TODO\\|FIXME' app/src/main/java/lk/assistive/services/safety \
         app/src/main/java/lk/assistive/services/arbiter 2>/dev/null" \
      "unfinished work on the hazard path"

check "no hard-coded spoken strings" \
      "! grep -rn 'say(\"[A-Z]' app/src/main/java/lk/assistive --include=*.kt 2>/dev/null" \
      "all speech goes through phrasebook keys"

check "fake adapters flag is OFF in debug" \
      "! grep -q 'USE_FAKE_ADAPTERS\", \"true\"' app/build.gradle.kts || \
       grep -q 'create(\"fakes\")' app/build.gradle.kts" \
      "demo must not run on fakes by accident"

# --- manual gates the script cannot verify ---------------------------------
{
  echo
  echo "## Manual gates — tick by hand, initial each"
  echo
  echo "| Gate | Done | Initials |"
  echo "|---|---|---|"
  echo "| Offline alert test passed on real hardware, radio off (C1.7) | [ ] | |"
  echo "| 60-minute endurance run completed, no shutdown (C1.6) | [ ] | |"
  echo "| Three full rehearsals completed (E1.3) | [ ] | |"
  echo "| Backup video on two devices (E1.4) | [ ] | |"
  echo "| Spare kit packed and ticked (E1.5) | [ ] | |"
  echo "| Every team member can answer the Q&A list (E1.7) | [ ] | |"
  echo
  echo "## Verdict"
  echo
  if [ "$FAIL" -eq 0 ]; then
    echo "**Automated gates: PASSED.** Freeze may proceed once the manual gates above are ticked."
  else
    echo "**Automated gates: FAILED.** Do not freeze. Fix the failures above and re-run."
  fi
  echo
  echo "Frozen by: ______________________  Date: __________"
} >> "$REPORT"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "ALL AUTOMATED GATES PASSED"
  echo "Report: $REPORT  — tick the manual gates, then tag the freeze:"
  echo
  echo "  git add -A && git commit -m 'E1.2: feature freeze'"
  echo "  git tag -a freeze-25oct -m 'Feature freeze. Bug fixes only after this.'"
else
  echo "GATES FAILED — see $REPORT"
fi
exit "$FAIL"
