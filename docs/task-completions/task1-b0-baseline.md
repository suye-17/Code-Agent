# Task 1 完成文档：固化 B0 Baseline

## 任务目标

Task 1 的目标是让当前 B0 baseline 更可测试、可复现、可作为后续优化对照。

B0 的定义保持不变：`naive ReAct + full file reads`。本任务不提升 Agent 解题能力，而是把 baseline 报告中的关键指标固化为可单元测试的纯逻辑，避免后续改动破坏报告结构或指标计算。

## 实现思路

原始 `eval/baseline_runner.py` 把三类职责都放在 `main()` 中：

- 批量运行 regression case。
- 汇总每个 case 的通过率、成本、token 和缓存命中率。
- 拼接 markdown 报告并写入 `eval/reports/`。

这种写法能运行，但不利于测试。因为如果只想验证报告字段是否正确，也必须准备真实 case、真实 LLM client 和真实 pytest 子进程。

本次重构采用“分离纯逻辑”的方式：

- `summarize_rows(rows)`：只负责汇总指标。
- `render_report(rows, generated_at=None)`：只负责把 rows 渲染成 markdown。
- `main()`：继续负责真实运行 case、写报告文件和打印输出。

这样做的教学重点是：把“会产生副作用的逻辑”和“纯数据转换逻辑”拆开。纯函数容易测试、运行快、没有 API 成本，适合放进 CI。

## TDD 过程

### Red：先写失败测试

新增 `tests/unit/test_baseline_runner.py`，测试期望从 `eval.baseline_runner` 导入：

- `summarize_rows`
- `render_report`

首次运行：

```bash
.venv/bin/python -m pytest tests/unit/test_baseline_runner.py -q
```

失败结果符合预期：

```text
ImportError: cannot import name 'render_report' from 'eval.baseline_runner'
```

这说明测试确实覆盖了尚未实现的能力，而不是测试已有行为。

### Green：实现最小代码

在 `eval/baseline_runner.py` 中新增：

```python
def summarize_rows(rows: list[dict]) -> dict:
    total = len(rows)
    passed = sum(r["passed"] for r in rows)
    total_spend = round(sum(r["spend_cny"] for r in rows), 6)
    total_hit = sum(r["tokens_in_hit"] for r in rows)
    total_miss = sum(r["tokens_in_miss"] for r in rows)
    token_total = total_hit + total_miss
    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total else 0.0,
        "total_spend": total_spend,
        "total_hit": total_hit,
        "total_miss": total_miss,
        "cache_hit_rate": total_hit / token_total if token_total else 0.0,
    }
```

这段代码的关键点：

- `pass_rate` 用 `passed / total` 计算，并处理空 rows 的情况。
- `total_spend` 做了 `round(..., 6)`，避免浮点加法带来的测试不稳定。
- `cache_hit_rate` 用 `hit / (hit + miss)`，没有 token 时返回 `0.0`。

新增报告渲染函数：

```python
def render_report(rows: list[dict], generated_at: str | None = None) -> str:
    summary = summarize_rows(rows)
    generated_at = generated_at or time.strftime("%Y-%m-%d %H:%M:%S")
    ...
```

这段代码的关键点：

- `generated_at` 可注入，单测中传固定时间，避免测试依赖当前时钟。
- 报告保留 B0 标题和所有关键字段。
- 每个 case 行包含 pass/fail、耗时、成本、输入命中 token、输入未命中 token、输出 token、pytest tail。
- 如果存在 `agent_err`，额外输出 `Agent errors` 小节，便于批量评测排查失败。

最后让 `main()` 复用：

```python
report = render_report(rows)
```

这样真实运行路径和单元测试路径使用同一套报告逻辑。

## 核心代码说明

### `summarize_rows`

职责：从 case 级别 rows 中计算全局指标。

输入是一组形如下面的字典：

```python
{
    "id": "case_ok",
    "passed": True,
    "elapsed_s": 1.2,
    "spend_cny": 0.1,
    "tokens_in_hit": 80,
    "tokens_in_miss": 20,
    "tokens_out": 10,
    "agent_err": None,
    "pytest_tail": "1 passed",
}
```

输出是 baseline 汇总：

```python
{
    "total": 2,
    "passed": 1,
    "pass_rate": 0.5,
    "total_spend": 0.3,
    "total_hit": 100,
    "total_miss": 100,
    "cache_hit_rate": 0.5,
}
```

### `render_report`

职责：把 rows 转换成稳定的 markdown 报告文本。

这个函数不读文件、不写文件、不调用模型，适合单测。真实写入文件仍由 `main()` 完成。

## 测试结果

### 环境验证

```bash
.venv/bin/python --version
.venv/bin/python -m pytest --version
.venv/bin/python -c "import httpx, typer, dotenv, pydantic; print('deps ok')"
```

结果：

```text
Python 3.11.15
pytest 9.0.3
deps ok
```

### 新增单测

```bash
.venv/bin/python -m pytest tests/unit/test_baseline_runner.py -q
```

结果：

```text
2 passed in 0.02s
```

### 全量测试

```bash
.venv/bin/python -m pytest -q
```

结果：

```text
21 passed, 2 skipped in 1.22s
```

两个 skipped 来自需要真实 DeepSeek API key 的集成测试跳过逻辑，属于预期现象。

## 未运行项说明

未直接运行：

```bash
python eval/baseline_runner.py
```

原因：该命令需要真实 `DEEPSEEK_API_KEY`，会产生 API 调用成本。当前 Task 1 已通过单元测试固化报告逻辑；真实 B0 跑分应在确认 `.env` 中配置 key 和预算后执行。

建议后续手动运行：

```bash
source .venv/bin/activate
python eval/baseline_runner.py
```

运行后会生成：

```text
eval/reports/baseline_*.md
```

该目录已在 `.gitignore` 中忽略，适合本地留存实验结果，不建议提交大量运行报告。

## 交付结果

- 新增 baseline runner 单元测试。
- 新增 `summarize_rows` 和 `render_report`，让报告指标可测试。
- 保持 B0 baseline 行为不变，真实 case 执行仍由 `run_one()` 和 `main()` 完成。
- 全量测试通过。
