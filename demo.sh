#!/bin/bash
# CFB Contrarian Predictor 2026 — guided tour of the supported `cfb` interface.
#
# Read-only: nothing here writes an artifact. Predictions are byte-immutable claims (D22), so the
# demo deliberately never passes `--save`.
#
# Install first:  make install    (editable install; provides the `cfb` console script)

set -u

banner() {
    echo ""
    echo "================================================"
    echo "  $1"
    echo "================================================"
    echo ""
}

pause() { echo ""; read -r -p "Press Enter to continue..."; }

if ! command -v cfb >/dev/null 2>&1; then
    echo "⚠️  The 'cfb' command is not installed. Run:  make install"
    exit 1
fi

banner "CFB Contrarian Predictor 2026 — Live Demo"
echo "A rule-based, frozen-weight contrarian spread model."
echo "Weights were frozen at the v2026-frozen tag and do not change during the season."
pause

banner "1. System health, and proof the model is still frozen"
echo "Shows the current week, the freeze tag, whether factors/ and engine/ still"
echo "match that tag, and per-source key + quota status."
echo ""
cfb status
pause

banner "2. The week's slate"
echo "The FBS-vs-FBS games with a prediction-time line, from the committed snapshot."
echo ""
cfb slate 1
pause

banner "3. Predicting a full week"
echo "Every game is serialized — including NO_BET, which is the point: the model"
echo "logs what it declined, so selectivity can be graded later."
echo ""
cfb predict week 1 | head -30
echo "..."
pause

banner "4. What drove one game"
echo "Per-sub-signal factor breakdown for a single matchup on the slate."
echo ""
cfb predict game "Baylor @ Auburn" --week 1 --show-factors
pause

banner "5. A hypothetical matchup"
echo "Any two teams, priced off the current ratings — not restricted to the slate."
echo "Travel, altitude and rest are applied, so the number moves with the venue."
echo ""
cfb hypothetical "Texas vs Ohio State" --show-factors
pause

banner "6. Season projections"
echo "Projected wins for every FBS team, from the same frozen pricer."
echo ""
cfb project | head -20
echo "..."
pause

banner "7. Inspecting the data behind a prediction"
echo "Provenance for the week's snapshot: which sources were live, which fields are"
echo "honestly missing, and the field-level coverage. Missing data is recorded as"
echo "missing — never neutral-filled."
echo ""
cfb data inspect --week 1 | head -25
echo "..."

banner "Demo complete"
cat <<'NOTES'
What this system is:

  • Rule-based and frozen. No in-season weight changes; the freeze is enforced by
    hooks, by a tree-hash check, and by a behavioural fingerprint over the slate.
  • Honest about absence. Missing data is recorded with provenance, never faked.
  • Forward-tested only. Predictions are committed before kickoff and graded after,
    so the audit trail is the product.

Preseason, every game is NO_BET. That is selectivity working as designed, not
breakage — the maximum attainable edge preseason sits below the betting floor
because most factors are dormant until real games are played.

Further reading:
  docs/PIPELINE.md        the weekly automation and its commit choreography
  docs/SPEC.md            the build plan and the binding decisions
  docs/DECISIONS.md       every owner ruling, with its reasoning
  docs/CALIBRATION_LOG.md every constant, with the evidence behind it
NOTES
echo ""
