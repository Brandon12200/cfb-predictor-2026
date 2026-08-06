# HANDOFF → Phase 5 (temporary — delete when Phase 5 closes)

A briefing for a fresh session with zero conversational context. **Not authoritative over
`docs/SPEC.md`.** Refreshed at the F-close, 2026-08-05.

Read this, then `docs/PHASE5_NOTES.md` (binding cadence), then SPEC §10.

---

## (a) Current state — THE MODEL IS FROZEN

**`v2026-frozen` was cut 2026-08-05 at `6910675`.** Phases 0–4.5 are complete and merged; the
freeze sequence is closed.

- **Gates on `main`:** `make test` **691 passed / 2 skipped**, `make lint` clean, all six
  `verify-phase-*` targets PASS.
- **`factors/` and `engine/` are immutable** — `.claude/hooks/protected_paths.py` refuses edits, and
  `guard_bash.py` refuses the shell/git bypasses. Demonstrated at F-close, not assumed.
- **The freeze is also enforced BEHAVIOURALLY.** `verify-phase-3` asserts a SHA-256 fingerprint of
  the model's output over all 330 tracked games
  (`eab7ffdb90df6fb549bbed0f9ebc291e00f710f592bc4e3699e41a3f52a20e2d`). **This is the important
  one:** path protection cannot see a change that reaches output through the freeze-exempt `data/`
  seam, and that has happened **twice** (A6's metres/feet fix, the venue-timezone fallback). If this
  gate fails, model output moved.
- **Pre-flight: FREEZE-READY** (`docs/preflight_verdict_rerun.md`, run 2, 0 blockers). Run 1's
  verdict is retained and banner-marked superseded.

**⚠ If the slate-hash gate fails, do NOT update the constant.** Either the change was unintended —
revert it — or it was intended, in which case it needs a **documented SPEC §3 exception plus a new
tag**. Updating the constant hides exactly what the gate exists to show.

## (b) Work order

**Phase 5 is the automation pipeline (SPEC §10) and has not begun.** It needs its own plan-mode
cycle. Nothing from the freeze session carries into it as unfinished work.

1. **`docs/PIPELINE.md`** — still unwritten; Phase 5 owns it.
2. **Workflow files + secrets.** **The pipeline calls `scripts/*.py`, NEVER `cfb`** — the scripts are
   the canonical entry points; `cfb` is the human interface. *(This is doubly true right now: see the
   console-script defect in §(d).)*
3. **§10.6 config fields ADD to `season.json`** (kickoff windows, freeze tag, slate filter, budget
   thresholds) — Phase 5 extends a home, it does not design one (D24).
4. **The rehearsal regimen is ACCEPTANCE CRITERIA, not suggestions.**

Two open design questions carried from PHASE5_NOTES §4: **pipeline commit identity** (Actions bot vs
an authored identity — D3 forbids AI attribution, and SPEC §10 leans on the commit as tamper-evident
provenance) and **branch-protection interaction** with bot pushes.

## (c) The binding cadence (PHASE5_NOTES — do not re-derive)

- **Tuesday — grade FIRST, then predict.** The catch-up grade covers Sunday/Monday games and
  postponements; it is **idempotent** and per-game. Then snapshot → predict → commit.
- **Daily Wed–Sat line capture** — not Saturday-only. Thursday/Friday games need honest pre-kickoff
  closes. Each observation appends to `data/lines/` and **never** mutates the snapshot (the
  hash-exclusion rule).
- **Each game's closing line = the last observation before THAT game's own kickoff** — per-game
  as-of-T, already built (`closing_observation`). No schema work.
- **Cron jitter is real.** Schedule with slack before the earliest kickoff; never at the kickoff
  minute.
- **Artifact taxonomy (D22/D23):** `data/predictions/` byte-immutable forever; results/archive/
  lines/ratings/projections/graded append-only; **`reports/` are regenerable renderings** — git is
  their audit trail. Rehearsal commits **must be marked as rehearsals.**

## (d) Queued freeze-exempt fixes — verified at F-close, none started

All are outside `factors/`/`engine/`, so all are fixable now. **None was fixed during the freeze
session** — the pre-tag window stayed on what gated the tag.

1. **⚠ The `cfb` console script is broken for MOST of its subcommands — TWO unpackaged
   directories, not one.** `pyproject.toml`'s `[tool.setuptools.packages.find] include` lists
   `["cli*", "engine*", "factors*", "data*", "utils*"]` — **neither `scripts*` nor `analytics*`**.
   Verified at F-close by running the installed console script:

   | Invocation | Fails with |
   |---|---|
   | `cfb status`, `cfb grade`, `cfb report`, `cfb data snapshot`, `cfb data inspect` | `ModuleNotFoundError: No module named 'scripts'` |
   | `cfb slate <wk>`, `cfb predict week <wk>`, `cfb predict game`, `cfb predict rerun` | `ModuleNotFoundError: No module named 'analytics'` (via `cli/cfb.py:50` `_load_slate`) |

   That is **~9 invocations, including the flagship `cfb predict week`**. **`python -m cli.cfb …`
   from the repo root works** (cwd lands on `sys.path`), which is why this survived Phase 4.5's
   acceptance and why it is invisible in development.

   **The pipeline is unaffected — it calls `scripts/*.py` directly by design (§b.2)** — but the
   documented human interface is largely broken on a clean install. **Fixing only `scripts/` would
   leave `slate` and all three `predict` subcommands broken**; the fix must cover both directories.
2. **`README.md:80,118` document an invocation that errors.**
   `python main.py hypothetical --home "Ohio State" --away "Texas"` →
   `cfb: error: unrecognized arguments: --home --away`. It mixes the new subcommand form with the
   deprecated flat flags. Should read `cfb hypothetical "Ohio State vs Texas"`.
3. **`demo.sh` still drives the deprecated flat-flag path** (`python main.py --home … --away …`,
   `--list-games`, `--validate-team`). These work — the D24 shim routes them, printing a deprecation
   notice — but the demo should show the supported interface.
4. **Status label — already correct, no action.** `cfb status` reports `Frozen tag: v2026-frozen`
   (a `-dirty` suffix appears only with an unclean working tree). Verified at F-close.
5. **Dropped-game detector.** CFBD returns **888** games; the snapshot stores **734**; the 154
   dropped are FBS-vs-FCS, correctly out of scope per §16.1 — but **nothing records the count or the
   reason**, and `normalize_games`' comment claiming "the slate reconciler logs them" is false. No
   tracked FBS-vs-FBS game is currently lost, but there is **no detector** if one ever were. SPEC
   §5.5.3 wants excluded-with-reason. Cheap: the count is computable at build time.

## (e) The SP+ transition — a rehearsal item, not a footnote

**Verified live 2026-08-03: CFBD has NOT posted 2026 preseason SP+ or returning production.**
`/ratings/sp?year=2026` and `/player/returning?year=2026` both returned **0 rows**, while the 2025
equivalents returned 137/134 — the endpoints work; the data is not published. The committed snapshot
was built 2026-07-03 in the same state.

**Why this is a rehearsal item.** D10 holds with zero code change — they auto-activate when CFBD
posts. But when they land:

- **`Sandwich` wakes up** (currently 0/330 for want of SP+ ranks), and the returning-production
  prior starts moving preseason ratings.
- **Model output changes**, so **the slate-hash gate will fail — correctly.** That is the gate doing
  its job, not a defect.
- **This transition must be OBSERVED ON A REHEARSAL, not discovered on the Week-1 live run.**

**Concretely:** each rehearsal should assert whether SP+ arrived; if it has, re-measure the slate and
record the delta before the graded dress rehearsal. A frozen model with a newly-populated input is
not the model characterised at the tag — and per §(a), that needs a SPEC §3 exception entry and a new
tag, not a quiet gate update.

## (f) Reporting framing — games of interest

Preseason, **every game is NO_BET** (330/330) and that is **selectivity working as designed** (L4,
3c.5's ratified "bets rarely" posture) — not breakage. §(g) explains why structurally.

**Therefore reports should lead with "games of interest", not "bets".** A weekly report whose
headline is an empty bet list reads as a broken system to anyone who has not read the calibration
log. The self-explaining-cells rule applies: **any honest-missing or honest-empty cell states its
reason inline**, because September readers see cells, not preambles — e.g. *"no closing lines
captured (honest-missing)"*, *"NO_BET: edge 0.02 below the 0.75 floor"*.

**Attribution obligations that shape the reports (D27):** CLV and ATS% **must** be reported split by
lean side and against a naive always-lean-home baseline. Preseason leans run **195 home / 35 away
(5.57:1)** — structural, since `TravelBurden`/`ConsecutiveRoad` only penalise the visitor and
`Altitude` only advantages the host. **230 of 330 games carry a gradable lean**, so the measurement
season survives a season of NO_BET. An unsplit headline repeats D17's failure exactly. The away-lean
cell is thin (~35) and **must carry its Wilson interval**.

## (g) Two things that will look like bugs and are not

1. **Every preseason game is NO_BET.** The maximum attainable edge is **1.0023** theoretically and
   **0.8269** on this vehicle, against floors of 0.75/1.0/1.5 — so **1.5 is structurally unreachable
   and 1.0 is vehicle-unreachable**. Cause: dormant factors keep their raw weight in the 1.5400
   normalization denominator while contributing zero, so live weights sum to **~69.5% of unity**.
   Logged in `CALIBRATION_LOG` ("Edge ceiling vs the `min_edge` ladder") and asserted by a standing
   gate. **Do not "fix" this in-season** — it is a documented structural property with a 2027
   recalibration obligation.
2. **`confidence_score` barely varies** — 38 distinct values over 330 games, one covering 30.3%,
   tiers A 2 / B 318 / C 10. It is coarsely quantized and data-availability-driven (B1's ratified
   consequence). Treat `confidence_tier` as a coarse stratum, not per-game conviction.

## (h) Calendar — binding

| Date | Item |
|---|---|
| **2026-08-05** | ✅ `v2026-frozen` cut at `6910675` |
| **2026-08-14** | **Pipeline PR** |
| **2026-08-17** | **First rehearsal cycle** |
| 2026-08-29 | **Kickoff — Week 1.** D8 abolished Week 0; the opener IS Week 1 |

**Between Aug 17 and Aug 29:** two clean full-cycle rehearsals on rehearsal-marked commits, one
deliberate **failure-injection drill** proving the auto-Issue path, and a graded Week-1 dress
rehearsal. Run `pipeline-adversary` during development and **before each rehearsal**.

## (i) Standing process rules

- **`code-reviewer` on the full diff before every PR; a NO-GO is binding.** Its record is real — it
  caught a blocker or a should-fix in every PR of the freeze session, including two errors inside my
  own corrections.
- **Propose → pause → ratify** for anything touching a documented constant. Dense proposals go to
  `docs/proposals/<ITEM>.md` (deleted when ratified); **PR summaries go to `docs/pr-summaries/` and
  are retained.**
- **The six-target sweep** — any pricer-affecting change runs **all six** verify targets. `make test`
  plus the phase target you think you touched is **not** sufficient; that has failed twice.
- **A pricer-altering change must regenerate `data/projections/`** through the pipeline writer.
- **No AI attribution** in commits or PR text.
- **Owner-only:** calibration, the freeze, SPEC §16 changes, anything that spends money.

## (j) Reading list

`docs/PHASE5_NOTES.md` (cadence, binding) → SPEC §10 → `docs/2027_NOTES.md` (the drawer: dormant set,
dead constants, family tallies, the ceiling/denominator obligation) → `docs/DECISIONS.md` D22–D28 →
`docs/preflight_verdict_rerun.md` → `docs/SCHEMA.md` §3a.

*Delete this file when Phase 5 closes.*
