"""Markdown report generator (Phase 4, SPEC §8 item 6) — freeze-exempt.

Renders plain-markdown weekly + season reports (no external services) from the JOIN (predictions ⋈
graded). Says plainly when a quiet slate is selectivity, not breakage (L4 / 3c.9). The report layer is
the cut-first tail of Phase 4 (SPEC §15.1): a pure downstream renderer over stored JSON — cutting it
loses nothing permanent (reports recompute from the artifacts anytime). Reports are **regenerable
renderings** (D23), not append-only history — git is their audit trail; `reports/` is not hook-guarded.

General rule: any honest-missing / honest-empty cell states its reason inline (September readers see
cells, not the preamble).
"""

from __future__ import annotations

from typing import Any

from analytics.attribution import by_lean_side, per_factor
from analytics.calibration import brier_score, calibration_table
from analytics.join import join
from analytics.kpis import kpi_pack
from analytics.selectivity import selectivity_report


def _pct(x: Any) -> str:
    return "—" if x is None else f"{x:.1%}"


def _num(x: Any, n: int = 2) -> str:
    return "—" if x is None else f"{x:+.{n}f}"


def report_context(joined: list[dict]) -> dict[str, Any]:
    """The full analytics pack over a joined slate (or season) — the data behind every report."""
    graded = [r for r in joined if r.get("graded")]
    return {
        "kpis": kpi_pack(graded),
        "brier": brier_score(joined),
        "calibration": calibration_table(joined),
        "selectivity": selectivity_report(joined),
        "attribution": per_factor(joined),
        "lean": by_lean_side(joined),
        "counts": {"games": len(joined), "graded": len(graded)},
    }


def _lean_cell(s: dict) -> str:
    """One side's CLV cell, stating its reason inline when empty (September readers see cells)."""
    if s["n_clv"]:
        return f"{_num(s['avg_clv'])} pts (beat close {_pct(s['clv_positive_pct'])}, n={s['n_clv']})"
    if s["n_games"]:
        return "— no closing lines captured yet (honest-missing)"
    return "— (no games on this side)"


def _lean_block(ctx: dict) -> list[str]:
    """D27's split — the PRIMARY result. Deliberately rendered before the blended KPIs, because a
    single blended headline over a 5.57:1 structural home skew is not acceptable as the headline."""
    lean = ctx["lean"]
    m, sides, base = lean["meta"], lean["sides"], lean["baseline_always_home"]

    def row(label: str, s: dict) -> str:
        w = s["wilson_95"]
        wil = f"[{w[0]:.0%}–{w[1]:.0%}]" if w else "—"
        return (f"| {label} | {s['n_games']} | {s['wins']}-{s['losses']}-{s['pushes']} | "
                f"{_pct(s['ats_win_pct'])} | {wil} | {_lean_cell(s)} |")

    ratio = f"{m['home_away_ratio']}:1" if m["home_away_ratio"] is not None else "—"
    lines = [
        "### Games of interest, by lean side (D27 — read this before the blended numbers)", "",
        f"_{m['n_with_side']} of {m['n_games']} games carry a gradable lean "
        f"({sides['home']['n_games']} home / {sides['away']['n_games']} away, {ratio})._", "",
        "| lean | games | W-L-P | ATS win% | Wilson 95% | avg CLV |",
        "|---|---|---|---|---|---|",
        row("home", sides["home"]),
        row("away", sides["away"]),
        row("_naive: always lean home_", base),
    ]

    delta = lean["vs_baseline"]["ats_delta"]
    if delta is None:
        lines += ["", "_No graded bets yet, so the model cannot be differenced against the naive "
                  "always-lean-home baseline. That comparison — not the raw win% — is what makes "
                  "the number evidence about the model (D27)._"]
    else:
        verdict = ("**above**" if delta > 0 else "**at or below**")
        lines += ["", f"_Model {_pct(lean['model_overall']['ats_win_pct'])} vs naive baseline "
                  f"{_pct(base['ats_win_pct'])} on the same games: **{delta:+.1%}** — "
                  f"{verdict} always taking the home team._"]
        if delta <= 0:
            lines += ["", "_The model's side-selection has not beaten 'always take the home team' "
                      "on this sample. That is the comparison D17 existed to force, so it is "
                      "reported at the top rather than buried._"]

    if sides["away"]["n_graded"] and sides["away"]["n_graded"] < 50:
        lines += ["", f"_The away cell is thin (n={sides['away']['n_graded']} graded). Its Wilson "
                  f"interval, not its point estimate, is the honest reading._"]
    if lean["neutral"]["n_games"]:
        lines += ["", f"_{lean['neutral']['n_games']} neutral games: {lean['neutral']['reason']}_"]
    lines += ["", f"_{m['note']}_"]
    return lines


def _kpi_block(ctx: dict) -> list[str]:
    k = ctx["kpis"]
    ats, roi, clv = k["ats"], k["roi_at_110"], k["clv"]
    w = ats["wilson_95"]
    wil = f"[{w[0]:.0%}–{w[1]:.0%}]" if w else "—"
    # Honest-missing/empty CLV states its reason inline (a bare em-dash reads as a bug).
    if clv["n"]:
        clv_cell = (f"{_num(clv['avg_clv'])} pts (beat close {_pct(clv['clv_positive_pct'])}, "
                    f"n={clv['n']})")
    elif clv["n_no_clv"]:
        clv_cell = f"— no closing lines captured (honest-missing), n={clv['n_no_clv']}"
    else:
        clv_cell = "— (no placed bets)"
    lines = ["### Placeable strategy — blended (secondary; see the lean split above)", "",
             "_Blended across both lean sides. Per D27 this is **not** the headline: with a "
             "structurally home-skewed lean, a single number here is dominated by how home teams "
             "did against the spread._", "",
             "| metric | value |", "|---|---|",
             f"| ATS record | {ats['wins']}-{ats['losses']}-{ats['pushes']} |",
             f"| ATS win% | {_pct(ats['ats_win_pct'])}  {wil} |",
             f"| ROI @ -110 | {_pct(roi['roi'])} (${roi['profit']:.2f} on {roi['n']} bets) |",
             f"| Sharpe | {k['sharpe']['sharpe'] if k['sharpe']['sharpe'] is not None else '—'} |",
             f"| max drawdown | {k['max_drawdown']} units |",
             f"| longest losing streak | {k['longest_losing_streak']} |",
             f"| avg CLV | {clv_cell} |"]
    if ats["n_graded"] == 0:
        lines += ["", "_No bets placed — the model declined the slate. Selectivity working as "
                  "designed (dormancy-as-design, 3c.9), not breakage._"]
    return lines


def _calibration_block(ctx: dict) -> list[str]:
    rows = ctx["calibration"]
    lines = ["### Calibration by tier", "",
             f"Brier score: **{ctx['brier']['brier'] if ctx['brier']['brier'] is not None else '—'}** "
             f"(n={ctx['brier']['n']}; lower is better, 0.25 = no-skill).", "",
             "| tier | n | ATS win% | mean conf | Wilson 95% |", "|---|---|---|---|---|"]
    for row in rows:
        w = row["wilson_95"]
        lines.append(f"| {row['tier']} | {row['n']} | {_pct(row['ats_win_pct'])} | "
                     f"{_pct(row['mean_confidence'])} | "
                     f"{f'[{w[0]:.0%}–{w[1]:.0%}]' if w else '—'} |")
    # The finding states itself inline — an empty-looking breakdown IS the L3/D17 result.
    lines.append("")
    total = sum(r["n"] for r in rows)
    graded = [r for r in rows if r["n"] and r["ats_win_pct"] is not None]
    if total == 0:
        lines.append("_No graded bets in these tiers yet — tier separation unmeasured. An empty "
                     "breakdown here is the honest state (e.g. an all-NO_BET slate), not a bug._")
    else:
        dom = max(rows, key=lambda r: r["n"])
        pcts = [r["ats_win_pct"] for r in graded]
        span = (max(pcts) - min(pcts)) if pcts else 0.0
        finding = f"**Finding:** {dom['n'] / total:.0%} of graded bets landed in tier {dom['tier']}"
        if len(graded) > 1:
            finding += (f"; tier ATS win% ranged {min(pcts):.1%}–{max(pcts):.1%} "
                        f"(a {span * 100:.0f}-point spread)")
        finding += "."
        if dom["n"] / total >= 0.80 and span < 0.05:
            finding += (" The confidence score barely separated winners from losers — the tiers are "
                        "not distinguishing anything (L3 / D17): confidence clustered, and the top "
                        "tier hit at the overall rate.")
        lines.append(f"_{finding}_")
    return lines


def _selectivity_block(ctx: dict) -> list[str]:
    s = ctx["selectivity"]
    p, h = s["placed"], s["no_bet_hypothetical"]
    lines = ["### Selectivity (was the skip right?)", "",
             "| bucket | games | ATS win% |", "|---|---|---|",
             f"| placed bets | {p['n_games']} | {_pct(p['ats_win_pct'])} |",
             f"| NO_BET (hypothetical lean) | {h['n_games']} | {_pct(h['ats_win_pct'])} |",
             f"| NO_BET (neutral, no lean) | {s['no_lean']['n_games']} | — (no side) |", "",
             f"_{s['note']}_"]
    if s["skip_validated"] is True:
        lines.append("_Placed bets outperformed the hypothetical NO_BET leans — the floors earned their keep._")
    return lines


def _attribution_block(ctx: dict) -> list[str]:
    a = ctx["attribution"]
    if not a["meta"].get("attributable"):
        return ["### Per-factor attribution", "",
                f"_Unavailable: {a['meta'].get('reason', 'no per-sub-signal breakdown')}._"]
    lines = ["### Per-factor attribution (converts `reasoned` → `measured` for 2027)", "",
             "| factor | fired | ATS (W-L) | ATS win% | avg CLV |", "|---|---|---|---|---|"]
    for name in sorted(a["factors"]):
        f = a["factors"][name]
        lines.append(f"| {name} | {f['n_activated']} | {f['wins']}-{f['losses']} | "
                     f"{_pct(f['ats_win_pct'])} | "
                     f"{_num(f['avg_clv']) if f['avg_clv'] is not None else '—'} |")
    lines += ["", f"_{a['meta'].get('note', '')}_"]
    return lines


def render_week(predictions_env: dict, graded_env: dict | None, *, title: str | None = None) -> str:
    joined = join(predictions_env, graded_env)
    ctx = report_context(joined)
    meta = predictions_env.get("meta", {})
    week, year = meta.get("week"), meta.get("year")
    head = title or f"2026 Week {week:02d} — Report" if isinstance(week, int) else (title or "Week Report")
    cov = ctx["counts"]
    out = [f"# {head}", "",
           f"_{cov['graded']}/{cov['games']} games graded. Model: {meta.get('model_version', '—')} "
           f"(schema v{meta.get('schema_version', '—')}), year {year}._", ""]
    out += _lean_block(ctx) + [""] + _kpi_block(ctx) + [""] + _calibration_block(ctx) + [""]
    out += _selectivity_block(ctx) + [""] + _attribution_block(ctx) + [""]
    return "\n".join(out) + "\n"


def render_season(weeks: list[tuple[dict, dict | None]], *, title: str, subtitle: str = "") -> str:
    """Aggregate a season (or the 2025 retro): a list of (predictions_env, graded_env) per week."""
    joined: list[dict] = []
    for pred_env, graded_env in weeks:
        joined += join(pred_env, graded_env)
    ctx = report_context(joined)
    cov = ctx["counts"]
    out = [f"# {title}", ""]
    if subtitle:
        out += [f"_{subtitle}_", ""]
    out += [f"_{cov['graded']}/{cov['games']} games graded across {len(weeks)} week(s)._", ""]
    out += _lean_block(ctx) + [""] + _kpi_block(ctx) + [""] + _calibration_block(ctx) + [""]
    out += _selectivity_block(ctx) + [""] + _attribution_block(ctx) + [""]
    return "\n".join(out) + "\n"
