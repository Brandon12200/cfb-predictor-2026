#!/usr/bin/env python3
"""Resolve every locator in a document on three axes: exists, says what you think, reachable.

D43 (b), superseding D42 (a)3: there was never a tool, so this is it, built from the owner's
three-axis specification. The need is recorded in `docs/HANDOFF_SEASON.md` §7 and §9. Every pointer
error found in the season handoff sat inside a sentence that read perfectly well. Careful reading
caught none of them; resolving the token in isolation caught them in about a minute.

For each locator the tool reports:

1. **exists**: the file is there, the line is inside it, the `::symbol` is defined in it, the SHA
   is a commit. A basename (`ci.yml:52`) must resolve to exactly one tracked file.
2. **says**: what is actually at that location, printed for a human to compare with the sentence.
   This axis cannot be decided mechanically. As a hint, it notes whether any other backticked
   token from the same document line appears in the cited lines. A mismatch is `CHECK` and does not
   fail the run.
3. **reachable**: the commit (a SHA, or the frame a locator is pinned to with "at `sha`" or
   "as at `sha`") is an ancestor of `--ref`, which defaults to `origin/main`. A commit that exists
   locally but is on no path to `main` is not evidence a successor can follow.

Locators recognised: `path:N`, `path:N-M`, `path::symbol`, a backticked `path/with.ext`, a backticked
basename, a bare `:N`, and a backticked 7–40-character hex SHA. A bare `:N` inherits the file of
the previous line locator in its paragraph; a table row and a list item are each their own paragraph.
An all-digit token is checked only if it resolves to a commit; otherwise it is an Actions run ID and
is skipped. A locator in a sentence that names a frame is read from that commit. Any other locator is
read from the working tree, so a branch is checked as it stands.

**Half a tool, by design (D42 (a)3, `HANDOFF_SEASON.md` §9).** It cannot re-derive a claim with no
pointer: a count, a date, a status, a figure. Run it, then separately re-derive those (D42 (d)).

**Known limits, accepted by owner ruling 2026-09-14 (after #64):**

- **`::symbol` can pass on docstring prose.** Indented assignments count as definitions, so a class
  attribute can be cited, but the same pattern also matches a docstring line such as
  `bar: the input value`. `file::bar` then reports `ok` when `bar` is only a documented parameter.
  The printed `says:` line shows what matched; read it. The proper fix, skipping triple-quoted
  strings, is `docs/2027_NOTES.md` §8 item 32.
- **Sentence splitting is naive.** A frame governs only its own sentence, and sentences are split at
  `.`, `;`, `!` or `?` followed by whitespace. "e.g. ", "i.e. ", "etc. ", "vs. " or a semicolon inside
  an aside can therefore end a frame's sentence early, and a locator after it is read from the working
  tree instead of the frame. No abbreviation list, by ruling. When a frame matters, keep it in the
  same plain sentence as its locator, or pass `--frame`.

Exit 0: every locator passes `exists` and `reachable` (`CHECK` hints do not fail).
Exit 1: at least one locator is `MISSING`, out of range, ambiguous, unknown or unreachable.
Exit 2: usage error.

Usage: python scripts/resolve_locators.py DOC [DOC ...] [--ref origin/main] [--all]
       make resolve-locators DOC=docs/HANDOFF_SEASON.md
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_root = ROOT                       # the repository resolved against; `--root` moves it (tests only)
EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

_PATH = r"(?:[\w.-]+/)*[\w-][\w.-]*\.[A-Za-z][A-Za-z0-9]{0,4}"
# `path:N`, `path:N-M` or `path::symbol`, backticked or not.
_LINE_LOC = re.compile(rf"(?<![\w/.$<{{-])({_PATH})(?::(\d+)(?:-(\d+))?\b|::(\w+))")
_BARE_LINE = re.compile(r"`:(\d+)(?:-(\d+))?`")
_BACKTICK = re.compile(r"`([^`\n]+)`")
_SHA = re.compile(r"[0-9a-f]{7,40}")
_FRAME = re.compile(r"\b(?:as at|at)\s+`([0-9a-f]{7,40})`")
# Template paths are descriptions, not claims: `2026_week_NN.json`, `docs/proposals/<ITEM>.md`.
_TEMPLATE = re.compile(r"NN|XX|YYYY|MM|<|>|\{|\}|\*|\$")
# A path with no directory must carry a file extension, or `cli.cfb`, `matrix.phase` and
# `permissions.deny` (module and key names) would be looked up as files.
_FILE_EXT = {"py", "md", "json", "yml", "yaml", "toml", "txt", "sh", "cfg", "ini", "csv", "lock", "html", "js"}


@dataclass
class Locator:
    doc: str
    doc_line: int
    text: str                      # the locator as written
    kind: str                      # "line" | "symbol" | "path" | "sha"
    path: str | None = None
    start: int | None = None
    end: int | None = None
    symbol: str | None = None
    sha: str | None = None
    frame: str | None = None       # commit the locator is pinned to; None = working tree
    exists: str = "ok"
    reachable: str = "n/a"
    says: list[str] = field(default_factory=list)
    hint: str = ""

    @property
    def failed(self) -> bool:
        return self.exists != "ok" or self.reachable not in ("ok", "n/a")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(_root), *args], capture_output=True, text=True)


def _is_commit(sha: str) -> bool:
    return _git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def default_ref() -> str:
    for ref in ("origin/main", "main", "HEAD"):
        if _git("rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    return "HEAD"


def _tracked(frame: str | None) -> list[str]:
    out = _git("ls-tree", "-r", "--name-only", frame) if frame else _git("ls-files")
    return out.stdout.splitlines()


def _read(path: str, frame: str | None) -> str | None:
    if frame:
        got = _git("show", f"{frame}:{path}")
        return got.stdout if got.returncode == 0 else None
    p = _root / path
    return p.read_text(errors="replace") if p.is_file() else None


def _resolve_path(path: str, frame: str | None, tracked_cache: dict[str | None, list[str]]) -> tuple[str | None, str]:
    """(resolved repo path, status). A basename or partial path must match exactly one tracked file."""
    if _read(path, frame) is not None:
        return path, "ok"
    files = tracked_cache.setdefault(frame, _tracked(frame))
    hits = [f for f in files if f == path or f.endswith("/" + path)]
    if len(hits) == 1:
        return hits[0], "ok"
    return None, ("AMBIGUOUS: " + ", ".join(hits[:4])) if hits else "MISSING"


_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
_SENTENCE_END = re.compile(r"[.;!?](?=\s)")


def _sentence_frames(line: str, default_frame: str | None) -> list[tuple[int, list[str | None]]]:
    """[(segment end offset, frames named in that segment)] for one line.

    A frame pin ("at `sha`") governs only its own sentence. Applied to the whole line, "As at `a`, X
    was `f.py:4`. On the branch, `f.py:4` reads differently." pinned the second locator to `a` too,
    and it reported `ok` with stale content.
    """
    ends = [m.end() for m in _SENTENCE_END.finditer(line)] + [len(line)]
    out, start = [], 0
    for end in ends:
        named: list[str | None] = [m.group(1) for m in _FRAME.finditer(line) if start <= m.start() < end]
        out.append((end, named or [default_frame]))
        start = end
    return out


def _frames_at(segments: list[tuple[int, list[str | None]]], pos: int) -> list[str | None]:
    return next(frames for end, frames in segments if pos < end or end == segments[-1][0])


def _is_sha_token(tok: str) -> bool:
    """Hex-shaped, and not an Actions run ID. About 1 in 27 real short SHAs is all digits, so digits alone
    cannot mean "run ID": skipping them silently dropped those commits from every check."""
    return bool(_SHA.fullmatch(tok)) and (not tok.isdigit() or _is_commit(tok))


def _is_file_like(path: str) -> bool:
    return "/" in path or path.rsplit(".", 1)[-1] in _FILE_EXT


def extract(doc: Path, text: str, default_frame: str | None = None) -> list[Locator]:
    found: list[Locator] = []
    last_line_loc: Locator | None = None
    prev_row = False
    for n, line in enumerate(text.splitlines(), 1):
        # A bare `:N` inherits only within its own paragraph. A table row and a list item are each
        # their own paragraph: inheriting across rows pinned C3's `:111` to C1's file.
        is_row = line.lstrip().startswith("|")
        if not line.strip() or is_row or prev_row or _LIST_ITEM.match(line):
            last_line_loc = None
        prev_row = is_row
        # A sentence may pin a locator to more than one frame ("at `a`, same line at `b`"): check each.
        segments = _sentence_frames(line, default_frame)
        spans: list[tuple[int, int]] = []

        for m in _LINE_LOC.finditer(line):
            path = m.group(1)
            if ("://" in line[max(0, m.start() - 12):m.start()] or _TEMPLATE.search(path)
                    or not _is_file_like(path)):
                continue
            spans.append(m.span())
            frames = _frames_at(segments, m.start())
            for fr in frames:
                if m.group(4):
                    loc = Locator(str(doc), n, m.group(0), "symbol", path=path, symbol=m.group(4), frame=fr)
                else:
                    start = int(m.group(2))
                    loc = Locator(str(doc), n, m.group(0), "line", path=path, start=start,
                                  end=int(m.group(3)) if m.group(3) else start, frame=fr)
                    if fr == frames[0]:
                        last_line_loc = loc
                found.append(loc)

        for m in _BARE_LINE.finditer(line):
            start = int(m.group(1))
            if last_line_loc is None:
                found.append(Locator(str(doc), n, m.group(0).strip("`"), "line", start=start,
                                     hint="CHECK: bare line number with no file on its line or in its paragraph"))
                continue
            found.append(Locator(str(doc), n, m.group(0).strip("`"), "line", path=last_line_loc.path,
                                 start=start, end=int(m.group(2)) if m.group(2) else start,
                                 frame=_frames_at(segments, m.start())[0]))

        for m in _BACKTICK.finditer(line):
            tok = m.group(1).strip()
            inside = any(a <= m.start(1) < b or m.start(1) <= a < m.end(1) for a, b in spans)
            if _is_sha_token(tok):
                found.append(Locator(str(doc), n, tok, "sha", sha=tok))
            elif (not inside and re.fullmatch(_PATH, tok) and not _TEMPLATE.search(tok)
                  and _is_file_like(tok) and ("/" in tok or tok.count(".") == 1)):
                found.append(Locator(str(doc), n, tok, "path", path=tok, frame=_frames_at(segments, m.start())[0]))
    return found


def _hint(loc: Locator, doc_line: str, lines: list[str]) -> str:
    """Advisory only: does any other backticked token on the document line appear in the cited lines?"""
    tokens = [t.strip() for t in _BACKTICK.findall(doc_line)]
    tokens = [t for t in tokens if len(t) >= 3 and loc.text not in t and not _LINE_LOC.search(t)
              and not _SHA.fullmatch(t) and not _BARE_LINE.fullmatch(f"`{t}`")]
    if not tokens:
        return ""
    body = "\n".join(lines)
    hits = [t for t in tokens if t in body or re.split(r"::|\.", t.rstrip("()"))[-1] in body]
    return f"match: {', '.join(f'`{t}`' for t in hits[:3])}" if hits else \
        f"CHECK: none of {', '.join(f'`{t}`' for t in tokens[:3])} is on the cited line(s)"


def resolve(loc: Locator, ref: str, doc_lines: list[str], cache: dict[str | None, list[str]]) -> None:
    commit = loc.sha if loc.kind == "sha" else loc.frame
    if commit is not None:
        if not _is_commit(commit):
            if loc.kind == "sha":
                loc.exists, loc.reachable = "UNKNOWN COMMIT (not in this clone's object store)", "n/a"
                return
            loc.exists = f"UNKNOWN FRAME {commit}"
            return
        loc.reachable = "ok" if _git("merge-base", "--is-ancestor", commit, ref).returncode == 0 \
            else f"UNREACHABLE (not an ancestor of {ref})"
    if loc.kind == "sha":
        loc.says = [_git("log", "-1", "--format=%h %ad %s", "--date=short", commit or "").stdout.strip()]
        return

    if loc.path is None:                      # an unanchored bare `:N` — reported as CHECK, not resolved
        return
    if loc.path.startswith("/") or ".." in loc.path.split("/"):
        loc.exists = "OUTSIDE THE REPOSITORY"
        return
    path, status = _resolve_path(loc.path, loc.frame, cache)
    if path is None:
        loc.exists = status
        return
    content = _read(path, loc.frame) or ""
    lines = content.splitlines()
    shown = path if path == loc.path else f"{loc.path} -> {path}"

    if loc.kind == "line":
        assert loc.start is not None and loc.end is not None
        if loc.start < 1 or loc.end > len(lines) or loc.end < loc.start:
            loc.exists = f"NO SUCH LINE ({shown} has {len(lines)} lines)"
            return
        cited = lines[loc.start - 1:loc.end]
        loc.says = [f"{shown}:{loc.start + i}: {ln.strip()}" for i, ln in enumerate(cited[:6])]
        if len(cited) > 6:
            loc.says.append(f"… {len(cited) - 6} more line(s)")
        loc.hint = _hint(loc, doc_lines[loc.doc_line - 1], cited)
    elif loc.kind == "symbol":
        sym = re.escape(loc.symbol or "")
        # Indented assignments count: a class attribute is as citable as a module constant.
        pat = re.compile(rf"^\s*(?:async\s+def|def|class)\s+{sym}\b|^\s*{sym}\s*(?::|=(?!=))")
        where = [i for i, ln in enumerate(lines, 1) if pat.search(ln)]
        if not where:
            loc.exists = f"NO SUCH SYMBOL in {shown}"
            return
        loc.says = [f"{shown}:{i}: {lines[i - 1].strip()}" for i in where[:2]]
    else:
        loc.says = [f"{shown} ({len(lines)} lines)"] if shown != loc.path else []


def render(locs: list[Locator], ref: str, show_all: bool) -> str:
    out = []
    for loc in locs:
        if not show_all and not loc.failed and not loc.hint.startswith("CHECK") and loc.kind == "path":
            continue
        frame = f" @{loc.frame}" if loc.frame else ""
        mark = "FAIL" if loc.failed else ("CHECK" if loc.hint.startswith("CHECK") else "ok")
        out.append(f"[{mark:5}] {loc.doc}:{loc.doc_line}  {loc.text}{frame}")
        if loc.exists != "ok":
            out.append(f"        exists:    {loc.exists}")
        if loc.reachable not in ("ok", "n/a"):
            out.append(f"        reachable: {loc.reachable}")
        for s in loc.says:
            out.append(f"        says:      {s}")
        if loc.hint:
            out.append(f"        hint:      {loc.hint}")
    failed = sum(loc.failed for loc in locs)
    checks = sum(loc.hint.startswith("CHECK") for loc in locs)
    out.append(f"\nresolve_locators: {len(locs)} locator(s) against {ref}: {failed} failed, "
               f"{checks} to check by eye. Claims with no locator are not covered (D42 (d)).")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("docs", nargs="*", type=Path)
    ap.add_argument("--ref", default=None, help="commits must be ancestors of this (default origin/main)")
    ap.add_argument("--all", action="store_true", help="also list plain path references that resolved")
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root (tests only)")
    ap.add_argument("--frame", default=None,
                    help="read locators with no frame on their line from this commit, not the working tree")
    args = ap.parse_args(argv)
    global _root
    _root = args.root
    if not args.docs:
        print("usage: resolve_locators.py DOC [DOC ...]  (make resolve-locators DOC=...)", file=sys.stderr)
        return EXIT_USAGE
    ref = args.ref or default_ref()
    if args.frame and not _is_commit(args.frame):
        print(f"resolve_locators: --frame {args.frame} is not a commit", file=sys.stderr)
        return EXIT_USAGE
    locs: list[Locator] = []
    cache: dict[str | None, list[str]] = {}
    for doc in args.docs:
        p = doc if doc.is_absolute() else Path.cwd() / doc
        if not p.is_file():
            print(f"resolve_locators: no such document {doc}", file=sys.stderr)
            return EXIT_USAGE
        text = p.read_text()
        doc_lines = text.splitlines()
        for loc in extract(doc, text, args.frame):
            resolve(loc, ref, doc_lines, cache)
            locs.append(loc)
    print(render(locs, ref, args.all))
    return EXIT_FAIL if any(loc.failed for loc in locs) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
