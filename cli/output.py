"""Shared CLI output + exit-code helpers for the ``cfb`` CLI (Phase 4.5, SPEC §9.5).

Every subcommand supports ``--format table|json|csv`` (default table) and returns a meaningful exit
code — ``0`` ok, ``1`` error, ``2`` degraded data — so shell scripting works. Table/CSV/JSON rendering
lives here once, reused by every subcommand (generalizing the ad-hoc formatting in the pre-4.5
``run_hypothetical``/``run_project``).
"""

from __future__ import annotations

import csv
import io
import json
import sys
from collections.abc import Sequence
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DEGRADED = 2

# A column spec is (record_key, header).
Column = tuple[str, str]


def _cell(value: Any) -> str:
    """Render a single cell — ``None`` becomes an em-dash so honest-missing reads as such."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def render_table(rows: list[dict], columns: Sequence[Column], *, title: str | None = None) -> str:
    headers = [h for _, h in columns]
    body = [[_cell(r.get(k)) for k, _ in columns] for r in rows]
    widths = [max(len(headers[i]), *(len(row[i]) for row in body)) if body else len(headers[i])
              for i in range(len(columns))]
    def fmt(cells: list[str]) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells))
    lines: list[str] = []
    if title:
        lines += [title, ""]
    lines.append(fmt(headers))
    lines.append("  ".join("-" * w for w in widths))
    lines += [fmt(row) for row in body]
    if not body:
        lines.append("(no rows)")
    return "\n".join(lines)


def render_csv(rows: list[dict], columns: Sequence[Column]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([h for _, h in columns])
    for r in rows:
        writer.writerow(["" if r.get(k) is None else r.get(k) for k, _ in columns])
    return buf.getvalue().rstrip("\n")


def emit(fmt: str, *, rows: list[dict] | None = None, columns: Sequence[Column] | None = None,
         json_obj: Any = None, title: str | None = None) -> None:
    """Print in the requested format. ``json`` emits ``json_obj`` if provided (the full structured
    payload), else the ``rows``; ``table``/``csv`` render ``rows`` over ``columns``."""
    if fmt == "json":
        print(json.dumps(json_obj if json_obj is not None else rows, indent=2, sort_keys=True,
                         default=str))
    elif fmt == "csv":
        print(render_csv(rows or [], columns or []))
    else:
        print(render_table(rows or [], columns or [], title=title))


def error(message: str, *, code: int = EXIT_ERROR) -> int:
    """Print an error to stderr and return the exit code (so callers ``return error(...)``)."""
    print(message, file=sys.stderr)
    return code
