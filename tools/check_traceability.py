"""Fail when SECURITY_CLAIMS.md points at missing implementation or test paths."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLAIMS = PROJECT_ROOT / "docs" / "SECURITY_CLAIMS.md"


def main() -> None:
    text = CLAIMS.read_text(encoding="utf-8")
    missing: list[str] = []
    current = "UNKNOWN"
    for line in text.splitlines():
        if line.startswith("## CLAIM-"):
            current = line.replace("## ", "").strip()
        stripped = line.strip().lower()
        if not (
            stripped.startswith("- **implementation:**") or stripped.startswith("- **tests:**")
        ):
            continue
        for token in re.findall(r"`([^`]+)`", line):
            candidate = token.split()[0].strip(",")
            if ".py" not in candidate:
                continue
            if "/" not in candidate and "\\" not in candidate:
                continue
            path = PROJECT_ROOT / candidate.replace("\\", "/")
            if not path.exists():
                missing.append(f"{current}: missing {candidate}")
    if missing:
        raise SystemExit("Traceability check failed:\n" + "\n".join(missing))
    print("traceability check: PASS")


if __name__ == "__main__":
    main()
