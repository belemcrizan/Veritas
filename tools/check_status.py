"""Fail when package version, research_status.json, and pyproject drift."""

from __future__ import annotations

import re
from pathlib import Path

from veritas.research import PACKAGED_VERSION, packaged_status

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    if match is None:
        raise SystemExit("pyproject.toml has no version")
    packaged = packaged_status()
    errors: list[str] = []
    if match.group(1) != PACKAGED_VERSION:
        errors.append(f"pyproject {match.group(1)} != PACKAGED_VERSION {PACKAGED_VERSION}")
    if packaged["version"] != PACKAGED_VERSION:
        errors.append("research_status.json version drift")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    if PACKAGED_VERSION not in readme:
        errors.append("README does not mention packaged version")
    if errors:
        raise SystemExit("status check failed:\n" + "\n".join(errors))
    print("status check: PASS")


if __name__ == "__main__":
    main()
