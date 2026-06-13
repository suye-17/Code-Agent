from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASES_FILE = ROOT / "eval" / "regression_set" / "seed_cases.jsonl"
TOY_CASES = ROOT / "tests" / "toy_cases"


def load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES_FILE.read_text().splitlines() if line.strip()]


def test_regression_set_has_minimum_case_count_and_unique_ids():
    cases = load_cases()
    ids = [case["id"] for case in cases]

    assert len(cases) >= 15
    assert len(ids) == len(set(ids))


def test_regression_set_repositories_exist_and_have_tests():
    for case in load_cases():
        repo = TOY_CASES / case["repo"]
        assert repo.is_dir(), f"missing repo for case {case['id']}: {repo}"
        assert list(repo.glob("test_*.py")), f"case {case['id']} has no pytest files"
        assert case["task"].strip(), f"case {case['id']} has empty task"


def test_regression_set_cases_start_with_failing_tests():
    for case in load_cases():
        repo = TOY_CASES / case["repo"]
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0, f"case {case['id']} should start failing"
