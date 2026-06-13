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


def test_react_sandboxes_run_test_path(tmp_path):
    agent = ReActAgent(workdir=tmp_path, llm=DummyLLM())
    outside = Path("/tmp")

    result = agent._invoke_tool("run_test", {"path": str(outside)})

    assert "ERROR" in result
    assert "escapes workdir" in result
