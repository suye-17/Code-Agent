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
    return [ReadFile(), WriteFile(), ListDir(), Grep(), RunShell()]


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
            return f"ERROR: unknown tool {name!r}"
        # 2. 仅当参数里出现 path 字段时才走沙箱（run_shell 的 cmd 不沙箱）
        if "path" in args:
            sandboxed = self._sandbox_path(str(args["path"]))
            if sandboxed is None:
                return f"ERROR: path {args['path']!r} escapes workdir {self.workdir}"
            args = {**args, "path": sandboxed}
        # 3. 工具执行：所有异常都吞掉转成字符串，避免单次工具失败炸掉整个循环
        try:
            result = self.tools[name].run(**args)
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"
        # 4. 输出统一截断 8K 字符，防 LLM 误读大文件把 token 烧光
        if isinstance(result, dict):
            return json.dumps(result)[:8000]
        return str(result)[:8000]

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
                except json.JSONDecodeError:
                    # 极少见：LLM 输出畸形 JSON。给空 dict，让工具自身报参数缺失
                    args = {}
                result = self._invoke_tool(fn["name"], args)
                # tool_call_id 必须原样回填，否则下一轮请求会被 API 拒绝
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        # 跑满步数预算还没收敛，约定的"超时退出"标记
        return "MAX_STEPS_REACHED"
