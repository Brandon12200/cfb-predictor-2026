"""`cfb` — the unified CLI v2 (Phase 4.5, SPEC §9).

A thin human interface over the existing `analytics/` + `scripts/` seams — NOT a parallel code path.
Each subcommand resolves the week (always echoed to stderr, so stdout stays clean for `--format json`
piping), delegates to the canonical core the Phase-5 jobs also call, formats via `cli.output`, and
returns a meaningful exit code (0 ok / 1 error / 2 degraded data).

Week inference (SPEC §9.1) fixes the 2025 silent-week-1 bug: omitting `--week` resolves to the same
value a correct explicit `--week` would (via `utils.season_calendar.resolve_week` over `season.json`);
out-of-season → exit 2, never a guess. `cfb predict game` prices off the ratified slate
(`analytics.predictions.build_predictions`), never the legacy A2 single-game path.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from cli.output import EXIT_DEGRADED, EXIT_ERROR, EXIT_OK, emit, error
from utils.season_calendar import WeekInferenceError, cli_defaults, resolve_week

_DEFAULTS = cli_defaults()
_YEAR = _DEFAULTS.get("year", 2026)

# Top-level subcommands, for the main.py deprecation shim to detect and delegate.
CFB_COMMANDS = frozenset({"predict", "hypothetical", "project", "slate", "grade", "report",
                          "data", "status"})

_PREDICT_COLUMNS = [("matchup", "MATCHUP"), ("vegas", "VEGAS"), ("model", "MODEL"),
                    ("edge", "EDGE"), ("tier", "TIER"), ("rec", "REC")]


def _resolve_week_echo(explicit: int | None) -> int:
    """Resolve the week (explicit or inferred), echo the inference to stderr, exit 2 if out of season."""
    today = datetime.now().date()
    try:
        week = resolve_week(explicit, today=today)
    except WeekInferenceError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(EXIT_DEGRADED) from exc
    if explicit is None:
        print(f"Week {week} — inferred from {today.isoformat()}", file=sys.stderr)
    return week


def _load_slate(week: int, year: int) -> dict | None:
    """The ratified schema-v2 prediction envelope for a cached snapshot's slate (offline, deterministic).
    ``None`` if no snapshot has been built for the week."""
    from analytics.predictions import build_predictions
    from data.snapshot.store import SnapshotNotFoundError, load_snapshot
    from utils.version import model_version
    try:
        snapshot = load_snapshot(week, year)
    except SnapshotNotFoundError:
        return None
    return build_predictions(snapshot, week=week, model_version=model_version())


def _row(rec: dict) -> dict:
    return {"matchup": f"{rec.get('away_team')} @ {rec.get('home_team')}",
            "vegas": rec.get("vegas_spread"), "model": rec.get("contrarian_spread"),
            "edge": rec.get("predicted_edge"), "tier": rec.get("confidence_tier"),
            "rec": rec.get("prediction_type")}


def _filtered(records: list[dict], *, only: str | None, min_edge: float, tier: str | None) -> list[dict]:
    from utils.normalizer import normalizer
    teams = {normalizer.normalize(t.strip()) for t in only.split(",")} if only else None
    out = []
    for rec in records:
        if min_edge and (rec.get("predicted_edge") or 0) < min_edge:
            continue
        if tier and rec.get("confidence_tier") != tier:
            continue
        if teams is not None and not ({rec.get("home_team"), rec.get("away_team")} & teams):
            continue
        out.append(rec)
    out.sort(key=lambda r: (r.get("predicted_edge") is None, -(r.get("predicted_edge") or 0)))
    return out


def _show_factors(records: list[dict]) -> None:
    for rec in records:
        fired = [n for n, f in (rec.get("factor_breakdown") or {}).items()
                 if isinstance(f, dict) and f.get("activated")]
        print(f"  {rec['away_team']} @ {rec['home_team']}: "
              f"{', '.join(fired) if fired else 'no factors fired (dormant)'}", file=sys.stderr)


def _emit_slate(records: list[dict], env: dict, args, *, title: str) -> int:
    rows = [_row(r) for r in records]
    if args.format == "json":
        emit("json", json_obj={"meta": env["meta"], "predictions": records})
    else:
        emit(args.format, rows=rows, columns=_PREDICT_COLUMNS, title=title)
    if getattr(args, "show_factors", False) and args.format == "table":
        _show_factors(records)
    return EXIT_OK


def _slate_degraded(env: dict) -> int:
    """EXIT_DEGRADED (+ a stderr note) when the WHOLE week's slate dropped games; EXIT_OK otherwise.
    Only whole-slate commands (predict week / rerun) use this — a single-game query's exit code must
    reflect that game, not unrelated dropped games in the same week."""
    skipped = env.get("meta", {}).get("coverage", {}).get("skipped") or []
    if skipped:
        print(f"degraded: {len(skipped)} game(s) dropped (no line / unresolved): "
              f"{', '.join(skipped)}", file=sys.stderr)
        return EXIT_DEGRADED
    return EXIT_OK


# ── predict ──────────────────────────────────────────────────────────────────────────────────────

def cmd_predict_week(args) -> int:
    week = _resolve_week_echo(args.week)
    env = _load_slate(week, args.year)
    if env is None:
        return error(f"No snapshot for {args.year} week {week}. Run `cfb data snapshot --week {week}`.")
    records = _filtered(env["predictions"], only=args.only, min_edge=args.min_edge, tier=args.tier)
    if args.save:
        rc = _save_slate(env, week, args.year)
        if rc:
            return rc
    _emit_slate(records, env, args, title=f"Week {week} — {len(records)} game(s)")
    return _slate_degraded(env)


def cmd_predict_rerun(args) -> int:
    # Re-execute from the cached snapshot (offline, zero API) — identical to the original run since
    # build_predictions is a pure function of the snapshot. Same core as predict week, view-only.
    args.save = False
    return cmd_predict_week(args)


def cmd_predict_game(args) -> int:
    from utils.normalizer import normalizer
    raw = args.matchup
    sep = "@" if "@" in raw else (" vs " if " vs " in raw else None)
    if sep is None:
        return error('Parse error: use `cfb predict game "AWAY @ HOME"`.')
    away_raw, home_raw = (p.strip() for p in raw.split(sep, 1))
    away, home = normalizer.normalize(away_raw), normalizer.normalize(home_raw)
    if not away or not home:
        bad = away_raw if not away else home_raw
        return error(f"Unknown team '{bad}'. Check the name (see `cfb slate` for the week's teams).")
    week = _resolve_week_echo(args.week)
    env = _load_slate(week, args.year)
    if env is None:
        return error(f"No snapshot for {args.year} week {week}. Run `cfb data snapshot --week {week}`.")
    match = [r for r in env["predictions"] if r.get("home_team") == home and r.get("away_team") == away]
    if not match:
        return error(f"{away} @ {home} is not in the week {week} slate. For any matchup use "
                     f'`cfb hypothetical "{away} vs {home}"`.')
    return _emit_slate(match, env, args, title=f"Week {week}: {away} @ {home}")


def _save_slate(env: dict, week: int, year: int) -> int:
    """Persist the slate to data/predictions/ (the canonical claim). Refuses to overwrite an existing
    week file — predictions are byte-immutable (D22); use the pipeline / a new week to (re)write."""
    from scripts.build_predictions import PREDICTIONS_DIR, write_predictions
    path = PREDICTIONS_DIR / f"{year}_week_{week:02d}.json"
    if path.exists():
        return error(f"{path.relative_to(PREDICTIONS_DIR.parent.parent)} already exists — predictions "
                     f"are byte-immutable (D22). View with `cfb predict rerun --week {week}`.")
    write_predictions(env, path)
    print(f"Saved {path.relative_to(PREDICTIONS_DIR.parent.parent)}", file=sys.stderr)
    return EXIT_OK


# ── slate ────────────────────────────────────────────────────────────────────────────────────────

def cmd_slate(args) -> int:
    week = _resolve_week_echo(args.week)
    env = _load_slate(week, args.year)
    if env is None:
        return error(f"No snapshot for {args.year} week {week}. Run `cfb data snapshot --week {week}`.")
    rows = [{"matchup": f"{r['away_team']} @ {r['home_team']}", "vegas": r.get("vegas_spread"),
             "data_quality": r.get("data_quality"), "rec": r.get("prediction_type")}
            for r in sorted(env["predictions"], key=lambda r: r["game_id"])]
    cov = env["meta"]["coverage"]
    if args.format == "json":
        emit("json", json_obj={"meta": env["meta"], "slate": rows})
    else:
        emit(args.format, rows=rows,
             columns=[("matchup", "MATCHUP"), ("vegas", "VEGAS"),
                      ("data_quality", "DATA_Q"), ("rec", "REC")],
             title=f"Week {week} slate — {cov['written']} game(s) with a line")
        if cov.get("skipped"):
            print(f"\nDropped ({len(cov['skipped'])}, no line / unresolved): "
                  f"{', '.join(cov['skipped'])}")
    return EXIT_DEGRADED if cov.get("skipped") else EXIT_OK


# ── delegating wrappers (canonical cores; Phase-5 jobs call the same) ──────────────────────────────

def cmd_hypothetical(args) -> int:
    from cli.app import run_hypothetical
    away_raw, home_raw = _split_vs(args.matchup)
    if away_raw is None:
        return error('Parse error: use `cfb hypothetical "TEAM A vs TEAM B"`.')
    argv = ["--away", away_raw, "--home", home_raw, "--format", args.format]
    if args.neutral_site:
        argv.append("--neutral-site")
    if args.date:
        argv += ["--date", args.date]
    if args.show_factors:
        argv.append("--show-factors")
    return run_hypothetical(argv)


def _split_vs(raw: str):
    sep = " vs " if " vs " in raw else ("@" if "@" in raw else None)
    if sep is None:
        return None, None
    a, b = (p.strip() for p in raw.split(sep, 1))
    return a, b


def cmd_project(args) -> int:
    from cli.app import run_project
    argv = ["--format", args.format]
    if args.team:
        argv += ["--team", args.team]
    if args.history:
        argv.append("--history")
    return run_project(argv)


def cmd_grade(args) -> int:
    from scripts.grade import main as grade_main
    week = _resolve_week_echo(args.week)
    return grade_main(["--week", str(week), "--year", str(args.year)])


def cmd_report(args) -> int:
    from scripts.build_reports import main as report_main
    if args.retro:
        return report_main(["--retro"])
    if args.season:
        return report_main(["--season", "--year", str(args.year)])
    week = _resolve_week_echo(args.week)
    return report_main(["--week", str(week), "--year", str(args.year)])


def cmd_data_snapshot(args) -> int:
    from scripts.build_snapshot import main as snapshot_main
    week = _resolve_week_echo(args.week)
    return snapshot_main(["--week", str(week), "--year", str(args.year)])


def cmd_data_inspect(args) -> int:
    from scripts.inspect_snapshot import main as inspect_main
    week = _resolve_week_echo(args.week)
    argv = ["--week", str(week), "--year", str(args.year)]
    if args.game:
        argv += ["--game", args.game]
    return inspect_main(argv)


def cmd_status(args) -> int:
    from scripts.status import main as status_main
    from utils.version import model_version
    # Current week + frozen tag alongside the source-health/quota view.
    today = datetime.now().date()
    try:
        week = resolve_week(None, today=today)
        print(f"Current week: {week} (inferred from {today.isoformat()})")
    except WeekInferenceError:
        print(f"Current week: — (outside the season as of {today.isoformat()})")
    print(f"Frozen tag: {model_version()}")
    return status_main(["--ping"] if args.ping else [])


# ── parser ───────────────────────────────────────────────────────────────────────────────────────

def _add_format(p: argparse.ArgumentParser, *, choices=("table", "json", "csv")) -> None:
    p.add_argument("--format", choices=list(choices), default=_DEFAULTS.get("format", "table"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfb",
        description="CFB Contrarian Predictor — slate-first terminal workflow (SPEC §9). "
                    "Week is inferred from today's date (echoed) unless --week is given.")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    # predict week / game / rerun
    predict = sub.add_parser("predict", help="Run predictions.").add_subparsers(
        dest="predict_command", metavar="<week|game|rerun>", required=True)

    pw = predict.add_parser("week", help="Predict the whole slate for a week (default: inferred).")
    pw.add_argument("week", nargs="?", type=int, default=None)
    pw.add_argument("--only", help='Restrict to games involving these teams (comma-separated).')
    pw.add_argument("--min-edge", type=float, default=_DEFAULTS.get("min_edge", 0.0), metavar="PTS")
    pw.add_argument("--tier", choices=["A", "B", "C"], default=_DEFAULTS.get("tier"))
    pw.add_argument("--show-factors", action="store_true")
    pw.add_argument("--save", action="store_true", default=_DEFAULTS.get("save", False),
                    help="Persist to data/predictions/ (refuses to overwrite; pipeline's job).")
    pw.add_argument("--no-save", dest="save", action="store_false")
    _add_format(pw)
    pw.set_defaults(func=cmd_predict_week, year=_YEAR)

    pg = predict.add_parser("game", help='Predict one slate game: "AWAY @ HOME".')
    pg.add_argument("matchup")
    pg.add_argument("--week", type=int, default=None)
    pg.add_argument("--show-factors", action="store_true")
    _add_format(pg)
    pg.set_defaults(func=cmd_predict_game, year=_YEAR, only=None, min_edge=0.0, tier=None, save=False)

    pr = predict.add_parser("rerun", help="Re-run a week from the cached snapshot (offline).")
    pr.add_argument("--week", type=int, default=None)
    pr.add_argument("--only")
    pr.add_argument("--min-edge", type=float, default=_DEFAULTS.get("min_edge", 0.0), metavar="PTS")
    pr.add_argument("--tier", choices=["A", "B", "C"], default=_DEFAULTS.get("tier"))
    pr.add_argument("--show-factors", action="store_true")
    _add_format(pr)
    pr.set_defaults(func=cmd_predict_rerun, year=_YEAR, save=False)

    # hypothetical
    hy = sub.add_parser("hypothetical", help='Price any matchup: "TEAM A vs TEAM B".')
    hy.add_argument("matchup")
    hy.add_argument("--neutral-site", action="store_true")
    hy.add_argument("--date")
    hy.add_argument("--show-factors", action="store_true")
    _add_format(hy, choices=("table", "json"))
    hy.set_defaults(func=cmd_hypothetical)

    # project
    pj = sub.add_parser("project", help="Experimental season win-total projections + drift.")
    pj.add_argument("--team")
    pj.add_argument("--history", action="store_true")
    _add_format(pj, choices=("table", "json"))
    pj.set_defaults(func=cmd_project)

    # slate
    sl = sub.add_parser("slate", help="A week's games, lines, data quality, and dropped games.")
    sl.add_argument("week", nargs="?", type=int, default=None)
    _add_format(sl)
    sl.set_defaults(func=cmd_slate, year=_YEAR)

    # grade
    gr = sub.add_parser("grade", help="Grade a week's predictions (CLV + ATS) into data/graded/.")
    gr.add_argument("--week", type=int, default=None)
    gr.set_defaults(func=cmd_grade, year=_YEAR)

    # report
    rp = sub.add_parser("report", help="Render a weekly / season / retro markdown report.")
    grp = rp.add_mutually_exclusive_group()
    grp.add_argument("--week", type=int, default=None)
    grp.add_argument("--season", action="store_true")
    grp.add_argument("--retro", action="store_true")
    rp.set_defaults(func=cmd_report, year=_YEAR)

    # data snapshot / inspect
    data = sub.add_parser("data", help="Data ops (snapshot build / inspect).").add_subparsers(
        dest="data_command", metavar="<snapshot|inspect>", required=True)
    ds = data.add_parser("snapshot", help="Prefetch + cache all inputs for a week (online).")
    ds.add_argument("--week", type=int, default=None)
    ds.set_defaults(func=cmd_data_snapshot, year=_YEAR)
    di = data.add_parser("inspect", help="Show a snapshot's provenance manifest.")
    di.add_argument("--week", type=int, default=None)
    di.add_argument("--game", default=None, help='e.g. "AWAY@HOME"')
    di.set_defaults(func=cmd_data_inspect, year=_YEAR)

    # status
    st = sub.add_parser("status", help="Current week, frozen tag, API quota, cache freshness.")
    st.add_argument("--ping", action="store_true", help="Live CFBD reachability check.")
    st.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or EXIT_OK
    except SystemExit as exc:  # week-inference exit(2) propagates as the process code
        return int(exc.code) if isinstance(exc.code, int) else EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
