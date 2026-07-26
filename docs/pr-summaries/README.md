# PR summaries

Durable per-PR records: what shipped, the measured evidence behind it, the reviewer verdict, and the
decisions it settled. **Retained, not retired** — unlike `docs/proposals/`, nothing here expires.

Why they exist: table-dense reports do not survive paste transit, so the report is written as a file
and the terminal reply points at it. Why they are separate from `docs/proposals/`: proposals are
working documents that are deleted once ratified, and PR summaries were twice deleted a cycle later
under that rule when they should have been kept. A summary is a record; a proposal is scaffolding.

The authoritative records are always `docs/CALIBRATION_LOG.md`, `docs/DECISIONS.md`, and
`docs/SPEC.md`. These files carry the review context around a change, never the ruling itself.
