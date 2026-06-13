from __future__ import annotations

import json

from agent.orchestrator.react import ReActAgent


class ScriptedLLM:
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.calls = 0
        self.messages_seen: list[list[dict]] = []
        self.tools_seen: list[list[dict] | None] = []

    def chat(self, messages, tools=None, model=None):  # noqa: ARG002
        self.messages_seen.append(messages.copy())
        self.tools_seen.append(tools)
        response = self.responses[self.calls]
        self.calls += 1
        return response


def tool_response(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ]
    }


def final_response(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def test_react_agent_fixes_toy_bug_with_scripted_llm(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (tmp_path / "test_calc.py").write_text(
        "from calc import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n"
    )
    fixed_calc = "def add(a, b):\n    return a + b\n"
    llm = ScriptedLLM(
        [
            tool_response("call-read", "read_file", {"path": "calc.py"}),
            tool_response("call-write", "write_file", {"path": "calc.py", "content": fixed_calc}),
            tool_response("call-test", "run_test", {"path": "."}),
            final_response("Fixed add() and verified tests pass."),
        ]
    )
    agent = ReActAgent(workdir=tmp_path, llm=llm, max_steps=5)

    result = agent.run("Fix the failing tests.")

    assert result == "Fixed add() and verified tests pass."
    assert (tmp_path / "calc.py").read_text() == fixed_calc
    assert llm.calls == 4
    tool_names = {
        tool["function"]["name"]
        for tool in llm.tools_seen[0]
    }
    assert {"read_file", "write_file", "run_test"}.issubset(tool_names)

    last_messages = llm.messages_seen[-1]
    tool_messages = [m for m in last_messages if m["role"] == "tool"]
    run_test_payload = json.loads(tool_messages[-1]["content"])
    assert run_test_payload["ok"] is True
    assert run_test_payload["tool"] == "run_test"
    assert run_test_payload["result"]["passed"] is True
