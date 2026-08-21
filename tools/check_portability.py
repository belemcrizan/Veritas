"""Fail when cloud SDKs leak from adapters into domain modules."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "veritas"
FORBIDDEN = ("boto3", "botocore", "azure", "google.cloud")


def imported_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    return node.names[0].name if node.names else ""


def main() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        relative = path.relative_to(SOURCE_ROOT)
        if relative.parts and relative.parts[0] == "adapters":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                name = imported_name(node)
                if any(name == item or name.startswith(item + ".") for item in FORBIDDEN):
                    violations.append(f"{relative}:{node.lineno}: {name}")
    if violations:
        raise SystemExit("Cloud SDK import outside adapters:\n" + "\n".join(violations))
    print("portability check: PASS")


if __name__ == "__main__":
    main()

