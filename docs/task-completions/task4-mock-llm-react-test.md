# Task 4 完成文档：增加 Mock LLM 集成测试

## 任务目标

Task 4 的目标是在不依赖真实 `DEEPSEEK_API_KEY` 的情况下，验证 ReAct Agent 的核心工具调用链。

真实 LLM 集成测试有两个问题：

- 没有 API key 时会跳过，CI 无法验证核心闭环。
- 调用真实模型有成本、速度慢、结果可能不稳定。

因此本任务新增 `ScriptedLLM`，用脚本化响应模拟模型 function calling，让本地测试稳定覆盖：

- `read_file`
- `write_file`
- `run_test`
- 最终无工具调用收敛

## 实现思路

新增 `tests/unit/test_react_mock_llm.py`。

测试创建一个临时 bug 项目：

```python
def add(a, b):
    return a - b
```

以及对应失败测试：

```python
def test_add():
    assert add(2, 3) == 5
```

然后用 `ScriptedLLM` 按顺序返回工具调用：

1. 调用 `read_file` 读取 `calc.py`。
2. 调用 `write_file` 写入修复后的 `calc.py`。
3. 调用 `run_test` 执行 pytest。
4. 返回最终总结文本，表示任务完成。

这验证了 ReAct 循环中最关键的路径：模型请求工具、Agent 执行工具、工具结果回填、继续下一轮、最终收敛。

## 核心代码说明

### `ScriptedLLM`

```python
class ScriptedLLM:
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.calls = 0
        self.messages_seen: list[list[dict]] = []
        self.tools_seen: list[list[dict] | None] = []

    def chat(self, messages, tools=None, model=None):
        self.messages_seen.append(messages.copy())
        self.tools_seen.append(tools)
        response = self.responses[self.calls]
        self.calls += 1
        return response
```

它模拟 `LLMClient.chat()` 接口，但不发网络请求。每次调用只返回预先准备好的响应。

### `tool_response`

```python
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
```

这个 helper 生成 OpenAI-compatible function calling 响应，形状和真实 LLM 返回一致。

### 验证点

测试断言：

- Agent 返回最终文本。
- `calc.py` 被正确修复。
- LLM 被调用 4 次。
- function-calling schema 中包含 `read_file`、`write_file`、`run_test`。
- 最后一条 `run_test` 工具结果是结构化 JSON。
- `run_test` 的嵌套结果中 `passed` 为 `True`。

## 测试结果

### Mock LLM 测试

```bash
.venv/bin/python -m pytest tests/unit/test_react_mock_llm.py -q
```

结果：

```text
1 passed in 0.59s
```

### 全量测试

```bash
.venv/bin/python -m pytest -q
```

结果：

```text
32 passed, 2 skipped in 3.25s
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

- 新增无需 API key 的 ReAct 闭环测试。
- 验证 `read_file -> write_file -> run_test -> final response` 全流程。
- 验证 ReAct 向 LLM 暴露了包含 `run_test` 的工具 schema。
- 验证结构化工具结果能被测试解析。

## 性能交付

- 测试不调用真实模型，成本为 0。
- 单测运行约 0.6 秒，适合每次提交和 CI 运行。
- 让核心 Agent 编排回归从依赖外部 API 变成稳定本地测试。
