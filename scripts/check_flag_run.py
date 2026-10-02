"""Hold a finished example run to the bug matrix.

    python scripts/check_flag_run.py <results-root> [--flag NAME]

Without --flag every test must pass. With --flag, every test that did not pass is
sorted into one of three groups:
  guard            the matrix's test; it must be red at the matrix's check
  caused by flag   a declared impact of this flag, with the reason it is reached
  separate defect  anything else: fails the check (a second bug, or a defect that
                   reaches further than the matrix says)
A declared impact that stayed green fails the check too (the matrix is stale).
Every test must be guarded by a flag or listed in NOT_GUARDED with a reason.

Reads the newest finished run labelled for the flag (<run id>-<flag>, or -clean)
under <results-root>, prints the verdict and writes it to matrix_check.txt in that
run's folder, next to its report.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from example.app.bugs import FLAGS  # noqa: E402
from example.suite import profile  # noqa: E402,F401  (report titles)
from example.suite.bug_matrix import GUARDS, NOT_GUARDED  # noqa: E402
from framework.reporting.recorder import FAILED  # noqa: E402
from framework.reporting.report_builder import load_run  # noqa: E402
from framework.tokens import newest_run  # noqa: E402


def first_failed_step(test: dict) -> str:
    return next((s.get("step", "") for s in test["steps"] if s.get("status") == FAILED), "")


def describe(test: dict) -> str:
    where = first_failed_step(test)
    return f"{test['func']} {test['status']}" + (f" at {where!r}" if where else "")


def check(run: dict, flag: str | None) -> tuple[list[str], list[str]]:
    """(lines explaining every test that did not pass, problems)."""
    guarded = {g.test for g in GUARDS.values()} | set(NOT_GUARDED)
    problems = [f"{t['func']} is guarded by no flag (add one to the bug matrix)"
                for t in run["tests"] if t["func"] not in guarded]
    lines = []
    ran = {t["func"]: t for t in run["tests"]}
    if flag is None:
        for test in run["tests"]:
            if test["status"] != "passed":
                problems.append(f"{describe(test)} on a clean run")
        return lines, problems

    guard = GUARDS[flag]
    test = ran.get(guard.test)
    if test is None:
        problems.append(f"guard {guard.test} did not run")
    elif test["status"] != "failed":
        problems.append(f"guard {guard.test} is {test['status']}, expected failed")
    elif guard.check not in first_failed_step(test):
        problems.append(f"guard {describe(test)}, expected the check {guard.check!r}")
    else:
        lines.append(f"guard            {describe(test)}")

    for test in run["tests"]:
        if test["func"] == guard.test or test["status"] == "passed":
            continue
        reason = guard.impact.get(test["func"])
        if reason:
            lines.append(f"caused by flag   {describe(test)} - {reason}")
        else:
            lines.append(f"SEPARATE DEFECT  {describe(test)}")
            problems.append(f"{describe(test)} is not a declared impact of {flag}")
    for func in guard.impact:
        if func in ran and ran[func]["status"] == "passed":
            problems.append(f"declared impact {func} stayed green: the matrix is stale")
    return lines, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--flag", default=None)
    args = parser.parse_args()
    if set(GUARDS) != set(FLAGS):
        print(f"bug matrix and app flags differ: {sorted(set(GUARDS) ^ set(FLAGS))}")
        return 1
    if args.flag and args.flag not in GUARDS:
        print(f"unknown flag {args.flag!r}")
        return 1
    label = args.flag or "clean"
    run_dir = newest_run(args.root, label)
    if run_dir is None:
        print(f"no finished {label} run under {args.root}")
        return 1
    lines, problems = check(load_run(run_dir), args.flag)
    verdict = (f"[{label}] NOT as the matrix requires:\n- " + "\n- ".join(problems)
               if problems else f"[{label}] as the matrix requires")
    text = "\n".join([f"[{label}] {run_dir}", *(f"  {ln}" for ln in lines), verdict]) + "\n"
    (run_dir / "matrix_check.txt").write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
