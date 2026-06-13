import sys

import pytest

from agent.tools.base import Tool  # noqa: F401
from agent.tools.exec import RunShell
from agent.tools.fs import Grep, ListDir, ReadFile, WriteFile
from agent.tools.test import RunTest


def test_tool_schema_shape():
    t = ReadFile()
    s = t.schema()
    assert s["type"] == "function"
    assert s["function"]["name"] == "read_file"
    assert "parameters" in s["function"]
    assert s["function"]["parameters"]["type"] == "object"


def test_read_write_roundtrip(tmp_path):
    p = tmp_path / "a.txt"
    msg = WriteFile().run(path=str(p), content="hello world")
    assert "hello world".encode() == p.read_bytes()
    assert ReadFile().run(path=str(p)) == "hello world"
    assert "11" in msg or "wrote" in msg.lower()


def test_write_creates_parent_dirs(tmp_path):
    p = tmp_path / "deep" / "nested" / "f.txt"
    WriteFile().run(path=str(p), content="x")
    assert p.read_text() == "x"


def test_read_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ReadFile().run(path=str(tmp_path / "nope.txt"))


def test_list_dir(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.txt").write_text("")
    (tmp_path / "sub").mkdir()
    out = ListDir().run(path=str(tmp_path))
    assert "a.py" in out
    assert "b.txt" in out
    assert "sub" in out


def test_grep_finds_pattern(tmp_path):
    (tmp_path / "x.py").write_text("def foo():\n    pass\n")
    (tmp_path / "y.py").write_text("def bar():\n    pass\n")
    out = Grep().run(pattern=r"def foo", path=str(tmp_path))
    assert "x.py" in out
    assert "y.py" not in out


def test_grep_no_match(tmp_path):
    (tmp_path / "x.py").write_text("hello\n")
    out = Grep().run(pattern="zzznotfound", path=str(tmp_path))
    assert "zzznotfound" not in out


def test_run_shell_success():
    r = RunShell().run(cmd="echo hi", timeout=5)
    assert r["returncode"] == 0
    assert r["stdout"].strip() == "hi"


def test_run_shell_failure_code():
    r = RunShell().run(cmd="exit 7", timeout=5)
    assert r["returncode"] == 7


def test_run_shell_timeout():
    r = RunShell().run(cmd="sleep 5", timeout=1)
    assert r["returncode"] == -1
    assert "TIMEOUT" in r["stderr"].upper()


def test_run_shell_uses_cwd(tmp_path):
    (tmp_path / "marker.txt").write_text("from cwd")

    r = RunShell().run(
        cmd=(
            f"{sys.executable} -c \"from pathlib import Path; "
            "print(Path('marker.txt').read_text())\""
        ),
        timeout=5,
        cwd=str(tmp_path),
    )

    assert r["returncode"] == 0
    assert r["stdout"].strip() == "from cwd"


def test_run_shell_schema_exposes_cwd():
    schema = RunShell().schema()["function"]["parameters"]

    assert "cwd" in schema["properties"]
    assert schema["properties"]["cwd"]["type"] == "string"


def test_run_test_passes_pytest_suite(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n")

    r = RunTest().run(path=str(tmp_path), timeout=5)

    assert r["passed"] is True
    assert r["returncode"] == 0
    assert r["timed_out"] is False
    assert "passed" in r["stdout_tail"]
    assert r["stderr_tail"] == ""
    assert r["elapsed_s"] >= 0


def test_run_test_reports_pytest_failure(tmp_path):
    (tmp_path / "test_fail.py").write_text("def test_fail():\n    assert False\n")

    r = RunTest().run(path=str(tmp_path), timeout=5, max_output_chars=200)

    assert r["passed"] is False
    assert r["returncode"] != 0
    assert r["timed_out"] is False
    assert "FAILED" in r["stdout_tail"] or "failed" in r["stdout_tail"]
    assert len(r["stdout_tail"]) <= 200


def test_run_test_reports_timeout(tmp_path):
    (tmp_path / "test_slow.py").write_text(
        "import time\n\ndef test_slow():\n    time.sleep(2)\n"
    )

    r = RunTest().run(path=str(tmp_path), timeout=1)

    assert r["passed"] is False
    assert r["returncode"] == -1
    assert r["timed_out"] is True
    assert "TIMEOUT" in r["stderr_tail"]


def test_all_tools_have_unique_names():
    tools = [ReadFile(), WriteFile(), ListDir(), Grep(), RunShell(), RunTest()]
    names = [t.name for t in tools]
    assert len(names) == len(set(names))
    assert set(names) == {
        "read_file",
        "write_file",
        "list_dir",
        "grep",
        "run_shell",
        "run_test",
    }
