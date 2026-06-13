"""ReAct 编排器：LLM 选工具 → 我们执行 → 把结果回灌 → 循环直到收敛。

这是 Phase 1 的核心，刻意保持单层 ReAct（不含 Planner / Critic）。
Phase 5 会把它替换为 Plan-Execute-Critic 三态机；
下面依赖的工具层和 LLM 层届时无需改动。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.llm.client import LLMClient
from agent.tools.base import Tool
from agent.tools.exec import RunShell
from agent.tools.fs import Grep, ListDir, ReadFile, WriteFile
from agent.tools.test import RunTest

# system prompt 放在最前并保持不可变，是命中 DeepSeek prefix-cache 的前提。
# 一旦这段字符串发生哪怕一个字节的改动，缓存命中率就会从 ~80% 跌到 0。
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
    return [ReadFile(), WriteFile(), ListDir(), Grep(), RunShell(), RunTest()]


MAX_TOOL_OUTPUT_CHARS = 8000


class ReActAgent:
    """单层 ReAct 循环，自带步数预算与路径沙箱。

    路径沙箱把所有工具传入的 path 强制约束在 self.workdir 之内，
    防止 LLM 通过相对路径或符号链接读写工作目录之外的系统文件。
    """

    def __init__(
        self,
        workdir: Path,
        max_steps: int = 20,
        tools: list[Tool] | None = None,
        llm: LLMClient | None = None,
    ):
        # 立刻规范化为绝对路径，后续沙箱比较只做一次解析
        self.workdir = Path(workdir).resolve()
        self.max_steps = max_steps
        # 工具改用 dict（key=name），既能 O(1) 查找也强制工具名唯一
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or _default_tools())}
        self.llm = llm or LLMClient()

    # ---- 路径沙箱 -----------------------------------------------------------

    def _sandbox_path(self, raw: str) -> str | None:
        """把原始路径解析到 workdir 之内，越界返回 None。

        关键安全点：使用 Path.resolve() 会自动展开 `..` 和符号链接，
        即使 LLM 传入 "../../etc/passwd" 也会被识破。
        """
        p = Path(raw)
        if not p.is_absolute():
            # 相对路径补全为 workdir/相对
            p = self.workdir / p
        try:
            resolved = p.resolve()
        except OSError:
            # resolve 抛 OSError（极少见，例如循环符号链接）→ 直接判定越界
            return None
        # workdir 自身允许（如 list_dir(".")）
        if resolved == self.workdir:
            return str(resolved)
        # workdir 的子孙允许
        if self.workdir in resolved.parents:
            return str(resolved)
        # 其他一律越界
        return None

    def _invoke_tool(self, name: str, args: dict[str, Any]) -> str:
        # 1. 未知工具：LLM 偶尔会幻觉出不存在的工具名，直接以 ERROR 字符串告知
        if name not in self.tools:
            return self._tool_error(
                name,
                "UNKNOWN_TOOL",
                f"unknown tool {name!r}",
            )
        # 2. 仅当参数里出现 path 字段时才走沙箱（run_shell 的 cmd 不沙箱）
        if "path" in args:
            sandboxed = self._sandbox_path(str(args["path"]))
            if sandboxed is None:
                return self._tool_error(
                    name,
                    "PATH_ESCAPE",
                    f"path {args['path']!r} escapes workdir {self.workdir}",
                )
            args = {**args, "path": sandboxed}
        # 3. 工具执行：所有异常都吞掉转成字符串，避免单次工具失败炸掉整个循环
        try:
            result = self.tools[name].run(**args)
        except Exception as e:
            return self._tool_error(name, type(e).__name__, str(e))
        return self._tool_success(name, result)

    def _tool_success(self, name: str, result: Any) -> str:
        return self._tool_payload(
            {
                "ok": True,
                "tool": name,
                "result": result,
                "error_type": None,
                "error_message": None,
                "truncated": False,
            }
        )

    def _tool_error(self, name: str, error_type: str, error_message: str) -> str:
        return self._tool_payload(
            {
                "ok": False,
                "tool": name,
                "result": None,
                "error_type": error_type,
                "error_message": error_message,
                "truncated": False,
            }
        )

    def _tool_payload(self, payload: dict[str, Any]) -> str:
        text = json.dumps(payload, ensure_ascii=False)
        if len(text) <= MAX_TOOL_OUTPUT_CHARS:
            return text

        compact = {**payload, "result": str(payload["result"])[:7000], "truncated": True}
        return json.dumps(compact, ensure_ascii=False)

    # ---- 主循环 -------------------------------------------------------------

    def run(self, task: str) -> str:
        # workdir 写在 user message 而非 system prompt：让 system 部分保持完全稳定
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

            # LLM 不再调用工具 → 视为收敛，返回最终文本
            calls = msg.get("tool_calls") or []
            if not calls:
                return msg.get("content") or ""

            # 依次执行 LLM 这一轮请求的所有 tool_calls
            for call in calls:
                fn = call["function"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                    result = self._invoke_tool(fn["name"], args)
                except json.JSONDecodeError as e:
                    result = self._tool_error(
                        fn["name"],
                        "JSON_DECODE_ERROR",
                        str(e),
                    )
                # tool_call_id 必须原样回填，否则下一轮请求会被 API 拒绝
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        # 跑满步数预算还没收敛，约定的"超时退出"标记
        return "MAX_STEPS_REACHED"
