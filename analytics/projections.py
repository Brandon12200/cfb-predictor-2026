"""Season win-total projections + belief-drift (SPEC §6.5) — freeze-exempt.

Each week, after ratings update, price **every remaining game** with the 2a matchup pricer and
roll up **per-team projected win totals** = wins so far + Σ(remaining-game win probabilities),
using the ratified D12 conversion (`spread_to_win_prob`, σ=16). Pure computation over the
snapshot + pricer → zero API cost, deterministic, byte-reproducible.

**Explicitly experimental** (SPEC §6.5): labeled `experimental: true`; never drives bet
recommendations in 2026. Preseason (flat priors) the projections are near-uniform — the honest
"no signal yet" state; they differentiate as games are played.

Counting convention (stated so an external comparison isn't misread as a model discrepancy):
`projected_wins` counts **all scheduled games incl. FCS opponents, regular season only** — it
matches the snapshot's `games`. FCS/unrated opponents are priced from the flat baseline prior
via the pricer's existing fallback.
"""

from __future__ import annotations

from typing import Any

from data.team_registry import get_fbs_canonical_names
from engine.matchup_pricer import compute_ratings_for_snapshot, price
from engine.power_ratings import DEFAULT_CONFIG, EloConfig, spread_to_win_prob

# Bump when the per-week record shape changes; the drift/history reader keys off this so a
# season-spanning read tolerates older weeks' files (2b is freeze-exempt, so fields may be
# added mid-season).
SCHEMA_VERSION = 1


def _game_sort_key(g: dict) -> tuple:
    return (g.get("week") if g.get("week") is not None else 0,
            str(g.get("start_date") or ""),
            str(g.get("home_team") or ""), str(g.get("away_team") or ""))


def _completed(g: dict) -> bool:
    return bool(g.get("completed")) and g.get("home_points") is not None and g.get("away_points") is not None


def build_projections(snapshot: dict, cfg: EloConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    """Per-team projected win totals for a loaded snapshot. Deterministic; `generated_at` is
    frozen from the snapshot's `built_at` (mirrors `build_ratings_export`) → byte-reproducible.
    Projects only **FBS** teams (registry-scoped, no hardcoded names); opponents absent from
    the ratings universe price from the flat prior via the pricer fallback."""
    data = snapshot["data"]
    meta = snapshot["meta"]
    games = data.get("games", [])
    venues = data.get("venues", {})
    sp = data.get("sp_ratings", {})
    rp = data.get("returning_production", {})
    ratings = compute_ratings_for_snapshot(snapshot, cfg)
    fbs = get_fbs_canonical_names()

    acc: dict[str, dict] = {}

    def _rec(team: str) -> dict:
        if team not in acc:
            tr = ratings.get(team)
            acc[team] = {
                "rating": round(tr.rating, 1) if tr else round(cfg.baseline, 1),
                "rating_uncertainty": round(tr.uncertainty(cfg), 3) if tr else 1.0,
                "wins_so_far": 0, "losses_so_far": 0, "remaining": 0,
                "projected_wins": 0.0, "games": [],
            }
        return acc[team]

    for g in sorted(games, key=_game_sort_key):
        home, away = g.get("home_team"), g.get("away_team")
        if not home or not away:
            continue
        wk, neutral = g.get("week"), bool(g.get("neutral_site"))

        if _completed(g):
            home_won = g["home_points"] > g["away_points"]
            for team, opp, is_home, won in ((home, away, True, home_won),
                                            (away, home, False, not home_won)):
                if team not in fbs:
                    continue
                rec = _rec(team)
                if won:
                    rec["wins_so_far"] += 1
                    rec["projected_wins"] += 1.0
                else:
                    rec["losses_so_far"] += 1
                rec["games"].append({
                    "week": wk, "opponent": opp, "is_home": is_home, "neutral_site": neutral,
                    "model_spread": None, "win_prob": 1.0 if won else 0.0,
                    "completed": True, "won": won})
            continue

        # Remaining game: price once, attribute to both FBS participants.
        if home not in fbs and away not in fbs:
            continue
        priced = price(home, away, ratings=ratings, season_games=games, venues=venues,
                       sp_ratings=sp, returning_production=rp, week=wk,
                       game_date=g.get("start_date"), neutral_site=neutral, cfg=cfg)
        home_wp = spread_to_win_prob(priced.home_margin, cfg)
        for team, opp, is_home, wp, spread in (
                (home, away, True, home_wp, priced.model_spread),
                (away, home, False, 1.0 - home_wp, -priced.model_spread)):
            if team not in fbs:
                continue
            rec = _rec(team)
            rec["remaining"] += 1
            rec["projected_wins"] += wp
            rec["games"].append({
                "week": wk, "opponent": opp, "is_home": is_home, "neutral_site": neutral,
                "model_spread": round(spread, 2), "win_prob": round(wp, 4),
                "completed": False, "won": None})

    teams: dict[str, dict] = {}
    for team in sorted(acc):
        rec = acc[team]
        rec["games"].sort(key=lambda x: (x["week"] if x["week"] is not None else 0))
        total = rec["wins_so_far"] + rec["losses_so_far"] + rec["remaining"]
        rec["projected_wins"] = round(rec["projected_wins"], 3)
        rec["projected_losses"] = round(total - rec["projected_wins"], 3)
        rec["schedule_missing"] = False
        teams[team] = rec

    # Every FBS team with NO games in the snapshot is included explicitly (not silently
    # dropped) with `schedule_missing` + null totals, so coverage gaps are loud. The current
    # snapshot's `games` is FBS-vs-FBS only (FCS opponents' games dropped upstream), and a
    # handful of FBS teams have no FBS-vs-FBS game resolved — a pre-existing Phase-1 data/
    # normalizer gap surfaced (not caused) here; see docs/PHASE2_NOTES.md.
    unscheduled = sorted(t for t in fbs if t not in acc)
    for team in unscheduled:
        tr = ratings.get(team)
        teams[team] = {
            "rating": round(tr.rating, 1) if tr else round(cfg.baseline, 1),
            "rating_uncertainty": round(tr.uncertainty(cfg), 3) if tr else 1.0,
            "wins_so_far": 0, "losses_so_far": 0, "remaining": 0,
            "projected_wins": None, "projected_losses": None,
            "schedule_missing": True, "games": [],
        }

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": meta.get("snapshot_id"),
            "week": meta.get("week"),
            "year": meta.get("year"),
            "generated_at": meta.get("built_at"),
            "engine": "power_ratings",
            "margin_sigma": cfg.margin_sigma,
            "experimental": True,
            "counts": "all scheduled games incl. FCS opponents, regular season only "
                      "(the snapshot is regular-season-only by construction — the builder "
                      "fetches season_type=regular)",
            "coverage": {"fbs_total": len(fbs), "scheduled": len(acc),
                         "unscheduled": unscheduled},
        },
        "teams": teams,
    }
