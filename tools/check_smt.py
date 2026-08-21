"""Optional Z3 checks. Install with: python -m pip install -e .[dev]"""

from __future__ import annotations

try:
    from z3 import Int, Solver, sat, unsat
except ImportError as exc:
    raise SystemExit("z3-solver is not installed; install the 'dev' extra") from exc


def main() -> None:
    actions = [Int(f"a{i}") for i in range(12)]
    unit = Solver()
    for action in actions:
        unit.add(action == 900, action <= 10000)
    unit.add(sum(actions) > 10000)
    if unit.check() != sat:
        raise SystemExit("expected a SAT counterexample for the unit-call filter")

    residuals = [Int(f"r{i}") for i in range(13)]
    trajectory = Solver()
    trajectory.add(residuals[0] == 10000)
    for index in range(12):
        trajectory.add(residuals[index + 1] == residuals[index] - 900)
        trajectory.add(residuals[index + 1] >= 0)
    if trajectory.check() != unsat:
        raise SystemExit("expected UNSAT for twelve authorized residual transitions")
    print("SMT checks: unit-filter=SAT counterexample, residual-trajectory=UNSAT")


if __name__ == "__main__":
    main()

