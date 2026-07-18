"""Markdown report generator (Phase 4, SPEC §8 item 6) — freeze-exempt.

Renders plain-markdown weekly + season reports (no external services) from the JOIN (predictions ⋈
graded). Says plainly when a quiet slate is selectivity, not breakage (L4 / 3c.9). The report layer is
the cut-first tail of Phase 4 (SPEC §15.1): a pure downstream renderer over stored JSON — cutting it
loses nothing permanent (reports recompute from the artifacts anytime).
"""

from __future__ import annotations

from typing import Any

from analytics.attribution import per_factor
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
        "counts": {"games": len(joined), "graded": len(graded)},
    }


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
    lines = ["### Placeable strategy (real bets)", "",
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
    out += _kpi_block(ctx) + [""] + _calibration_block(ctx) + [""]
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
    out += _kpi_block(ctx) + [""] + _calibration_block(ctx) + [""]
    out += _selectivity_block(ctx) + [""] + _attribution_block(ctx) + [""]
    return "\n".join(out) + "\n"
