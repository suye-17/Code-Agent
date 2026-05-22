"""ReAct orchestrator: LLM picks tool -> we execute -> result fed back -> repeat.

This is the heart of Phase 1. It is intentionally a single-layer ReAct
(no Planner/Critic). Phase 5 will replace this with a Plan-Execute-Critic
three-state machine; the tool & LLM layers below remain unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.llm.client import LLMClient
from agent.tools.base import Tool
from agent.tools.exec import RunShell
from agent.tools.fs import Grep, ListDir, ReadFile, WriteFile

# System prompt is held FIRST and stable so it benefits from prefix-cache hits.
# Keep this string immutable across calls -- that is the whole point.
SYSTEM_PROMPT = (
    "You are a precise code-fixing agent.\n"
    "Work step by step. On each turn, call exactly ONE tool via function "
    "calling. After enough investigation, propose and apply a fix, then run "
    "the tests to verify. When all tests pass, reply with a final text "
    "message (no tool call) summarizing what you did.\n"
    "Rules:\n"
    "- All paths are interpreted relative to the workdir; do not escape it.\n"
    "- Prefer minimal edits.\n"
    "- Do not give up: if a tool errors, try a different approach."
)


def _default_tools() -> list[Tool]:
    return [ReadFile(), WriteFile(), ListDir(), Grep(), RunShell()]


class ReActAgent:
    """Single-layer ReAct loop with a strict step budget and a path sandbox.

    The path sandbox confines all tool-supplied paths under self.workdir to
    prevent the LLM from reading or writing system files via relative paths.
    """

    def __init__(
        self,
        workdir: Path,
        max_steps: int = 20,
        tools: list[Tool] | None = None,
        llm: LLMClient | None = None,
    ):
        self.workdir = Path(workdir).resolve()
        self.max_steps = max_steps
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or _default_tools())}
        self.llm = llm or LLMClient()

    # ---- path sandbox -------------------------------------------------------

    def _sandbox_path(self, raw: str) -> str | None:
        """Resolve raw path relative to workdir; reject if it escapes.

        Returns the resolved absolute path string, or None if rejected.
        """
        p = Path(raw)
        if not p.is_absolute():
            p = self.workdir / p
        try:
            resolved = p.resolve()
        except OSError:
            return None
        if resolved == self.workdir:
            return str(resolved)
        if self.workdir in resolved.parents:
            return str(resolved)
        return None

    def _invoke_tool(self, name: str, args: dict[str, Any]) -> str:
        if name not in self.tools:
            return f"ERROR: unknown tool {name!r}"
        if "path" in args:
            sandboxed = self._sandbox_path(str(args["path"]))
            if sandboxed is None:
                return f"ERROR: path {args['path']!r} escapes workdir {self.workdir}"
            args = {**args, "path": sandboxed}
        try:
            result = self.tools[name].run(**args)
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"
        if isinstance(result, dict):
            return json.dumps(result)[:8000]
        return str(result)[:8000]

    # ---- main loop ----------------------------------------------------------

    def run(self, task: str) -> str:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": f"workdir = {self.workdir}\n\nTASK:\n{task}"},
        ]
        schemas = [t.schema() for t in self.tools.values()]

        for _step in range(self.max_steps):
            resp = self.llm.chat(messages, tools=schemas)
            msg = resp["choices"][0]["message"]
            messages.append(msg)

            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content") or ""

            for call in calls:
                fn = call["function"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self._invoke_tool(fn["name"], args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        return "MAX_STEPS_REACHED"
