"""Canonical entry points. The pipeline calls these directly; `cfb` wraps the same cores.

This file exists so `scripts` is a regular package that `setuptools.find_packages` discovers —
without it, `[tool.setuptools.packages.find] include = ["scripts*"]` matches nothing and `cfb grade`
/ `report` / `status` / `data *` all raise `ModuleNotFoundError` on a non-editable install.
"""
