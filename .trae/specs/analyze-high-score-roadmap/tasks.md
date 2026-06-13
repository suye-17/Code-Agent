# Tasks

- [x] Task 1: 固化当前项目现状分析：基于源码和文档梳理已完成功能模块、核心能力、技术栈和当前开发阶段。
  - [x] SubTask 1.1: 梳理 `agent/cli.py`、`agent/orchestrator/react.py`、`agent/llm/client.py`、`agent/tools/*` 的职责边界。
  - [x] SubTask 1.2: 梳理 `tests/*`、`eval/baseline_runner.py`、`eval/regression_set/seed_cases.jsonl` 的测试与评测覆盖。
  - [x] SubTask 1.3: 对比 `docs/superpowers/plans/2026-05-22-enterprise-code-agent.md` 中的目标架构，标注已实现和未实现能力。

- [x] Task 2: 建立当前性能基线：明确现有 B0 基线能衡量什么、不能衡量什么，以及缺失的实测数据。
  - [x] SubTask 2.1: 记录当前 B0 定义为 naive ReAct + full file reads。
  - [x] SubTask 2.2: 明确现有指标包括 pass rate、耗时、花费、缓存命中 token、缓存未命中 token、输出 token。
  - [x] SubTask 2.3: 标注仓库当前缺少已提交 baseline 报告，因此不能声称真实 pass@1 或成本表现。

- [x] Task 3: 分析短板和提升空间：从架构、功能、性能、错误处理和专业测试集适配五个维度形成问题清单。
  - [x] SubTask 3.1: 标注单层 ReAct、无 Planner/Critic、无 Context Engine、无 Sandbox 的架构短板。
  - [x] SubTask 3.2: 标注缺少专用 `run_test`、局部编辑、结构化工具结果、git 回滚和评测失败分类的功能短板。
  - [x] SubTask 3.3: 标注完整历史消息、完整文件读取、工具输出硬截断、HTTP client 不复用等性能短板。
  - [x] SubTask 3.4: 标注 API 异常、畸形 tool call、grep 失败语义、状态文件 IO 异常等错误处理短板。
  - [x] SubTask 3.5: 标注 5 个 toy case 规模过小、真实集成测试依赖 API key、缺少 SWE-bench harness 的高分短板。

- [x] Task 4: 制定短期开发计划：围绕稳定闭环、修复 P0 缺陷和扩大回归集制定 1-2 周内可交付目标。
  - [x] SubTask 4.1: 交付 shell 工作目录约束、专用 `run_test` 工具、结构化 tool result、失败可恢复错误模型。
  - [x] SubTask 4.2: 交付 baseline 报告留存、回归集扩到 15-20 个 toy/中等 case、无 API key 的 mock LLM 集成测试。
  - [x] SubTask 4.3: 预期效果是 B0 可重复跑分、核心工具稳定性提升、失败排查成本下降。

- [x] Task 5: 制定中期开发计划：围绕上下文工程、规划验证闭环和性能优化制定 3-6 周内可交付目标。
  - [x] SubTask 5.1: 交付分页读取、局部编辑、测试输出头尾保留、token budget 管理和请求重试。
  - [x] SubTask 5.2: 交付轻量符号索引、BM25/grep 混合检索、候选文件排序和上下文压缩。
  - [x] SubTask 5.3: 交付 Planner-Executor-Critic 雏形、自动测试验证、diff 留存和失败回滚。
  - [x] SubTask 5.4: 预期效果是中等复杂度多文件任务通过率提升，单题 token 和耗时受控。

- [x] Task 6: 制定长期开发计划：围绕专业测试集、ablation 和高级能力制定 6-12 周内可交付目标。
  - [x] SubTask 6.1: 交付 SWE-bench-Lite 或同类专业测试集 runner、分层抽样、环境准备和批量报告。
  - [x] SubTask 6.2: 交付 B0/B1/B2/B3/B4 消融实验，量化检索、压缩、规划、沙箱和回滚的增益。
  - [x] SubTask 6.3: 交付错误归因体系，把失败归类为定位、理解、编辑、测试、环境、预算等类型。
  - [x] SubTask 6.4: 预期效果是形成可解释、可复现、可优化的专业测试集高分闭环。

- [x] Task 7: 建立风险与瓶颈应对表：识别阻断高分目标的关键风险，并为每类风险给出应对策略。
  - [x] SubTask 7.1: 覆盖 API 预算、测试环境不稳定、检索召回不足、上下文过长、shell 安全、评测污染和过度工程风险。
  - [x] SubTask 7.2: 为每项风险绑定缓解动作，例如预算熔断、失败隔离、Live 数据集对照、阶段性砍需求、报告留存。

- [x] Task 8: 完成规格验收：确保 `spec.md`、`tasks.md`、`checklist.md` 三份文档能指导后续实现，且没有引入代码改动。
  - [x] SubTask 8.1: 检查每个用户需求都能在规格、任务或检查清单中找到对应项。
  - [x] SubTask 8.2: 检查阶段计划包含目标里程碑、关键交付物和预期效果。
  - [x] SubTask 8.3: 检查后续实现任务足够小、可验证、优先级清晰。

# Task Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 1 and Task 2.
- Task 4 depends on Task 3.
- Task 5 depends on Task 3 and Task 4.
- Task 6 depends on Task 3 and Task 5.
- Task 7 depends on Task 3, Task 4, Task 5 and Task 6.
- Task 8 depends on Task 1 through Task 7.
