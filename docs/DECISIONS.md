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

---

## D4 — Phase 0 makes the full test suite green offline
**Date:** 2026-07-02
**Context:** The squashed `Initial commit: 2026 season rebuild` baked in code/test drift: the committed suite has ~18 genuine pre-existing failures (stale tests referencing removed classes e.g. `ATSRecentFormCalculator`; tests asserting old API shapes e.g. `validate_api_keys`; bugs inside dead-code modules) and a large block of tests that make **real network calls** through a sleeping rate limiter, so the suite cannot run offline/deterministically. This contradicts SPEC Phase 0 acceptance ("all existing tests pass") and the README's "305 tests" claim. Verified: stashing all Phase-0 changes reproduces the identical failure count, so the drift predates this work.
**Decision:** Get the **entire** suite green and offline within Phase 0 (owner choice over the lighter "quarantine network tests" option): delete dead modules with their tests (item 5); fix or remove stale unit tests; and mock all client/network calls (and neutralize rate-limiter sleeps) via a shared test fixture layer so `make test` runs the full suite deterministically with no network.
**Note:** This front-runs part of Phase 1's snapshot/no-network architecture (SPEC §5). Phase 1 still owns the canonical `engine passes a no-network test` enforcement; the Phase 0 mocking layer is an interim guard, not the permanent data architecture.
**Rationale:** A trustworthy green suite is the guard rail for the `main.py` decomposition (item 6) and every later phase; leaving a broken baseline would undermine the freeze/audit-trail credibility the project is built on.

---

## D5 — API tier for Phase 1: existing CFBD Tier 1 + Odds API free
**Date:** 2026-07-03
**Context:** Phase 1 (data layer v2) needs a decided API budget; CFBD moved from request-throttling to monthly call quotas, and any paid tier is an owner spend decision.
**Decision:** Use the owner's existing **CFBD Tier 1** subscription — **$1/mo, 5,000 requests/mo shared between the football and basketball APIs** — plus **The Odds API free tier** (500 credits/mo). Verified live: CFBD v2 (`https://api.collegefootballdata.com`, Bearer auth) returns 200 for `/conferences`, `/teams/fbs?year=2026`, `/calendar?year=2026`.
**Implications:** The 5,000-cap is **shared with basketball**, so the design fetches **league-wide** (year/week-scoped, all teams per call ≈ 110 CFBD calls/season) and caches to disk; the config budget guard must treat 5,000/mo as the shared ceiling. Tier 1 also exposes Weather / Live Scoreboard / Live PBP — unused by the batch weekly pipeline (Weather stays out of 2026 core per SPEC Appendix A).

---

## D6 — Phase 1 scope: core now, availability + line-movement deferred to slice 1.5
**Date:** 2026-07-03
**Context:** Phase 1 is the largest phase (~7 weeks to the freeze). Availability-report ingestion is "cut second" per SPEC §14.1, and the four Power-Four report pages are JS-rendered Sidearm `.aspx` whose data format could not be confirmed without a headless-browser pass.
**Decision:** Ship **core Phase 1** — 4-layer data architecture (clients/normalize/snapshot/engine-reads-snapshot), CFBD v2 migration, provenance manifest, canonical team registry, schedule-intelligence dataset, closing-line capture, inspection tooling — and **defer availability-report ingestion and best-effort line-movement history to a follow-up slice (1.5)**.
**Implications:** In core Phase 1, `market_sentiment` consumes only the prediction-time spread (+ CFBD opening line where present); line-movement is recorded as `missing` in the manifest and the factor's missing-movement behavior is a documented, deliberate state — never fabricated.
