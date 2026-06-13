# Task 2 完成文档：增强测试执行工具

## 任务目标

Task 2 的目标是新增一个专用测试执行工具 `RunTest`，让 Agent 不必依赖裸 `run_shell` 去猜测 pytest 命令。

这个任务服务于“专业测试集跑高分”的短期 P0 目标：稳定验证闭环。后续 Planner、Critic、失败回滚和错误归因都需要一个稳定、结构化、可机器读取的测试结果。

## 实现思路

原项目已有 `RunShell`，可以执行任意 shell 命令，但它有三个问题：

- LLM 需要自己拼 pytest 命令，容易写错路径、参数或工作目录。
- shell 输出只有 `stdout`、`stderr`、`returncode`，没有直接的 `passed` 或 `timed_out`。
- pytest 输出可能很长，直接交给 LLM 容易浪费 token。

因此新增 `RunTest`：

- 输入：`path`、`timeout`、`max_output_chars`。
- 行为：使用当前虚拟环境 Python 执行 `python -m pytest -q <path>`。
- 输出：结构化字典，包含 `passed`、`returncode`、`stdout_tail`、`stderr_tail`、`elapsed_s`、`timed_out`。

## TDD 过程

### Red：先写失败测试

在 `tests/unit/test_tools.py` 中先添加：

- `test_run_test_passes_pytest_suite`
- `test_run_test_reports_pytest_failure`
- `test_run_test_reports_timeout`
- 更新 `test_all_tools_have_unique_names`，要求包含 `run_test`

首次运行：

```bash
.venv/bin/python -m pytest tests/unit/test_tools.py -q
```

失败结果符合预期：

```text
ModuleNotFoundError: No module named 'agent.tools.test'
```

说明测试确实覆盖了尚未实现的新工具。

### Green：实现最小功能

新增 `agent/tools/test.py`：

```python
class RunTest(Tool):
    name = "run_test"
    description = (
        "Run pytest for a file or directory. Returns passed, returncode, "
        "stdout_tail, stderr_tail, elapsed_s and timed_out."
    )
```

核心执行逻辑：

```python
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", path],
    capture_output=True,
    text=True,
    timeout=timeout,
)
```

这里用 `sys.executable` 是关键点：它保证 `RunTest` 使用当前 `.venv` 的 Python 解释器，而不是系统自带 Python。这样测试运行环境和项目依赖保持一致。

成功或失败都返回同一种结构：

```python
{
    "passed": result.returncode == 0,
    "returncode": result.returncode,
    "stdout_tail": _tail(result.stdout, max_output_chars),
    "stderr_tail": _tail(result.stderr, max_output_chars),
    "elapsed_s": elapsed,
    "timed_out": False,
}
```

超时时返回：

```python
{
    "passed": False,
    "returncode": -1,
    "stdout_tail": ...,
    "stderr_tail": "...TIMEOUT after <timeout>s",
    "elapsed_s": elapsed,
    "timed_out": True,
}
```

### 接入 ReAct

在 `agent/orchestrator/react.py` 中把 `RunTest` 加入默认工具：

```python
from agent.tools.test import RunTest

def _default_tools() -> list[Tool]:
    return [ReadFile(), WriteFile(), ListDir(), Grep(), RunShell(), RunTest()]
```

这样 LLM 的 function calling schema 中会出现 `run_test`，模型可以直接选择它来验证修复结果。

## 核心代码说明

### `_tail`

```python
def _tail(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    return text[-max_chars:]
```

pytest 的 summary、失败统计和 traceback 末尾通常最有价值，所以保留尾部比保留头部更适合给 LLM 做判断。

### `RunTest.run`

该方法做了四件事：

- 记录开始时间，计算 `elapsed_s`。
- 用当前 Python 运行 pytest。
- 把 pytest 的成功、失败、超时统一成结构化结果。
- 限制输出长度，避免大段日志占满上下文。

### ReAct 路径沙箱复用

`RunTest` 的参数包含 `path`，因此会复用 `ReActAgent._invoke_tool()` 中已有的路径沙箱逻辑。测试中验证了传入工作目录外路径时会被拒绝。

## 测试结果

### RunTest 工具测试

```bash
.venv/bin/python -m pytest tests/unit/test_tools.py -q
```

结果：

```text
14 passed in 2.69s
```

### ReAct 默认工具接入测试

```bash
.venv/bin/python -m pytest tests/unit/test_react_tools.py tests/unit/test_tools.py -q
```

结果：

```text
16 passed in 2.79s
```

### 全量测试

```bash
.venv/bin/python -m pytest -q
```

结果：

```text
26 passed, 2 skipped in 2.85s
```

### Ruff 检查

```bash
.venv/bin/python -m ruff check .
```

结果：

```text
All checks passed!
```

## 功能交付

- 新增 `agent.tools.test.RunTest`。
- `RunTest` 支持 pytest 成功、失败和超时三类结果。
- `RunTest` 返回结构化测试结果，便于 LLM 和未来 Critic 判断。
- `RunTest` 已接入 ReAct 默认工具列表。
- 新增工具层和编排层单元测试。

## 性能交付

- 测试输出按尾部截断，减少 token 浪费。
- LLM 不需要自行构造 pytest shell 命令，降低无效工具调用概率。
- 测试结果结构化后，后续可以直接用于失败归因、自动回滚和 pass/fail 指标统计。
