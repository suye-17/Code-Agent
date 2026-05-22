import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def load_env():
    from dotenv import load_dotenv
    load_dotenv()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")


def test_agent_fixes_calc_bug(tmp_path):
    """End-to-end: copy buggy_calc to tmp, agent fixes it, pytest passes."""
    from agent.orchestrator.react import ReActAgent

    src = Path(__file__).parent.parent / "toy_cases" / "buggy_calc"
    work = tmp_path / "buggy_calc"
    shutil.copytree(src, work)

    agent = ReActAgent(workdir=work, max_steps=20)
    agent.run(
        task="There are failing tests in this directory. "
             "Read calc.py and test_calc.py, find the bug, fix it, "
             "then run pytest to verify all tests pass."
    )

    r = subprocess.run(
        ["python", "-m", "pytest", "-x", "--tb=short"],
        cwd=work, capture_output=True, text=True,
    )
    assert r.returncode == 0, (
        f"pytest failed:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
    )


def test_max_steps_terminates_cleanly(tmp_path):
    """Agent must not infinite-loop; should return within step budget."""
    from agent.orchestrator.react import ReActAgent

    (tmp_path / "x.txt").write_text("trivial")
    agent = ReActAgent(workdir=tmp_path, max_steps=1)
    result = agent.run(
        task="Read every file in /etc and summarize them. "
             "Then read every file in /var. Then /usr."
    )
    assert isinstance(result, str)
