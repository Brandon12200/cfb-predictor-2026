# Lint-scope fold-in PR summary — the last pre-tag edit to `factors/` and `engine/`

> **Lifecycle.** A PR summary — a durable record of what shipped and why, **RETAINED, not retired.**
> `docs/pr-summaries/` is a stable home explicitly **outside** the proposal lifecycle (owner ruling,
> 2026-07-25): these are not proposals and they do not expire. The authoritative records remain
> `docs/FREEZE_CHECKLIST.md` (the completed checklist item + the 2027 known-state list) and the
> `Makefile`; this captures the review context around them.
>
> **Status:** open, awaiting owner merge. **Branch:** `lint-scope-fold-in` (base `ca29ec4`).

---

## What shipped

The pre-freeze lint-scope fold-in from `docs/FREEZE_CHECKLIST.md`, carried since the 3c code review
(should-fix #2) and deferred twice. It had to land **pre-tag** because fixing style errors *edits
freeze-bound files* — impossible after `v2026-frozen`. **All 170 ruff violations in the two ratified
files are resolved and both are now in `LINT_PATHS`.**

The work was deliberately split so the risky part was never bundled with the safe part:

- **Part 1 (`d29fe60`)** — the 153 provably-inert fixes: blank-line/trailing whitespace, PEP 585/604
  annotation modernization, unused stdlib import removal, duplicate-`inspect` dedup, and two
  `dict[str, Any]` local annotations that took mypy from **45 errors to 7**.
- **Part 2** — the 17 residuals that were **not** provably mechanical, each applied only under an
  explicit owner ruling (`docs/proposals/LINT_FOLDIN_RESIDUALS.md`, rulings 1–7, now spent and
  deleted per its lifecycle header).

## Evidence — zero behaviour change, proven, not asserted

Measured against the **original pre-change baseline**, i.e. across both parts combined:

| Evidence | Result |
|---|---|
| Week-1 `predictions` payload SHA-256 | `0cf87d68…2371` → `0cf87d68…2371` — **identical** |
| Envelope hash (meta + payload) | **identical** |
| Tracked slate, 330 games, each at its own week | `ca52d761…23d3` → `ca52d761…23d3` — **identical** |
| Records differing | **0 of 330** |
| Scalar fields compared | **154,937** |
| max &#124;Δ&#124; edge / confidence / model_spread | **0.000000000000** each |
| `make test` | 449 passed, 2 skipped |
| `make lint` (widened scope) | `All checks passed!` / `Success: no issues found in 40 source files` |
| `verify-phase-0 / 1 / 2 / 3 / 4 / 4-5` | **all PASS** |

**Why the instrument is trustworthy**, since the whole PR rests on it:

1. It compares the **entire engine result dict** per game — factor values, confidence internals,
   variance analysis, power rating — not merely the persisted schema-v2 fields.
2. Volatile keys (`generated_at`, `timestamp`, `model_version`, `built_at`, `prediction_time`) are
   excluded **by name**, and the exclusion list is written into the measurement output rather than
   applied silently.
3. It **self-checks its own determinism**: every invocation runs the 330-game slate twice and reports
   whether the hashes agree. They did on every run — a non-deterministic instrument proves nothing.
4. Only the week-1 snapshot is committed, so `load_snapshot` is patched to serve it at any week while
   the game's **real week** reaches the engine (A4's Vehicle B), so `compute_schedule_intel` fires at
   genuine in-season rates. Games without a line get a deterministic `-3.0` placeholder — which need
   not be output-neutral, because it is byte-identical on both sides of the comparison.
5. The 330-game basis independently reproduced 3c.5's documented both-teams-tracked denominator.

Per doctrine (d)(1), all six verify targets were run — not `make test` plus the phase target that
looked relevant. Nothing regenerated `data/projections/`, correctly: no pricer input moved.

## Rulings applied in part 2

| Ruling | Applied |
|---|---|
| **R1** | `from config import config` removed from both files. The side-effect concern (`config.py` runs `get_config()` at import; the production branch does `os.makedirs` + requires `ODDS_API_KEY`) is not reachable — `data/data_manager.py:16` imports `config` and `prediction_engine` imports `data_manager` on the next line, so `config` is in `sys.modules` on every path. The re-run hash proof is the backstop. |
| **R2** | Import sorting applied to both module heads and the one function-local block. |
| **R3** | Both unused loop control variables renamed `factor_name` → `_factor_name` (`:219`, `:353`). Both bodies were confirmed free of the binding before the rename. |
| **R4** | 10 docstring-internal whitespace lines fixed. **Constraint honoured:** the unsafe-fix pass was scoped `--select W293` only — no blanket `--unsafe-fixes`. Verified after: the diff's non-whitespace lines are exactly the R1/R2/R3 changes, nothing else. |
| **M1/M2** | `LINT_PATHS` only; `TYPED_PATHS` unchanged; no inline `type: ignore` comments. Exclusion recorded as a 2027 known state. |
| **6** | The stale `PROPOSED` label at `prediction_engine.py:15` now reads `RATIFIED (owner, 2026-07-04; CALIBRATION_LOG 3c.5 / 3c.6)`. Comment-only. |
| **7** | Carried to the B4 proposal (post-merge), not into this PR. |

## Ruling 6 extended to the defect class (`1f264cc`)

The owner ruled that ruling 6's intent covers the **defect class, not the single site**, so
`factors/factor_registry.py:165` was corrected the same way: the `DesperationIndex` threshold comment
now reads **RATIFIED (owner, 2026-07-04; CALIBRATION_LOG 3c.3)** instead of *"(Phase 3c, PROPOSED —
CALIBRATION_LOG 3c)"*. The bare `3c` reference was also made precise — `3c` spans 3c.1–3c.10 and
several unrelated dispositions; `3c.3` is the section that actually ratifies this threshold.

Comment-only. Re-proven against the **original** pre-change baseline: week-1 payload and envelope
hashes identical, tracked slate identical, **0 of 330** records differ, max |Δ| any numeric
`0.000000000000`, `make test` 449 passed / 2 skipped, `make lint` clean, all six verify targets PASS.

## The sweep was too narrow — corrected, with five sites remaining

**The stated answer to "are these the only two `PROPOSED` strings" is: yes for that literal
case-sensitive string, but that framing understated the problem, and the reviewer caught it.** The
same defect class also appears as `PROVISIONAL`, as lowercase *"proposed disposition"*, and as
future-tense *"ratified … before the freeze"* — none of which a grep for `PROPOSED` matches. Sites
verified against the log's ratification stamps, and **all five are left untouched pending a ruling**:

| Site | Text | Actual status | Severity |
|---|---|---|---|
| `engine/power_ratings.py:33-34` | "Calibration constants (D9/D11/D12) — **PROVISIONAL** until the dispersion test passes and the owner ratifies… **Do not treat as final.**" | D9 / D11 / D12 all **RATIFIED** (owner, 2026-07-03) | **Clearest of all** — it actively instructs a reader *not* to treat frozen constants as final. Self-contradicts the `EloConfig` docstring three lines below ("ratified in CALIBRATION_LOG.md, frozen at the tag") |
| `factors/physical_coefficients.py:18,20` | "**Calibration status (D17): PROPOSED**… Ratified… **before the freeze**" | 3b.1 **RATIFIED** (owner, 2026-07-03) | Clear-cut; self-contradicts the `PhysicalCoefficients` docstring below ("Owner-ratified calibration; frozen at the tag") |
| `factors/scheduling_fatigue.py:11` | "weights are ratified… **before the freeze**" (future tense) | 3b.2 **RATIFIED** (owner, 2026-07-03) | Clear-cut, same future-tense staleness |
| `factors/coaching_edge.py:214,223-225` | "DORMANT (Phase 3c **proposed disposition**)… Proposed disposition, ratified in the Phase 3c batch" | 3c.2 **RATIFIED** (owner, 2026-07-04) | Weaker — already says "ratified"; lacks owner/date stamp |
| `factors/style_mismatch.py:34` | "**PROPOSED** → ratified in CALIBRATION_LOG 3d" | 3d.3 **RATIFIED** (owner, 2026-07-04) | Weakest — describes the transition; bare `3d` should be `3d.3` |

Three are clear-cut instances of exactly what ruling 6 corrected; two are weaker, since they already
mention ratification and merely lack a stamp. All are **comment-only** and **pre-tag-or-never** —
`factors/` and `engine/` both freeze at the tag, so this PR's merge closes the window on all five.

### All five fixed under the final ruling (`bedce6a`)

The owner ruled all five ride in this PR, as its **final** extension: any site found after this
sweep goes to the 2027 known-state list, not into a pre-tag PR (pre-flight findings excepted).

Each was restated with a precise owner/date stamp and a **sub-entry** log reference, following the
precedent set at 3c.3 — bare phase numbers were the imprecision being corrected, so `3c` → `3c.2`,
`3d` → `3d.3`, and so on. Every stamp was verified against the log's ratification header **before**
being written, then re-verified independently by the reviewer:

| File | Was | Now |
|---|---|---|
| `engine/power_ratings.py:33` | "PROVISIONAL… Do not treat as final" | RATIFIED (owner, 2026-07-03; **D9 / D11 / D12**) |
| `factors/physical_coefficients.py:18` | "PROPOSED… ratified before the freeze" | RATIFIED (owner, 2026-07-03; **3b.1**), evidence-class `reasoned` (D17) |
| `factors/scheduling_fatigue.py:11` | "ratified… before the freeze" | RATIFIED (owner, 2026-07-03; coefficients **3b.1**, weights **3b.2**; shared cutoffs **B5**, 2026-07-16) |
| `factors/coaching_edge.py:214,223` | "proposed disposition" | RATIFIED (owner, 2026-07-04; **3c.2**) |
| `factors/style_mismatch.py:34` | "PROPOSED → ratified in 3d" | RATIFIED (owner, 2026-07-04; **3d.3**) |

`power_ratings.py:33` was the most consequential of the five: it actively instructed the reader
**not to treat the Elo constants as final**, while the `EloConfig` docstring six lines below already
said "ratified… frozen at the tag". A 2027 reader hitting that first line would have had grounds to
believe the frozen constants were still open.

## Sweep methodology, and whether it is comprehensive

Stated explicitly, because the first attempt was too narrow and that is the failure worth recording:
**the original sweep grepped only the literal case-sensitive string `PROPOSED`.** That answered the
question asked but not the question that mattered — the same defect wore other clothes.

**Patterns searched** (case-insensitive, all of `factors/` and `engine/`, including docstrings):
`PROPOSED`, `provisional`, `proposed disposition`, `before the freeze`, `do not treat as final`,
`to be ratified`, `will be ratified`, `not yet ratified`, `awaiting`, `pending`, `tentative`,
`subject to change`, `TBD`, `preliminary`, `unratified`, `pre-ratification`.

**The reviewer ran a second, independent sweep** with patterns of its own choosing — `draft`,
`interim`, `placeholder`, `not final`, `un-ratified`, `still proposed`, `WIP`, `in progress`,
`temporary`, `not ratified`, `open question`, `needs owner`, `open item`. It surfaced no sixth
stale-status site. Its only additional hits were `# placeholder` comments at `coaching_edge.py:289`
and `situational_context.py:236,270`, which describe **unimplemented H2H/coaching data** — already
covered by the A1 / B10 dormancy dispositions, not calibration-status claims.

**Declared: the sweep is comprehensive.** One match survives by design —
`engine/power_ratings.py:39`, the `EloConfig` docstring's *"proposed via the dispersion test,
ratified in CALIBRATION_LOG.md, frozen at the tag"*. That is accurate past-tense process history
sandwiched between "ratified" and "frozen", not a live status claim. The reviewer read the full
surrounding docstring and independently agreed with leaving it.

**No sixth site turned up during this pass.**

### Third review — the five-site commit

`code-reviewer` on `bedce6a`: **GO, no blockers, no should-fixes, no nits.** It verified the stamps
against the log line-by-line (including the three-part `scheduling_fatigue.py` claim, confirming B5
covers `activation_threshold = 0.4` and the `max_impact × 0.6` cutoff, and that 3b.2's six weights
match the live `_configure` calls exactly), confirmed no prose was lost in any rewrap, and — most
usefully — **checked the actual constant values byte-for-byte**: `EloConfig`'s fields,
`PhysicalCoefficients`' eight coefficients, the six `scheduling_fatigue` weights,
`coaching_edge`'s `return 0.0`, and `style_mismatch`'s ±1.5 bounds are all unchanged.

## Scope discipline

The **code** fold-in is confined to the two ratified files. The stale-label corrections reach three
further frozen files (`power_ratings.py`, `physical_coefficients.py`, `scheduling_fatigue.py`,
`coaching_edge.py`, `style_mismatch.py`) under the owner's explicit final ruling, and are
**comment-only in every case** — verified by the reviewer against the actual constant values. **No numeric constant, no
expression, and no control flow was touched anywhere** — the substantive diff is imports,
annotations, two loop-variable renames, and comment/whitespace text. `TYPED_PATHS`, `pyproject.toml`,
`data/`, `cli/`, and every calibration value are untouched.

## Reviewer — **GO**

`code-reviewer` on the complete diff (`ca29ec4..HEAD`, all three commits). **No blockers, one nit.**

What makes the verdict worth something here: the reviewer did not take the author's evidence on
trust. It **re-ran the gates itself** — `ruff` on the widened `LINT_PATHS`, `mypy` on `TYPED_PATHS`,
`make test`, and all six verify targets — and confirmed each matches the claims in this summary,
the commit messages and the checklist verbatim. It also independently reproduced the 2027
known-state error counts (exactly 6 `attr-defined` + 1 `assignment` at `variance_detector.py:232`).

Findings it confirmed by direct inspection rather than assertion:

- **R1 is safe for a reason I had not fully stated:** `config.py` also calls `load_dotenv()` at
  import. The reviewer verified those side effects still fire on every reachable path, since
  `prediction_engine.py:10` imports `data.data_manager` (which imports `config`) *before*
  `factors.factor_registry` at `:12`. It further grepped both files for any surviving bare `config`
  runtime reference — the only hit is historical prose in a comment.
- **R2:** checked `variance_detector.py` and `base_calculator.py` for a circular-import hazard the
  sort could expose; none, and a clean import of both modules succeeds.
- **R3:** read both loop bodies in full and confirmed `factor_name` is genuinely unreferenced.
- **Ruling 6:** verified the new `RATIFIED (owner, 2026-07-04)` text against `CALIBRATION_LOG`
  `3c.5` (`:369`) and `3c.6` (`:434`) — status and date match exactly — and checked the reflowed
  comment line-by-line against the original for dropped wording. None.
- **Scope:** exactly five files touched; `TYPED_PATHS`, `pyproject.toml`, `data/`, `cli/`,
  `CALIBRATION_LOG.md`, `DECISIONS.md` and every other `factors/`/`engine/` file confirmed
  zero-diff.

**Nit (at first review):** `factors/factor_registry.py:165`'s identical stale `PROPOSED` label —
since **fixed** under the extended ruling (`1f264cc`).

### Second review — the incremental commit

`code-reviewer` re-ran on `1f264cc` alone: **GO**, no blockers. It confirmed the commit is
comment-only (the `DesperationIndex` config dict on the line below is byte-identical), that `3c.3` is
the correct and more precise log reference, and that no explanatory wording was lost in the rewrap.

**It also caught a real gap in my sweep**, which is the reason the review exists: I had grepped the
literal string `PROPOSED`, so I missed `PROVISIONAL`, lowercase *"proposed disposition"*, and the
future-tense *"ratified … before the freeze"* variants — three further sites, including
`engine/power_ratings.py:33-34`, which is arguably the worst-worded of any of them. The table above
is the corrected result, independently re-verified against the log's ratification stamps before
being written down. The `1f264cc` commit message was amended to state the corrected scope; its
**tree hash is unchanged**, so the content the reviewer approved is byte-identical.

**Process note:** the reviewer's sandbox ran `git checkout af7b0ea -- .` during its investigation,
which the harness flagged as a potentially destructive action. Checked immediately afterwards: the
working tree was already at that exact commit, so it was a no-op — `HEAD` correct, tree clean, no
stash, empty diff. No damage, recorded because a read-only agent should not be writing to the tree.
