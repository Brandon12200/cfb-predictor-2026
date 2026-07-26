# Lint-scope fold-in — residual violations that are NOT provably mechanical

> **Lifecycle: working document.** Not authoritative over `docs/SPEC.md`. Once ruled, the
> dispositions move to `docs/FREEZE_CHECKLIST.md` (as the 2027 known-state list) and the file is
> **deleted at the next phase/session boundary**. This is scaffolding, not a record.
>
> **Status: PROPOSED — awaiting owner ruling.** Part 1 (the mechanical fixes) is committed as
> `d29fe60`; the Makefile `LINT_PATHS` / `TYPED_PATHS` fold-in lands in part 2, after these rulings.

## 1. What is already done, and the proof

153 of 170 ruff violations fixed, and mypy taken from 45 errors to 7, in the two ratified files
(`factors/factor_registry.py`, `engine/prediction_engine.py`). **Zero behaviour change, proven:**

| Evidence | Result |
|---|---|
| Week-1 `predictions` payload SHA-256 (before → after) | `0cf87d68…2371` → `0cf87d68…2371` — **identical** |
| Envelope hash (meta + payload) | **identical** |
| Tracked slate, 330 games, each driven at its own week | `ca52d761…23d3` → `ca52d761…23d3` — **identical** |
| Records differing | **0 of 330** |
| Scalar fields compared | **154,937** |
| max &#124;Δ&#124; edge / confidence / model_spread | **0.000000000000** each |
| `make test` | 449 passed, 2 skipped |
| Six verify targets (0 / 1 / 2 / 3 / 4 / 4-5) | **all PASS** |

Instrument notes, so the proof is auditable rather than trusted:

- The comparison captures the **entire engine result dict** per game, not just the persisted
  schema-v2 fields — factor values, confidence internals, variance analysis and power rating are
  all inside the 154,937 compared fields.
- Volatile keys (`generated_at`, `timestamp`, `model_version`, `built_at`, `prediction_time`) are
  excluded **by name**, and the exclusion list is written into the measurement output.
- Only the week-1 snapshot is committed, so `load_snapshot` is patched to serve that bundle at any
  week while the game's **real week** reaches the engine — A4's Vehicle B, so `compute_schedule_intel`
  fires at genuine in-season rates. Games without a line get a **deterministic** placeholder
  (`-3.0`); the placeholder need not be output-neutral because it is byte-identical on both sides.
- The instrument **self-checks**: it runs the 330-game slate twice per invocation and reports whether
  the two hashes agree. They did on every run — a non-deterministic instrument could not prove
  anything.
- The 330 games are the **both-teams-tracked** basis, which independently reproduces 3c.5's
  documented denominator.

## 2. The 17 ruff residuals — four classes

Each was held back because it changes the import graph, reorders imports, renames a binding, or
edits docstring bytes. None is a numeric-constant or control-flow change.

| # | Class | Count | Sites | Why it was not auto-applied |
|---|---|---|---|---|
| **R1** | `F401` unused import `from config import config` | 2 | `factor_registry.py:11`, `prediction_engine.py:10` | `config.py` executes `config = get_config()` **at import time**; removal is an import-graph change, not a formatting one |
| **R2** | `I001` unsorted imports | 3 blocks | both module heads + one function-local block | isort **reorders** import statements |
| **R3** | `B007` unused loop control variable | 2 | `factor_registry.py:221`, `:355` | renames a binding (`factor_name` → `_factor_name`) — an expression edit |
| **R4** | `W293` blank line contains whitespace, **inside docstrings** | 10 | 7 in `factor_registry.py`, 3 in `prediction_engine.py` | ruff classifies these as **unsafe** fixes: they edit string-literal bytes (`__doc__`) |

### R1 — the one with a real argument on both sides

`config` is genuinely unused in both files (only a comment at `factor_registry.py:81` mentions it).
The hesitation is not the name, it is the **side effect**: importing `config` runs `get_config()`,
which builds a `Config` (reads env vars, calls `_validate_config()` — which **raises** on
non-positive rate limits or cache TTL) and, on the `ProductionConfig` branch
(`ENVIRONMENT=production`), also calls `os.makedirs(log_dir, exist_ok=True)` and **requires
`ODDS_API_KEY`**.

**Why removal is nonetheless safe, verified:** `config` is imported by 13 sites, including
`data/data_manager.py:16` — which `prediction_engine.py` imports on the very next line. So in every
path that reaches either file, `config` is already in `sys.modules`. `factors/__init__.py` also
deliberately does **not** eagerly import the registry, so no import-order surprise hides there. The
only behaviour that could change is for a caller importing `factors.factor_registry` **completely
alone**, and even then the change is *when* `config` loads, never *whether*.

**Recommendation: remove.** It is the honest reading — the import is dead — and the side-effect
concern is provably not reachable. But it is your call, because "provably mechanical" was the bar
you set and this needed a four-step argument rather than an inspection.

### R2 / R3 / R4 — recommendations

- **R2 (import sorting): apply.** The reorder is within the stdlib and first-party blocks of two
  module heads; combined with R1 it is what makes `make lint` green. Its risk is the same
  import-order question as R1 and resolves the same way.
- **R3 (loop variable rename): apply.** I read both loop bodies: `factor_name` is genuinely
  unreferenced in each. Renaming an unreferenced local cannot change behaviour — this one *is*
  provably mechanical; I held it only because a rename is literally an expression edit and you asked
  me not to make that call unilaterally.
- **R4 (docstring whitespace): apply, or accept as a known state.** These are blank lines carrying
  trailing spaces *inside* docstrings. Fixing them requires `--unsafe-fixes` and changes `__doc__`
  bytes; nothing in this project reads, hashes, or renders these docstrings. **Slight preference for
  applying** so the fold-in leaves the files actually clean rather than clean-with-an-asterisk — but
  a per-file `W293` ignore is a legitimate alternative if you would rather no string bytes move.

## 3. The 7 mypy residuals — both fall OUTSIDE the two-file scope

This is the more consequential finding, and it is a scope question, not a style one.

| # | Errors | Site | What resolving it would actually require |
|---|---|---|---|
| **M1** | 6 × `attr-defined` | `factor_registry.py:215,222,223,225,231` | `normalized_weight` / `original_weight` are **set dynamically** on factor instances by the registry and never declared on `BaseFactorCalculator`. Declaring them means editing **`factors/base_calculator.py`** — a *third* frozen file, outside the ratified two-file scope |
| **M2** | 1 × `assignment` | `engine/variance_detector.py:232` | `category_analysis['inter_category_variance'] = <float>` into a dict whose other values are dicts. A *fourth* frozen file, surfaced only because mypy follows imports |

**M2 is typing noise, not a defect** — I checked the consumer: `variance_detector.py:307` reads
exactly that key as a number (`category.get('inter_category_variance', 0)`), so the heterogeneous
dict is intentional and nothing iterates the values expecting uniformity. It is also on the
**diagnostic-only** category-variance path that A3 established never reaches `variance_level`.

**Recommendation: fold both files into `LINT_PATHS` (ruff) only, and leave `TYPED_PATHS` alone**,
recording the exclusion as a one-line 2027 known state. Reasons:

1. Honest typing of these two files requires editing two *more* frozen files, which is exactly the
   silent scope expansion the two-file ruling was drawn to prevent.
2. The alternative — adding them to `TYPED_PATHS` with a blanket per-module error suppression — is
   theatre: it makes the target green while checking nothing.
3. Style is not behaviour, and you have already ruled that principle for the un-linted remainder.

If you would rather have them in `TYPED_PATHS`, the minimal honest route is **6 inline
`# type: ignore[attr-defined]` comments** in `factor_registry.py` plus one in `variance_detector.py`
— 7 comment-only edits to frozen files, no code change. I will do that instead on your word.

## 4. Two things noticed in passing — NOT part of this PR

Recording them because this is the last window in which `factors/` and `engine/` can be edited, and
because a freeze session should surface what it saw rather than bank it.

1. **`prediction_engine.py:16` labels the ratified 3c constants "PROPOSED".** The comment reads
   "Phase 3c calibration constants (PROPOSED — ratified in docs/CALIBRATION_LOG.md; frozen at the
   tag)". Those constants (`NO_BET_CONFIDENCE_FLOOR`, the tier minimums) are **RATIFIED** (3c.5 /
   3c.6, owner, 2026-07-04). A frozen file whose comment calls a ratified constant "PROPOSED" is
   precisely what the auditor's **rule 4 (cross-entry consistency)** flags — a stale label left as a
   live claim. A comment-only fix, but it edits a freeze-bound file, so it must land pre-tag or
   never. **Recommend: fix the word in part 2.**
2. **`variance_detector.py:225` carries a bare `0.3` cutoff** (`'consensus':
   cat_metrics['coefficient_of_variation'] < 0.3`) that is **not** a member of the `self.thresholds`
   dict the B4 gap covers. It is on the diagnostic-only category path, so it gates no bet — but it is
   the same *family* as B4 and the pre-flight will likely surface it. **Recommend: fold it into the
   B4 proposal as a logged known state**, not a separate cycle.

## 5. What you are asked to rule

1. **R1** — remove `from config import config` from both files? *(recommend: yes)*
2. **R2** — apply import sorting? *(recommend: yes)*
3. **R3** — rename the two unused loop variables? *(recommend: yes)*
4. **R4** — fix the 10 docstring-internal whitespace lines with `--unsafe-fixes`, or add a per-file
   `W293` ignore? *(slight preference: fix)*
5. **M1 / M2** — `LINT_PATHS` only, with the `TYPED_PATHS` exclusion recorded as a 2027 known state?
   *(recommend: yes)* — or shall I add the 7 inline `type: ignore` comments and fold into
   `TYPED_PATHS` as well?
6. **§4.1** — correct the stale "PROPOSED" label on the ratified 3c constants in
   `prediction_engine.py:16`? *(recommend: yes, comment-only, pre-tag or never)*
7. **§4.2** — carry `variance_detector.py:225`'s bare `0.3` into the B4 proposal as a logged known
   state? *(recommend: yes)*

Every ruling above is re-verified with the same before/after instrument before the PR opens, and the
`code-reviewer` runs on the complete diff after that.
