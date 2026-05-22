import pytest

from agent.tools.base import Tool  # noqa: F401
from agent.tools.exec import RunShell
from agent.tools.fs import Grep, ListDir, ReadFile, WriteFile


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


def test_all_tools_have_unique_names():
    tools = [ReadFile(), WriteFile(), ListDir(), Grep(), RunShell()]
    names = [t.name for t in tools]
    assert len(names) == len(set(names))
    assert set(names) == {"read_file", "write_file", "list_dir", "grep", "run_shell"}
