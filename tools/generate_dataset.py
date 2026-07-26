"""
Local fault-injection harness for generating labeled CI-failure training data.

For each fault in the catalog, this script:
  1. verifies the app repo is git-clean (safety),
  2. applies the fault to the app's source,
  3. runs pytest and captures the output,
  4. writes a <NNN>.json + <NNN>.log pair into the dataset repo,
  5. reverts the app repo to pristine via `git checkout .`.

Local runs have no commit, so commit_sha is null and source is "local_injection".
See faults_catalog.py for the list of faults.
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from faults_catalog import FAULTS

# --- Configuration (edit these paths to match your machine) ------------------
APP_REPO = Path("/Users/roshanpandey/Python Projects/expense-tracker-api")
DATASET_REPO = Path("/Users/roshanpandey/Python Projects/ci-triage-dataset")

# Path to the APP repo's venv Python. Using this (rather than a bare "pytest")
# guarantees we run the app's environment where pytest + its deps are installed,
# regardless of which Python launched this script.
APP_PYTHON = APP_REPO / "venv" / "bin" / "python"   # Windows: venv/Scripts/python.exe
# -----------------------------------------------------------------------------

DATASET_DIR = DATASET_REPO / "dataset"


def run_pytest() -> Tuple[bool, str]:
    """Run the app's test suite (via the app venv), return (passed, output)."""
    result = subprocess.run(
        [str(APP_PYTHON), "-m", "pytest", "-v"],
        cwd=APP_REPO,               # run inside the app repo
        capture_output=True,
        text=True,
    )
    passed = result.returncode == 0
    output = result.stdout + result.stderr
    return passed, output


def app_repo_is_clean() -> bool:
    """True if the app repo has no uncommitted changes (safe to inject)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=APP_REPO,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def revert_app_repo() -> None:
    """Discard all uncommitted changes in the app repo (undo the fault)."""
    subprocess.run(["git", "checkout", "."], cwd=APP_REPO, check=True)
    # also remove any untracked files a fault may have created
    subprocess.run(["git", "clean", "-fd"], cwd=APP_REPO, check=True)


def next_index(category: str) -> int:
    """Find the next NNN for a category by scanning existing *.json files."""
    category_dir = DATASET_DIR / category
    existing = sorted(category_dir.glob("*.json"))
    highest = 0
    for path in existing:
        stem = path.stem  # e.g. "001"
        if stem.isdigit():
            highest = max(highest, int(stem))
    return highest + 1


def apply_fault(fault: dict) -> None:
    """Apply a fault to the app source. Supports 'replace' and 'append' modes."""
    target = APP_REPO / fault["file"]
    content = target.read_text()

    if fault["mode"] == "replace":
        if fault["find"] not in content:
            raise ValueError(
                f"Fault '{fault['description']}': text to replace not found in {fault['file']}"
            )
        content = content.replace(fault["find"], fault["replace"])
    elif fault["mode"] == "append":
        content = content + "\n" + fault["append"] + "\n"
    else:
        raise ValueError(f"Unknown fault mode: {fault['mode']}")

    target.write_text(content)


def extract_failing_tests(output: str) -> list[str]:
    """Pull failing test names from pytest output (lines starting with FAILED)."""
    failing = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            # format: "FAILED tests/test_api.py::test_name - AssertionError..."
            name = line.split(" ", 1)[1].split(" - ")[0]
            failing.append(name)
    return failing


def write_example(category: str, index: int, fault: dict, output: str) -> None:
    """Write the <NNN>.json + <NNN>.log pair for one captured failure."""
    category_dir = DATASET_DIR / category
    nnn = f"{index:03d}"

    log_path = category_dir / f"{nnn}.log"
    log_path.write_text(output)

    metadata = {
        "id": f"{category}_{nnn}",
        "label": category,
        "log_file": f"{nnn}.log",
        "injected_fault": fault["description"],
        "commit_sha": None,
        "source": "local_injection",
        "ci_provider": None,
        "trigger": "local_pytest",
        "failing_tests": extract_failing_tests(output),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    json_path = category_dir / f"{nnn}.json"
    json_path.write_text(json.dumps(metadata, indent=2))
    print(f"  wrote {category}/{nnn}.json + {nnn}.log "
          f"({len(metadata['failing_tests'])} failing test(s))")


def main(only_category: Optional[str] = None) -> None:
    if not app_repo_is_clean():
        print("ERROR: app repo has uncommitted changes. Commit or stash them first,")
        print("       so the fault-revert (git checkout .) won't destroy your work.")
        return

    # Optionally filter the catalog to a single category (e.g. re-running only
    # flaky faults that skipped, without regenerating deterministic duplicates).
    faults = FAULTS
    if only_category is not None:
        faults = [f for f in FAULTS if f["label"] == only_category]
        if not faults:
            print(f"No faults found for category '{only_category}'.")
            print(f"Valid categories: {sorted({f['label'] for f in FAULTS})}")
            return
        print(f"Filtering to category: {only_category}")

    print(f"Generating examples from {len(faults)} fault(s)...\n")
    generated = 0
    skipped = 0

    for fault in faults:
        category = fault["label"]
        print(f"[{category}] {fault['description']}")
        try:
            apply_fault(fault)
            passed, output = run_pytest()
            if passed:
                print("  SKIPPED: fault did not cause a failure (tests passed).")
                skipped += 1
            else:
                index = next_index(category)
                write_example(category, index, fault, output)
                generated += 1
        finally:
            revert_app_repo()  # always revert, even if something errored

    print(f"\nDone. Generated {generated} example(s), skipped {skipped}.")
    print("Review the new files, then commit them in the dataset repo.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate labeled CI-failure examples by injecting faults."
    )
    parser.add_argument(
        "--only",
        dest="only_category",
        default=None,
        help="Run only faults of this category "
             "(genuine_regression | transient | flaky_test). "
             "Useful for re-running flaky faults without duplicating deterministic ones.",
    )
    args = parser.parse_args()
    main(only_category=args.only_category)