# Task 3 完成文档：加固 Shell 与工具结果

## 任务目标

Task 3 的目标是提升工具调用的稳定性和可诊断性：

- `RunShell` 支持显式 `cwd`，让命令可以在指定目录中执行。
- `ReActAgent` 的工具结果统一返回结构化 JSON。
- 未知工具、路径越界、畸形 JSON、工具异常都能用明确的 `error_type` 表达。

这个任务是后续 Critic、失败回滚和错误归因的基础。专业测试集里失败原因很多，如果工具层只返回普通字符串，系统很难自动判断下一步该重试、回滚还是修正参数。

## 实现思路

### 为什么要给 `RunShell` 增加 `cwd`

原来的 `RunShell` 直接在当前进程目录下执行 shell 命令。Agent 修复代码时，真实目标仓库通常是 `workdir`，如果命令没有明确工作目录，就容易出现：

- pytest 在错误目录执行。
- 相对路径找不到文件。
- LLM 需要在命令里自己写 `cd xxx && ...`，增加出错概率。

本次给 `RunShell.run()` 增加 `cwd` 参数：

```python
def run(self, cmd: str, timeout: int = 60, cwd: str | None = None) -> dict:
    ...
```

并传给 `subprocess.run(..., cwd=cwd)`。

同时在 `RunShell.parameters` 中暴露 `cwd`，确保 function calling schema 能把这个能力提供给 LLM。

### 为什么要结构化工具结果

原来的 `_invoke_tool()` 可能返回三种形态：

- 正常字符串，例如读文件直接返回内容。
- dict 被 `json.dumps(result)[:8000]` 截断。
- 错误字符串，例如 `ERROR: unknown tool`。

这对 LLM 和未来程序化 Critic 都不友好，因为它们需要解析自然语言字符串来判断失败类型。

本次统一为：

```json
{
  "ok": true,
  "tool": "read_file",
  "result": "...",
  "error_type": null,
  "error_message": null,
  "truncated": false
}
```

错误结果统一为：

```json
{
  "ok": false,
  "tool": "run_test",
  "result": null,
  "error_type": "PATH_ESCAPE",
  "error_message": "path '/tmp' escapes workdir ...",
  "truncated": false
}
```

## TDD 过程

### Red：先写失败测试

新增和修改测试：

- `test_run_shell_uses_cwd`
- `test_react_wraps_successful_tool_result`
- `test_react_reports_unknown_tool_as_structured_error`
- `test_react_sandboxes_run_test_path`
- `test_react_reports_malformed_tool_arguments_as_structured_error`
- `test_run_shell_schema_exposes_cwd`

第一次运行目标测试时失败：

```text
TypeError: RunShell.run() got an unexpected keyword argument 'cwd'
json.decoder.JSONDecodeError: Expecting value
```

这些失败证明当前实现还没有 `cwd` 和结构化 JSON 结果。

### Green：实现最小功能

`RunShell` 增加 `cwd`：

```python
r = subprocess.run(
    cmd,
    shell=True,
    capture_output=True,
    text=True,
    timeout=timeout,
    cwd=cwd,
)
```

`ReActAgent` 新增三个辅助方法：

```python
def _tool_success(self, name: str, result: Any) -> str:
    ...

def _tool_error(self, name: str, error_type: str, error_message: str) -> str:
    ...

def _tool_payload(self, payload: dict[str, Any]) -> str:
    ...
```

`_invoke_tool()` 中的错误路径改成：

- `UNKNOWN_TOOL`
- `PATH_ESCAPE`
- Python 异常类型，例如 `TypeError`

`run()` 中的畸形 function arguments 改成：

- `JSON_DECODE_ERROR`

## 核心代码说明

### `_tool_success`

正常工具调用会进入 `_tool_success()`，它把任何工具返回值放到 `result` 字段中。

这样即使底层工具返回字符串、dict 或其他 JSON 可序列化对象，上层都能看到统一结构。

### `_tool_error`

所有可预期错误都走 `_tool_error()`：

- 工具名不存在：`UNKNOWN_TOOL`
- 路径逃逸工作目录：`PATH_ESCAPE`
- LLM 输出畸形 JSON：`JSON_DECODE_ERROR`
- 工具自身抛异常：使用异常类名作为 `error_type`

这让后续错误归因可以直接统计 `error_type`，不需要解析自然语言日志。

### `_tool_payload`

`_tool_payload()` 负责最终 JSON 序列化和长度控制：

```python
text = json.dumps(payload, ensure_ascii=False)
if len(text) <= MAX_TOOL_OUTPUT_CHARS:
    return text

compact = {**payload, "result": str(payload["result"])[:7000], "truncated": True}
return json.dumps(compact, ensure_ascii=False)
```

这样避免超长工具结果直接撑爆上下文，同时通过 `truncated` 明确告诉上层结果被截断。

## 测试结果

### 目标测试

```bash
.venv/bin/python -m pytest tests/unit/test_tools.py::test_run_shell_uses_cwd tests/unit/test_react_tools.py -q
```

结果：

```text
6 passed in 0.18s
```

### 工具层与编排层测试

```bash
.venv/bin/python -m pytest tests/unit/test_tools.py tests/unit/test_react_tools.py -q
```

结果：

```text
20 passed in 3.26s
```

### 全量测试

```bash
.venv/bin/python -m pytest -q
```

结果：

```text
30 passed, 2 skipped in 2.84s
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

- `RunShell.run()` 支持 `cwd`。
- `RunShell` 的 function-calling schema 暴露 `cwd`。
- `ReActAgent._invoke_tool()` 正常结果返回结构化 JSON。
- 未知工具、路径逃逸、畸形 JSON、工具异常返回结构化错误。
- 工具输出支持截断标记 `truncated`。
- 新增 cwd、结构化成功、结构化错误、畸形 arguments 的单元测试。

## 性能交付

- 结构化错误减少 LLM 从自然语言错误中猜测原因的成本。
- `cwd` 降低 shell 命令因目录错误失败的概率。
- `truncated` 字段让后续上下文压缩和日志分页可以基于明确状态继续优化。
