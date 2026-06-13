from __future__ import annotations

import json

from agent.orchestrator.react import ReActAgent
from agent.tools.search import SearchContext


class DummyLLM:
    def chat(self, _messages, tools=None, model=None):  # noqa: ARG002
        return {"choices": [{"message": {"role": "assistant", "content": "done"}}]}


def test_search_context_tool_returns_ranked_code_results(tmp_path):
    (tmp_path / "config.py").write_text(
        "DEFAULT_TIMEOUT = 30\n\n"
        "def get_timeout(settings):\n"
        "    return settings.get('timeout', DEFAULT_TIMEOUT)\n"
    )
    (tmp_path / "math_utils.py").write_text("def add(a, b):\n    return a + b\n")

    result = SearchContext().run(path=str(tmp_path), query="timeout default", top_k=3)

    assert result["query"] == "timeout default"
    assert result["root"] == str(tmp_path)
    assert result["results"][0]["path"].endswith("config.py")
    assert result["results"][0]["symbols"][0]["name"] == "get_timeout"
    assert "DEFAULT_TIMEOUT" in result["results"][0]["snippet"]


def test_react_default_tools_include_search_context(tmp_path):
    agent = ReActAgent(workdir=tmp_path, llm=DummyLLM())

    assert "search_context" in agent.tools


def test_react_sandboxes_search_context_path(tmp_path):
    agent = ReActAgent(workdir=tmp_path, llm=DummyLLM())

    result = json.loads(agent._invoke_tool("search_context", {"path": "/tmp", "query": "secret"}))

    assert result["ok"] is False
    assert result["error_type"] == "PATH_ESCAPE"
