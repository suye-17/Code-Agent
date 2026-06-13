import json
from pathlib import Path

from agent.orchestrator.react import ReActAgent


class DummyLLM:
    def chat(self, messages, tools=None, model=None):  # noqa: ARG002
        return {"choices": [{"message": {"content": "done"}}]}


def test_react_default_tools_include_run_test(tmp_path):
    agent = ReActAgent(workdir=tmp_path, llm=DummyLLM())

    assert "run_test" in agent.tools
    schema_names = {tool.schema()["function"]["name"] for tool in agent.tools.values()}
    assert "run_test" in schema_names


def test_react_wraps_successful_tool_result(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    agent = ReActAgent(workdir=tmp_path, llm=DummyLLM())

    result = json.loads(agent._invoke_tool("read_file", {"path": "a.txt"}))

    assert result == {
        "ok": True,
        "tool": "read_file",
        "result": "hello",
        "error_type": None,
        "error_message": None,
        "truncated": False,
    }


def test_react_reports_unknown_tool_as_structured_error(tmp_path):
    agent = ReActAgent(workdir=tmp_path, llm=DummyLLM())

    result = json.loads(agent._invoke_tool("missing_tool", {}))

    assert result["ok"] is False
    assert result["tool"] == "missing_tool"
    assert result["error_type"] == "UNKNOWN_TOOL"
    assert "unknown tool" in result["error_message"]


def test_react_sandboxes_run_test_path(tmp_path):
    agent = ReActAgent(workdir=tmp_path, llm=DummyLLM())
    outside = Path("/tmp")

    result = json.loads(agent._invoke_tool("run_test", {"path": str(outside)}))

    assert result["ok"] is False
    assert result["tool"] == "run_test"
    assert result["error_type"] == "PATH_ESCAPE"
    assert "escapes workdir" in result["error_message"]


class MalformedArgumentsLLM:
    def __init__(self):
        self.messages_seen = []
        self.calls = 0

    def chat(self, messages, tools=None, model=None):  # noqa: ARG002
        self.messages_seen = messages
        self.calls += 1
        if self.calls == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "bad-json",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": "{",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        return {"choices": [{"message": {"role": "assistant", "content": "done"}}]}


def test_react_reports_malformed_tool_arguments_as_structured_error(tmp_path):
    llm = MalformedArgumentsLLM()
    agent = ReActAgent(workdir=tmp_path, llm=llm)

    assert agent.run("trigger malformed tool call") == "done"

    tool_messages = [m for m in llm.messages_seen if m["role"] == "tool"]
    assert len(tool_messages) == 1
    result = json.loads(tool_messages[0]["content"])
    assert result["ok"] is False
    assert result["tool"] == "read_file"
    assert result["error_type"] == "JSON_DECODE_ERROR"
