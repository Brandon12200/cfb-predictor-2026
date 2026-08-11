# VOIDED — 2026 week 01 claim, written before its window

**This artifact is NOT a prediction claim. It is the record of one that was voided.**
It is preserved here, outside the claim tier, so the void is auditable rather than invisible.
Nothing reads it; it exists to be read by a human.

## What it is

| | |
|---|---|
| Original path | `data/predictions/2026_week_01.json` |
| Original commit | `dcaf4a3e505091ae0095ada7f0267af2f6e9652a` |
| Commit subject | `predictions: 2026 week 01 (pre-kickoff)` |
| Commit author | `cfb-pipeline <cfb-pipeline@cfb-predictor-2026.invalid>` |
| Authored | 2026-08-11 14:31:20 +0000 |
| **Blob SHA-1** | **`0cf6fa74e4351df1b952f642c73a0ffa17a8b4fd`** |
| Size | 34575 bytes |
| Produced by | Actions run [31501943662](https://github.com/Brandon12200/cfb-predictor-2026/actions/runs/31501943662) — `Weekly predict (Tue)`, `event=schedule`, conclusion `success` |
| `generated_at` | 2026-08-11T14:31:17.864072+00:00 |
| `model_version` | `v2026-frozen-2-17-ga4bf8d5` |
| `snapshot_id` | `e482833812c69fbb` |
| `schema_version` | 2 |
| Entries | **11** (of a ~138-game week-1 slate) |

The neighbouring `2026_week_01_claim.json` is a **byte-identical** copy: `git hash-object` on it
returns the blob SHA above. The marker is deliberately a **separate file** rather than a field
injected into the JSON — adding a `voided: true` key would change the bytes and destroy the very
hash that makes this record verifiable.

## Why it was voided

The pipeline was working correctly; the schedule was not yet season-aware.

`pipeline_week` returns the lowest-numbered week whose `end` has not passed, so it returned **1** for
every date from before the season through 2026-09-07. The cadence went live when the pipeline
merged, and the **first Tuesday after that — 2026-08-11 — the scheduled predict run wrote this
file**: 14 days before the intended 2026-08-25 run, from a preseason snapshot carrying 11 of ~138
games.

Because a claim is byte-immutable (D22) and its prior existence is the predict step's skip
condition, both the 2026-08-18 and 2026-08-25 runs would have **skipped**. This 11-game preseason
file would have become the season's week-1 pre-registration, permanently.

## Why voiding it was legitimate here — and will not be again

**No predicted event had occurred.** Week 1 kicks off 2026-08-29; this was voided on 2026-08-11,
eighteen days before any game in it was played, and before any external party could have relied on
it. A void that cannot be outcome-motivated is not the failure mode pre-registration exists to
prevent — it is a defective artifact removed before it could mean anything.

That reasoning has a hard expiry, recorded in **D38**: **after the first predicted event or the
first external reliance, claims and history are permanently immutable, with no override.** This is
the only void this project will ever perform.

## What shipped alongside it

The season-aware claim gate (`utils.season_calendar.claim_window_open`, D38): a claim may only be
written within one predict cadence of its week's start. Under it, 2026-08-11 and 2026-08-18 refuse
and **2026-08-25 allows**.

Enforced at **`write_predictions()`**, the shared seam both the pipeline and `cfb predict week N
--save` reach disk through, with the `weekly-predict.yml` step gate as fast-fail. Pinned by
`tests/test_claim_window.py`, which **executes** both writers — an earlier version asserted
substrings in the source and survived the guard being mutated to `if False`.

Ratified by the owner, 2026-08-11.
