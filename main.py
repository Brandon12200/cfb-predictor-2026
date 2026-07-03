#!/usr/bin/env python3
"""Thin CLI entry point. Implementation lives in the `cli` package (SPEC §4.7)."""

import sys

from cli.app import main
from cli.args import parse_arguments  # re-exported for backward compatibility

__all__ = ["main", "parse_arguments"]

if __name__ == '__main__':
    sys.exit(main())
