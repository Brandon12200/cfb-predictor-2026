# Decisions Log

Binding owner decisions made outside the resolved SPEC §16 set. Each entry records the question, the decision, and the rationale. Referenced by the phase work as `D<N>`. SPEC §16 remains the authoritative source for the originally-resolved decisions; this log captures decisions taken since.

---

## D1 — Phase 0 week-inference source
**Date:** 2026-07-02
**Context:** SPEC §4.4 says the silent-week-default fix should "derive the week from the actual date via the season calendar," but no calendar file exists yet and `season.yaml` is formally a Phase 4.5/5 artifact (SPEC §9, §10.6).
**Decision:** The Phase 0 date→week deriver reads a dedicated **`data/season_calendar_2026.json`** (season + per-week start/end dates), not `season.yaml`. Phase 4.5 later folds this calendar into `season.yaml`.
**Rationale:** Unblocks the Phase 0 bug fix with an honest, testable date→week source without prematurely claiming the Phase 4.5 config filename. Week boundaries are Saturday-anchored from Week 0 = 2026-08-29 (SPEC §16.2) on standard cadence; exact boundaries are correctable data, not code.

---

## D2 — 2025 audit-trail archive
**Date:** 2026-07-02
**Context:** SPEC §4.3 + §16.5 require importing the 2025 prediction/result JSONs into `data/archive/2025/` with a provenance note. Those JSONs currently live in `data/predictions/` and `data/results/` as `2025_week_NN*.json`.
**Decision:** **Copy** the 14 prediction + 14 result JSONs into `data/archive/2025/{predictions,results}/` with a `data/archive/2025/README.md` provenance note; leave the originals in place.
**Rationale:** `data/predictions/`, `data/results/`, and `data/archive/` are append-only historical artifacts (CLAUDE.md principle 5). Copying (not moving) satisfies §4.3/§16.5 without disturbing paths existing scripts read.

---

## D3 — Repo goes private; AI tooling is committed, not hidden
**Date:** 2026-07-02
**Context:** Policy reversal from the original "nothing AI-related may be committed" rule. The repo is going private on GitHub and may be published in Aug 2026.
**Decision:**
- Repo visibility flips to **private** (`gh repo edit Brandon12200/cfb-predictor-2026 --visibility private`).
- `.gitignore` stops ignoring `CLAUDE.md`, `IMPLEMENTATION.md`, `KICKOFF_PROMPT.md`, and `.claude/`. Still ignored: `.claude/settings.local.json`, `.claude/memory/`, `CLAUDE.local.md`, `.env*`.
- `docs/IMPLEMENTATION.md` folded into `docs/SPEC.md` as **§14 "Agentic Implementation Guide"**; Timeline renumbered §14→§15 (incl. §14.1→§15.1), Owner Decisions §15→§16 (incl. §15.1–.7→§16.1–.7); all `§15.x` cross-refs updated in SPEC.md and CLAUDE.md; `docs/IMPLEMENTATION.md` deleted.
- CLAUDE.md's "nothing AI-related may be committed" rule removed; `.claude/` config + docs now commit normally.
**Surviving constraint:** `"includeCoAuthoredBy": false` stays set and commit messages / PR text contain **no AI attribution** — history can't be easily scrubbed once the repo is published.
**Rationale:** Committing the agent infrastructure and decision docs makes future agent sessions reproducible and the engineering showcase legible, while the private-until-review posture plus the no-attribution constraint protects the publishable history.
