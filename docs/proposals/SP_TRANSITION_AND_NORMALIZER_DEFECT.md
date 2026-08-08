# SP+ transition delta — and a blocker found while measuring it

**Status: PROPOSED — awaiting owner ratification. Nothing committed, no tag moved.**
Measured 2026-08-08 on `rehearsal/sp-transition-2026-08-08` (unmerged, per D32).
Working tree carries a rebuilt week-1 snapshot; `main` is untouched.

---

## 0. The headline, before the delta

The transition ran as documented. But rebuilding the snapshot activated the **new dropped-game
detector**, and it immediately surfaced a **pre-existing, binding-principle-4 defect that was
already present at the freeze**: the team-name normalizer's fuzzy matcher silently converts FCS
schools into FBS teams, fabricating games that enter `data["games"]`.

**This changes the retag decision.** Retagging on the current vehicle would freeze *more*
contamination than the current tag holds. Details in §3; it is the reason §4 recommends what it
does.

---

## 1. What CFBD published

| Source | Baseline (at the tag) | Now | Status |
|---|---:|---:|---|
| `returning_production` | 0 rows | **136 rows** | **ARRIVED** |
| `sp_ratings` (preseason SP+) | 0 rows | **0 rows** | still unpublished |

So this is an **RP-only** transition. 132 of the 136 rows resolve onto tracked/canonical teams.

---

## 2. Model-output delta (tag-time vehicle → rebuilt snapshot)

Both sides measured through the frozen engine over the tracked slate, placeholder-seeded exactly as
`slate_fingerprint` does, so the two are comparable.

| | BEFORE (tag-time) | AFTER (rebuilt) |
|---|---:|---:|
| tracked-slate games | 330 | **331** |
| `returning_production` teams | 0 | **132** |
| `sp_ratings` teams | 0 | 0 |
| mean `rating_uncertainty` | 1.0 | 1.0 |
| max \|edge\| | 0.0000 | 0.0000 |
| **fingerprint** | `eab7ffdb90df6fb5…` | `9ac12c7d3ec0ea85…` |

**The fingerprint moved. That is the gate working, exactly as HANDOFF §(e) predicted.**

### Lean direction
| | BEFORE | AFTER |
|---|---:|---:|
| home | 195 | 197 |
| away | 35 | 33 |
| neutral | 0 | 0 |

The 5.57:1 home skew is unchanged in character (now 5.97:1) — D27's obligation is unaffected.

### Confidence tier — the largest behavioural change
| tier | BEFORE | AFTER |
|---|---:|---:|
| A | **2** | **313** |
| B | 318 | 7 |
| C | 10 | 11 |

**Tier A goes from 2 games to 313.** This is the B1-ratified consequence in action: `confidence` is
data-availability-driven, and manifest coverage jumped **39.0% → 62.8%** when returning production
landed. It changes no bet today (everything is still NO_BET), but it inverts the tier stratification
that D27's reports and the Phase-4 calibration tables are built on. **It is the single most
important line in this delta** and must be in the exception entry.

### Factor activations
| factor | BEFORE | AFTER |
|---|---:|---:|
| Altitude | 16 | 16 |
| ByeAdvantage | 71 | 71 |
| ConsecutiveRoad | 69 | 67 |
| ShortWeek | 19 | 19 |
| TravelBurden | 160 | 162 |

**`Sandwich` did NOT wake, and will not until preseason SP+ specifically is published** — it needs
SP+ *ranks*, not returning production. It does not appear on either side because it has never fired.
The other dormant factors are unchanged. The small movements in `ConsecutiveRoad`/`TravelBurden` are
schedule-shape effects from CFBD posting the full season (1638 rows vs 888 at the tag), not from RP.

### Edge distribution
Unchanged and total: **331/331 games have \|edge\| < 0.001**, and all 331 are `NO_BET`. The
structural edge ceiling (HANDOFF §(g).1) is untouched by RP. Nothing about this transition brings
the model closer to betting.

---

## 3. ⚠ BLOCKER — the normalizer fabricates games (pre-existing, present at the freeze)

`utils/normalizer.py:172-176` resolves unknown team names with
`difflib.get_close_matches(..., cutoff=0.8)`. At that cutoff, **16 distinct FCS schools resolve to
FBS teams**, 7 of them to *tracked* teams:

| CFBD school (FCS) | resolves to | tracked? |
|---|---|---|
| Mississippi Valley State | MISSISSIPPI STATE | ✅ |
| Northwestern State | NORTHWESTERN | ✅ |
| Southern | USC | ✅ |
| Southern Utah | USC | ✅ |
| North Carolina A&T | NORTH CAROLINA | ✅ |
| South Carolina State | SOUTH CAROLINA | ✅ |
| Samford | STANFORD | ✅ |
| Morgan State | OREGON STATE | |
| North Dakota / South Dakota State | NORTH DAKOTA STATE | |
| SE Louisiana | LOUISIANA | |
| Southern Illinois | NORTHERN ILLINOIS | |
| North Alabama | SOUTH ALABAMA | |
| Western Carolina | EAST CAROLINA | |
| Eastern Kentucky | WESTERN KENTUCKY | |
| Jackson State | JACKSONVILLE STATE | |

When **both** sides of an FCS game resolve, a **fabricated FBS game enters `data["games"]`**:

| CFBD row (real) | stored as | |
|---|---|---|
| Samford @ UAB | STANFORD @ UAB | tracked |
| Southern @ Houston | USC @ HOUSTON | tracked |
| Southern Utah @ Colorado State | USC @ COLORADO STATE | tracked |
| Morgan State @ Arizona State | OREGON STATE @ ARIZONA STATE | tracked |
| South Dakota State @ North Dakota | **NORTH DAKOTA STATE @ NORTH DAKOTA STATE** | *self-matchup* |

**Counts:**

| | tag-time vehicle | rebuilt |
|---|---:|---:|
| fabricated games in `data["games"]` | **≥10** | **34** |
| …touching a tracked team | ≥10 | 23 |
| tracked teams carrying a fabricated game | **10** | **12** |
| self-matchups | 0 | 1 |

**The tag-time snapshot already contained 10 of the 13 fabricated-game signatures.** This was not
introduced by the transition and not by the detector — the detector is simply the first thing that
could see it. CFBD posting the full season (including FCS-vs-FCS) is what amplified 10 → 34.

**Why it matters, concretely:** `data["games"]` feeds `team_schedule()` → schedule intelligence
(rest, travel, consecutive road, sandwich). Preseason the Elo is unaffected because no game is
completed — but **in-season, a completed FCS result would be attributed to an FBS team and move its
Elo**. Stanford would be credited with Samford's result.

**Second, separate defect from the same site:** `"California"` resolves to **`None`** — Cal is a
tracked ACC team (`CAL`). Ten real tracked-vs-tracked games (`UCLA@California`,
`Clemson@California`, `Stanford@California`, `Virginia Tech@California`, `Wake Forest@California`,
`Pittsburgh@California`, `California@NC State`, `@SMU`, `@Syracuse`, `@Virginia`) are **dropped**.
D7 records `California→CAL` as an explicit `CANONICAL_OVERRIDES` entry; the override governs the
registry build, but the normalizer's runtime alias vocabulary does not carry it.

`utils/normalizer.py` is **freeze-exempt**, so this is fixable without a §3 exception for the fix
itself — but any fix **moves model output** (schedule intel changes), so it lands inside the same
retag.

---

## 4. Retag timing — the decision, with trade-offs

Binding: a new tag must exist **before the Aug 25 live predict run**, the delta must be recorded
**before the graded dress rehearsal** (HANDOFF §(e)), and **the fingerprint constant is not an
option under any path.**

| | **A. Retag now, RP-only** | **B. Hold briefly for SP+** | **C. Fix the normalizer first, then retag once (recommended)** |
|---|---|---|---|
| Transitions | 1 now, 1 later when SP+ lands | 1, if SP+ arrives in time | 1, covering RP + the data fix |
| Fabricated games in the new frozen vehicle | **34** | 34+ | **0** |
| Cal's 10 games | still dropped | still dropped | restored |
| Risk | freezes a known principle-4 violation, and *more* of it than today | SP+ may not land before Aug 25; no control over it | needs a normalizer fix + full six-target sweep before tagging |
| Aug 25 feasibility | immediate | **uncontrollable** | ~1–2 days of work, 17 days of runway |

**Recommendation: C.** A and B both bake 34 fabricated games — including a team playing itself —
into the fingerprint that governs the season, and the whole purpose of the tag is that the frozen
artifact is trustworthy. B additionally bets the deadline on a third party. C takes one transition,
removes a known violation of binding principle #4, and still leaves 17 days.

If you prefer A or B, the exception entry must state plainly that the new tag knowingly freezes the
fabricated-game defect, with a 2027 obligation — I would not want that unrecorded.

**Not recommended under any option:** retagging before the normalizer question is *ruled on*. Doing
so spends the tag and then discovers we want another.

---

## 5. DRAFT — SPEC §3 exception entry (NOT committed; for ratification)

> ### Exception 1 — 2026-08-XX — CFBD published preseason returning production
>
> **Trigger.** `scripts/sp_watch.py` detected `returning_production` moving 0 → 136 rows
> (`sp_ratings` remains 0). D10 activates the returning-production prior with **no code change**, so
> the frozen model's inputs changed underneath the tag.
>
> **Consequence, measured on `rehearsal/sp-transition-2026-08-08`.** The behavioural fingerprint over
> the tracked slate moved `eab7ffdb90df6fb549bbed0f9ebc291e00f710f592bc4e3699e41a3f52a20e2d` →
> `9ac12c7d3ec0ea8526bfd88f7a0cd7b80b6dd64f825491758a9aa385a67306cf` (330 → 331 games). The
> `verify-phase-3` gate failed **correctly**; the constant was not updated.
>
> **What actually changed.** Manifest field coverage 39.0% → 62.8%. Confidence tier A **2 → 313**,
> B 318 → 7 (B1's data-availability-driven consequence). Leans 195/35 → 197/33. All 331 games remain
> `NO_BET` with \|edge\| < 0.001 — the structural edge ceiling is unaffected. `Sandwich` did **not**
> wake and will not until preseason SP+ ranks are published specifically.
>
> **Scope of the exception.** No code in `factors/` or `engine/` changed; no calibration constant
> changed. The exception covers the model's *inputs* changing under a ratified auto-activation
> (D10), and — under option C — the freeze-exempt normalizer correction in §3 above.
>
> **New tag:** `v2026-frozen-2` at `<commit>`, with the pinned gate vehicle (D29) re-derived from it
> and `FROZEN_VEHICLE_SHA256` updated to match. The prior tag and its fingerprint remain in the log
> as the record of what the season's first freeze was.

---

## 6. Pipeline findings from the freeze-integrity run

1. **The `role capture, week 02` / `v-does-not-exist` blocks are the job's own negative self-tests.**
   `freeze-integrity` runs `make verify-phase-3`, which runs the full suite;
   `tests/test_pipeline_preflight.py:140,146` call `emit(pf, "capture", 2)` and the helper prints.
   Working as designed — though the printing is noisy in a production log.

2. **Issue #32 is not a broken close path — it is a dedupe collision, and worse than it looks.**
   #32 was opened by an **earlier, genuinely failing** run (before the secrets were set), so its
   title is `pipeline: freeze failed`. The later green run's SP+ arrival matched the same label
   triple (`pipeline-failure` + `stage:freeze`) and was appended as a **comment**. So the most
   important signal the pipeline can emit — a freeze-invalidating data transition — is filed under a
   title that reads as a broken job, and the `title:` override never applies to an existing issue.
   *Separately,* `freeze-integrity.yml` has **no `clear-failure` step at all** (the three cadence
   workflows do). Here that is harmless — the SP+ condition is genuinely unresolved and the issue
   *should* stay open — but the close path in that workflow is untested because it does not exist.

3. **⚠ Backticks in an issue body execute as shell commands.** `report-failure` builds the body with
   `BODY="$(printf '%s…' "${{ inputs.body }}" …)"`. Actions interpolates the input into the script
   *before* bash parses it, so backticks become **command substitution**. Reproduced exactly: the
   #32 comment reads *"so  wakes up and  will fail CORRECTLY"* — `` `Sandwich` `` and
   `` `verify-phase-3` `` were executed (`command not found`) and replaced with empty strings. Today
   this only mangles our own text, but it is the classic Actions script-injection shape and it
   corrupts every issue body containing backticks — which is most of them. Fix: pass the body via
   `env:` and reference `"$BODY_INPUT"`, never interpolate `${{ }}` into a shell script.

4. **Node 20 deprecation warning** → one line for `docs/2027_NOTES.md`: the pinned
   `actions/checkout@v4` / `setup-python@v5` / `cache@v4` / `upload-artifact@v4` will need a major
   bump when GitHub retires the Node 20 runtime.

---

## 7. Repo-visibility scan

**(a) Secrets in full history — CLEAN.**

| Check | Result |
|---|---|
| Commits examined | **148** (all refs) |
| Blobs content-scanned | **779** (every text blob in the object DB, 0 skipped) |
| `.env` ever tracked | **No** — only `.env.example`, all placeholder values |
| Secret-shaped paths in any tree | none beyond `.env.example` |
| Private-key blocks, AWS `AKIA`, GitHub `ghp_/gho_/ghs_`, Slack `xox*`, Google `AIza`, Stripe `sk_/rk_`, `Bearer <token>`, key-ish assignments of long opaque values | **0 hits** |

Scanned via `git cat-file --batch-all-objects`, so unreachable/dangling blobs were included too —
not just reachable history. **No rotation is required.**

**(b) Other public-read concerns.** Two commit identities, both yours:
`Brandon12200 <BrandonJKenney1@gmail.com>` (117 commits) and
`Brandon Kenney <66864131+…@users.noreply.github.com>` (31). The **real gmail address is in 117
commit headers** and becomes publicly scrapeable on flip. That is within "expected commit identity",
but it is a one-way door — worth a deliberate yes. Going forward you can set
`git config user.email` to the `noreply` address; rewriting existing history is not worth it and
would break every commit SHA the audit trail depends on.

No other personal information, credentials, private URLs, or private-audience content found. The
docs are written for an external reader already.

**(c) DRAFT — DECISIONS entry superseding D3's privacy component (NOT committed):**

> ### D37 — Repo goes public; D3's privacy component superseded — **RATIFIED (owner, 2026-08-XX)**
> **Context.** D3 made the repo private with an option to publish in Aug 2026. Two things now argue
> for exercising it. First, **GitHub does not enforce rulesets on private personal repositories on
> the free plan**, so `main-protection` — nine required checks, force-push and deletion blocked — is
> currently **created and Active but unenforced**. Public visibility turns it on. Second, the
> project's thesis is a *publicly verifiable* pre-registration trail: a prediction committed before
> kickoff is stronger evidence when anyone can check the timestamp. Secondary: unlimited Actions
> minutes for public repos removes any budget pressure on the cadence.
> **Decision.** The repository becomes **public**. **D3's privacy component is superseded; its other
> half is unchanged** — AI tooling and decision docs remain committed, `includeCoAuthoredBy` stays
> `false`, and commit messages and PR text carry **no AI attribution**. That constraint mattered
> *because* of this moment, and it now pays off: the history is publishable as written.
> **Pre-flight.** A full-history secret scan (148 commits, 779 blobs, including unreachable objects)
> returned **clean**; `.env` was never tracked. Recorded here so the decision rests on evidence.
> **Accepted consequence.** The authoring email in 117 commit headers becomes public. Consciously
> accepted; rewriting history would break every SHA the audit trail depends on.
