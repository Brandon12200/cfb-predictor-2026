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

## One thing surfaced, deliberately NOT fixed here

**`factors/factor_registry.py:165` carries the identical stale-label defect that ruling 6 fixed.**
The `DesperationIndex` threshold comment reads *"threshold 2.0 -> 1.0 (Phase 3c, **PROPOSED** —
CALIBRATION_LOG 3c)"*. That constant is **RATIFIED** (3c.3, owner, 2026-07-04).

It was left untouched because part-2 step 1 said *"nothing else in `factors/` or `engine/` moves"*,
and ruling 6 named only `prediction_engine.py:16`. It is flagged rather than fixed or banked:

- It is the **same defect class** the owner just approved fixing — a stale label presented as a live
  claim, which is what the auditor's **rule 4 (cross-entry consistency)** exists to catch.
- It is **comment-only** and **pre-tag-or-never**, so the window closes with this PR's merge.

**One word before merge folds it in.** Otherwise it becomes a 2027 known-state line.

## Scope discipline

`factors/` and `engine/` changes are confined to the two ratified files. **No numeric constant, no
expression, and no control flow was touched anywhere** — the substantive diff is imports,
annotations, two loop-variable renames, and comment/whitespace text. `TYPED_PATHS`, `pyproject.toml`,
`data/`, `cli/`, and every calibration value are untouched.

## Reviewer

`code-reviewer` on the complete diff (`d29fe60` through part 2) — verdict recorded below at review
time. A **NO-GO is binding**.
