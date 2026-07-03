"""Source clients (SPEC §5.2 layer 1).

One module per external source. Each client is dumb and honest: it fetches,
parses to source-native structures, and RAISES on failure. No fallback logic,
no neutral/placeholder values, and no cross-source knowledge live here — that
belongs to the snapshot builder (`data/snapshot/`).
"""
