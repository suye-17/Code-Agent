# Code Agent 高分路线交付计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 围绕“专业测试集跑高分”，把当前 Phase 1 ReAct 原型逐步升级为可复现、可评测、可优化的 Code Agent。

**Architecture:** 短期先稳住 B0 闭环和工具可靠性；中期引入上下文工程、局部编辑、Planner-Executor-Critic 与回滚验证；长期接入 SWE-bench-Lite 或同类专业测试集，通过 ablation 和错误归因持续提升 pass@1。所有阶段都用测试和报告证明收益，不做无法提升分数的展示功能。

**Tech Stack:** Python 3.11、Poetry、pytest、httpx、Typer、DeepSeek/OpenAI-compatible Chat API、未来可选 tree-sitter/BM25/Embedding/Docker。

---

## 计划总览

| 阶段 | 计划项 | 测试效果 | 功能交付 | 性能交付 |
|---|---|---|---|---|
| 短期 P0 | 跑通并固化 B0 baseline | `poetry run pytest` 通过；有 key 时 `python eval/baseline_runner.py` 生成报告 | 明确当前 5 个 toy case 通过率、成本、耗时 | 建立 pass rate、单题耗时、单题成本、cache hit rate 基线 |
| 短期 P0 | 增强测试执行工具 | 新增 `RunTest` 单测和 ReAct 集成测试 | Agent 有专用测试工具，不再只靠裸 shell 跑 pytest | 测试输出结构化、截断可控，减少 LLM 误判 |
| 短期 P0 | 加固 shell 与工具结果 | 工具异常、timeout、cwd、returncode 都有单测 | `RunShell` 强制工作目录、结构化返回 stdout/stderr/returncode | 降低无效步数和错误恢复成本 |
| 短期 P0 | Mock LLM 集成测试 | 无 `DEEPSEEK_API_KEY` 也能验证 ReAct 工具链 | CI 可验证核心编排，不依赖真实 API | 回归速度快、成本为 0 |
| 短期 P1 | 扩充 regression set | 15-20 个 toy/中等 case 批量可跑 | 覆盖跨文件、边界条件、测试输出复杂场景 | 更稳定衡量小模型修复能力 |
| 中期 P0 | 局部编辑与分页读取 | 大文件读取、局部替换、错误边界有单测 | 新增范围读取、局部编辑、diff 预览能力 | 减少整文件 token 与误写风险 |
| 中期 P0 | 轻量检索与候选排序 | 检索 golden set recall@k 可测 | grep/BM25/符号启发式候选文件排序 | 提升定位速度和召回率，降低上下文噪声 |
| 中期 P0 | Planner-Executor-Critic | 多步骤修复集成测试通过 | 计划、执行、验证、失败回滚闭环 | 提升多文件任务 pass rate，减少盲目试错 |
| 中期 P1 | Token budget 与重试 | API 429/5xx、超预算、usage 缺失有单测 | LLM 请求重试、退避、预算分层、稳定 prompt 区 | 提升稳定性和 cache hit rate，控制单题成本 |
| 长期 P0 | 专业测试集 runner | SWE-bench-Lite 子集可批量执行并产出报告 | 环境准备、任务执行、patch 验证、报告归档 | 得到真实 pass@1、耗时、成本曲线 |
| 长期 P0 | Ablation 体系 | B0/B1/B2/B3/B4 可重复对比 | 量化检索、压缩、规划、沙箱、回滚各自贡献 | 找到最高 ROI 优化方向 |
| 长期 P1 | 错误归因闭环 | 每个失败 case 有失败类型标签 | 失败分为定位、理解、编辑、测试、环境、预算 | 用失败分布驱动下一轮提分 |

---

## Task 1: 固化 B0 Baseline

**Files:**
- Modify: `eval/baseline_runner.py`
- Modify: `eval/regression_set/seed_cases.jsonl`
- Test: `tests/unit/test_tools.py`

**功能交付**
- 当前 B0 明确定义为 `naive ReAct + full file reads`。
- 每次 baseline 运行都输出 markdown 报告，包含 pass rate、time、spend、token、cache hit rate。
- 报告用于后续所有优化的对照组。

**测试效果**
- `poetry run pytest`：验证现有单测和不依赖 API 的流程。
- `python eval/baseline_runner.py`：在有 `DEEPSEEK_API_KEY` 时验证 5 个 seed case。

**性能交付**
- 拿到当前真实 B0 数据，不再凭预期估算。
- 建立后续提分指标：通过率、平均耗时、平均成本、缓存命中率。

**验收标准**
- 本地单测全部通过。
- `eval/reports/baseline_*.md` 能生成。
- 报告中每个 case 都有 `passed`、`elapsed_s`、`spend_cny`、`tokens_in_hit`、`tokens_in_miss`、`tokens_out`。

---

## Task 2: 增强测试执行工具

**Files:**
- Create: `agent/tools/test.py`
- Modify: `agent/orchestrator/react.py`
- Test: `tests/unit/test_tools.py`
- Test: `tests/integration/test_react_toy.py`

**功能交付**
- 新增 `RunTest` 工具，专门执行 pytest。
- 工具入参包括 `path`、`timeout`、`max_output_chars`。
- 工具输出结构化 JSON，包含 `passed`、`returncode`、`stdout_tail`、`stderr_tail`、`elapsed_s`、`timed_out`。

**测试效果**
- 单测覆盖 pytest 通过、pytest 失败、timeout 三类场景。
- 集成测试验证 ReActAgent 可以通过 `run_test` 完成 toy case 修复验证。

**性能交付**
- 测试输出保留尾部高信息密度内容，减少 8K 粗暴截断导致的关键信息丢失。
- LLM 不需要猜 shell 命令格式，减少工具调用步数。

**验收标准**
- `poetry run pytest tests/unit/test_tools.py -q` 通过。
- `poetry run pytest tests/integration/test_react_toy.py -q` 在有 API key 时通过或无 key 时按既有逻辑跳过。

---

## Task 3: 加固 Shell 与工具结果

**Files:**
- Modify: `agent/tools/exec.py`
- Modify: `agent/orchestrator/react.py`
- Test: `tests/unit/test_tools.py`
- Test: `tests/unit/test_react_tools.py`

**功能交付**
- `RunShell` 支持显式 `cwd`，由 ReActAgent 统一限制在 `workdir` 内。
- 工具调用结果统一封装为结构化结果，至少包含 `ok`、`tool`、`result`、`error_type`、`error_message`、`truncated`。
- 畸形 JSON tool call 不再静默变成空参数，而是返回明确错误给 LLM。

**测试效果**
- 单测覆盖 cwd 生效、路径越界被拒绝、命令 timeout、未知工具、畸形 arguments。
- 回归测试验证工具错误不会炸掉整个 ReAct 循环。

**性能交付**
- 结构化错误让 LLM 更容易恢复，降低重复尝试和 token 浪费。
- cwd 固定减少 shell 命令失败概率。

**验收标准**
- `poetry run pytest tests/unit/test_tools.py tests/unit/test_react_tools.py -q` 通过。
- 工具错误信息中能区分 `TIMEOUT`、`PATH_ESCAPE`、`JSON_DECODE_ERROR`、`UNKNOWN_TOOL`。

---

## Task 4: 增加 Mock LLM 集成测试

**Files:**
- Modify: `tests/integration/test_react_toy.py`
- Create: `tests/unit/test_react_mock_llm.py`

**功能交付**
- 构造一个按脚本返回 tool calls 的 fake LLM。
- 在无 API key 情况下也能验证 ReActAgent 的读文件、写文件、运行测试完整链路。

**测试效果**
- CI 不依赖真实模型即可验证核心编排。
- 能稳定复现工具调用顺序、路径沙箱和最终收敛。

**性能交付**
- Mock 测试成本为 0。
- 核心回归从真实 API 分钟级降到本地秒级。

**验收标准**
- `poetry run pytest tests/unit/test_react_mock_llm.py -q` 通过。
- 不设置 `DEEPSEEK_API_KEY` 时，非真实 API 测试仍全部通过。

---

## Task 5: 扩充 Regression Set

**Files:**
- Modify: `eval/regression_set/seed_cases.jsonl`
- Create: `tests/toy_cases/*`
- Modify: `eval/baseline_runner.py`

**功能交付**
- 从 5 个 case 扩充到 15-20 个 case。
- 新增跨文件调用、边界条件、异常处理、测试输出较长、配置错误、简单依赖问题。

**测试效果**
- baseline runner 可以批量执行新增 case。
- 每个 case 的 pytest 原始失败和修复后验证都可复现。

**性能交付**
- 回归集更接近专业测试集的缺陷形态。
- 后续优化不再只对单文件 toy bug 过拟合。

**验收标准**
- `python eval/baseline_runner.py` 能完整跑完所有 case。
- 报告中失败 case 有 `agent_err` 或 `pytest_tail` 便于定位。

---

## Task 6: 上下文读取与局部编辑

**Files:**
- Create: `agent/tools/edit.py`
- Modify: `agent/tools/fs.py`
- Modify: `agent/orchestrator/react.py`
- Test: `tests/unit/test_tools.py`

**功能交付**
- `ReadFile` 支持 `offset` 和 `limit`。
- 新增局部替换工具，要求 old text 唯一匹配后才替换。
- 新增 diff 预览能力，避免整文件覆盖破坏无关内容。

**测试效果**
- 单测覆盖分页读取、唯一替换、多匹配拒绝、无匹配拒绝、diff 内容正确。

**性能交付**
- 大文件任务不再必须整文件塞进上下文。
- 局部编辑降低误改概率和 token 成本。

**验收标准**
- `poetry run pytest tests/unit/test_tools.py -q` 通过。
- 对大文件读取时返回内容长度受 `limit` 控制。

---

## Task 7: 轻量检索与候选排序

**Files:**
- Create: `agent/context/retriever.py`
- Create: `tests/unit/test_retriever.py`
- Modify: `agent/orchestrator/react.py`

**功能交付**
- 基于文件名、符号名、grep 命中、测试失败栈构建候选文件排序。
- 提供 `search_context` 工具，返回 top-k 文件和关键片段。

**测试效果**
- 构造 golden queries，验证目标文件出现在 top-3/top-5。
- 覆盖单文件、多文件、测试栈定位、无匹配场景。

**性能交付**
- 减少无关文件读取。
- 提升中等仓库任务的定位召回率。

**验收标准**
- `poetry run pytest tests/unit/test_retriever.py -q` 通过。
- 自建 golden set 的 recall@5 达到阶段阈值，例如 80%。

---

## Task 8: Planner-Executor-Critic 闭环

**Files:**
- Create: `agent/orchestrator/planner.py`
- Create: `agent/orchestrator/executor.py`
- Create: `agent/orchestrator/critic.py`
- Create: `agent/orchestrator/state.py`
- Test: `tests/integration/test_plan_execute_critic.py`

**功能交付**
- Planner 输出可执行步骤。
- Executor 按步骤调用工具。
- Critic 运行测试、判断成功、保存 diff、失败时回滚。

**测试效果**
- 集成测试覆盖一次失败后修正、测试通过后停止、超过重试次数退出。

**性能交付**
- 多文件任务不再完全依赖单层 ReAct 自由探索。
- 减少盲目工具调用，提高复杂任务 pass rate。

**验收标准**
- `poetry run pytest tests/integration/test_plan_execute_critic.py -q` 通过。
- regression set 中多文件 case 通过率相对 B0 有提升。

---

## Task 9: Token Budget 与 LLM 稳定性

**Files:**
- Modify: `agent/llm/client.py`
- Create: `agent/llm/budget.py`
- Test: `tests/unit/test_llm_client.py`

**功能交付**
- 请求支持 retry/backoff。
- usage 缺失、429、5xx、timeout 有明确错误类型。
- 支持按阶段分配 token budget。

**测试效果**
- 单测 mock HTTP 响应，覆盖成功、429 重试、5xx 重试、超预算、usage 缺失。

**性能交付**
- 提升批量评测稳定性。
- 降低因临时网络/API 抖动导致的失败率。

**验收标准**
- `poetry run pytest tests/unit/test_llm_client.py -q` 通过。
- 重试次数、timeout、预算阈值可配置。

---

## Task 10: 专业测试集 Runner 与 Ablation

**Files:**
- Create: `eval/swe_bench_runner.py`
- Create: `eval/ablation_runner.py`
- Create: `eval/reports/`
- Test: `tests/unit/test_eval_runner.py`

**功能交付**
- 支持 SWE-bench-Lite 子集或同类专业测试集批量运行。
- 支持 B0/B1/B2/B3/B4 配置对比。
- 报告输出 pass@1、成本、耗时、token、错误类型。

**测试效果**
- 单测用 fake dataset 和 fake agent 验证 runner 汇总逻辑。
- 小规模真实子集 smoke test 验证环境可跑。

**性能交付**
- 得到真实专业测试集 pass@1。
- 通过 ablation 定位最高收益模块。

**验收标准**
- `poetry run pytest tests/unit/test_eval_runner.py -q` 通过。
- 小样本 runner 能生成 `eval/reports/*.md` 或 `eval/reports/*.json`。
- 报告包含 B0/B1/B2/B3/B4 对比表。

---

## 里程碑

| 里程碑 | 时间范围 | 必达指标 | 关键交付物 |
|---|---|---|---|
| M1: 稳定 B0 | 1 周 | 本地单测全过；baseline report 可生成 | `RunTest`、结构化工具结果、mock LLM 测试 |
| M2: 扩展回归 | 2 周 | regression set 达 15-20 个；批量运行不中断 | 新 toy cases、报告留存、失败摘要 |
| M3: 上下文工程 | 3-4 周 | golden set recall@5 达阶段阈值；token 明显下降 | 分页读取、局部编辑、轻量检索 |
| M4: 规划验证闭环 | 5-6 周 | 多文件 case 通过率相对 B0 提升 | Planner-Executor-Critic、diff、回滚 |
| M5: 专业评测 | 7-12 周 | 获得专业测试集 pass@1 和 ablation 报告 | SWE-bench runner、ablation runner、错误归因 |

---

## 执行原则

- 先跑测试再提交，所有测试跑通后才允许 commit。
- push 由用户执行。
- 每个任务先写或补测试，再实现功能，再跑最小测试，最后跑全量测试。
- 不做 Web UI、插件、多 Agent 协同、权限审计，直到专业测试集指标稳定。
- 每个性能优化都必须有 baseline 前后对比，否则不算交付。
