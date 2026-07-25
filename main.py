#!/usr/bin/env python3
"""Legacy entry point — now a **deprecation shim** over the `cfb` CLI v2 (Phase 4.5, SPEC §9, D24).

`cfb <command>` (see `cfb --help`) is the interface. This shim keeps the old flat flags working for
one release (retired in 2027) but **delegates**: `cfb` subcommands pass straight through; the legacy
flat flags print a deprecation notice and route to their `cfb` equivalent. The single-game
`--home/--away` path now routes to `cfb predict game` (the ratified slate) / `cfb hypothetical`, and
**no longer calls `cli.app.run_single_prediction`** — which is thereby consumer-less (D24; the A2
second engine, reverse-audit finding, is retired at freeze in Phase 5).
"""

import sys

from cli.args import parse_arguments  # re-exported for backward compatibility

__all__ = ["main", "parse_arguments"]


def _deprecation(what: str, use: str) -> None:
    print(f"[deprecated] `main.py` {what} is deprecated (removed after the 2026 season). Use: {use}",
          file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    from cli.cfb import CFB_COMMANDS
    from cli.cfb import main as cfb_main

    # New unified CLI: delegate `cfb` subcommands unchanged.
    if argv and argv[0] in CFB_COMMANDS:
        return cfb_main(argv)

    # Legacy flat flags (deprecated). parse_arguments reads sys.argv.
    args = parse_arguments()
    from cli.app import (
        _ensure_imports,
        check_configuration,
        list_games,
        list_teams,
        setup_logging,
        validate_team_name,
    )
    setup_logging(args.debug, args.quiet)

    # Utility flags keep their existing behavior (none touch the A2 engine).
    if args.list_teams:
        _deprecation("--list-teams", "cfb slate  /  cfb hypothetical")
        _ensure_imports()
        list_teams()
        return 0
    if args.list_games is not None:
        _deprecation("--list-games", "cfb slate [N]")
        _ensure_imports()
        list_games(args.list_games)
        return 0
    if args.validate_team:
        _deprecation("--validate-team", 'cfb predict game "A @ H" (suggests close matches)')
        _ensure_imports()
        validate_team_name(args.validate_team)
        return 0
    if args.check_config:
        _deprecation("--check-config", "cfb status")
        _ensure_imports()
        return 0 if check_configuration() else 1

    # Single-game prediction → the ratified paths (never the A2 run_single_prediction).
    if args.home and args.away:
        _deprecation('--home/--away', 'cfb predict game "AWAY @ HOME" (slate) | cfb hypothetical "A vs B" (any matchup)')
        week = ["--week", str(args.week)] if args.week else []
        return cfb_main(["predict", "game", f"{args.away} @ {args.home}", *week])

    # Batch analysis → the slate command.
    if args.analyze_week is not None or args.analyze_week_p4 is not None:
        wk = args.analyze_week or args.analyze_week_p4
        _deprecation("--analyze-week[-p4]", "cfb predict week [N]")
        return cfb_main(["predict", "week", *([str(wk)] if wk else [])])

    _deprecation("this invocation", "cfb --help")
    return 1


if __name__ == '__main__':
    sys.exit(main())
