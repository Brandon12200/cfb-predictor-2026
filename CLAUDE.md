# CFB Contrarian Predictor — 2026

Rule-based college football spread model. Frozen weights, git audit trail, forward-tested only.
**The authoritative build plan is `docs/SPEC.md`; the agentic build process is §14 (Agentic Implementation Guide) within it. Read both — the relevant SPEC phase and §14 — before any work.**

## Commands
- `make test` — full test suite (must pass before any commit)
- `make verify-phase-N` — executable acceptance criteria for phase N (Phase 0 creates these targets)
- `make lint` — ruff + mypy on new code

## Binding principles (never violate; full definitions in docs/SPEC.md)
1. **Data Recency Principle:** team-quality inputs use current-season data only. Prior seasons only for market-behavior calibration and roster-continuity-aware priors (SPEC §2).
2. **No hardcoded team/conference names** anywhere in application code. All membership comes from the season team registry (SPEC §5.5).
3. **Freeze discipline:** after tag `v2026-frozen` exists, `factors/`, `engine/`, and weight/threshold config are immutable for the season.
4. **No fabricated data:** missing data is recorded as missing with provenance — never neutral-filled (SPEC §5.2).
5. Files under `data/predictions/`, `data/results/`, `data/archive/` are append-only historical artifacts. Never edit or delete.

## Workflow
- One phase = one branch (`phase-N-short-name`) = one PR. Plan before implementing.
- A phase is done only when `make verify-phase-N` passes; paste its output in the PR as evidence.
- **Custom subagents (`.claude/agents/`), use them for their jobs:** `code-reviewer` — independent read-only review of the full branch diff **before** opening the PR (the author isn't the grader; it has caught real blockers every phase — treat a **NO-GO as binding until resolved**); `test-runner` — run the suite / a subset, report only failures; `data-source-scout` — verify external API/format specifics before building or changing a data client; `calibration-auditor` — read-only audit of the whole CALIBRATION_LOG + the reverse "frozen numeric literal with no log entry" check; the **formal pre-freeze pre-flight** (immediately pre-tag, on `docs/FREEZE_CHECKLIST.md`); `pipeline-adversary` — read-only failure-class enumeration of the Phase-5 pipeline vs its handling code (run during Phase-5 dev + before each rehearsal). Read-only `Explore` agents for codebase fan-out are fine and expected.
- Keep docs current as you work: `docs/SCHEMA.md`, `docs/CODE_AUDIT.md`, `docs/PIPELINE.md`, `docs/CALIBRATION_LOG.md`, `docs/DECISIONS.md`.
- **Dense ratification proposals go to `docs/proposals/` as a file, never pasted into the terminal.** Any proposal needing a table (measured distributions, per-number calibration batches, option matrices) is written to `docs/proposals/<ITEM>.md` first and the terminal reply just points at it — table-heavy output garbles in paste transit and the owner reviews the file. Proposals are **working documents**: they carry a lifecycle header, and once ratified their content moves to `docs/CALIBRATION_LOG.md` / `docs/DECISIONS.md` and the proposal file is deleted at the next phase/session boundary.
- SPEC §16 contains resolved, binding owner decisions — follow them. When the spec is ambiguous on anything NOT covered there: ask the owner, then record the answer in `docs/DECISIONS.md`. Never invent a resolution.
- `.claude/` config (agents, settings.json, hooks), `CLAUDE.md`, and docs are committed normally (repo is private; may be published Aug 2026). Only machine-local/secret bits stay ignored: `.claude/settings.local.json`, `.claude/memory/`, `CLAUDE.local.md`, `.env*`. **Surviving constraint (D3):** commit messages and PR descriptions contain no AI attribution or tool references, and `includeCoAuthoredBy` stays `false` — history can't be easily scrubbed once published.

## Owner-only decisions (propose, never decide)
Calibration/weight changes, the freeze itself, changes to SPEC §16 decisions, anything that costs money (API tiers).

## Language & style
Python 3.11+ only (decided — do not propose rewrites). Typed on new code. JSON on disk is the source of truth; no databases.
