# Code Agent 高分路线分析 Spec

## Why
当前项目目标是在专业测试集上获得高分，但代码实现仍处于最小 ReAct 原型阶段，缺少面向真实仓库缺陷修复所需的检索、规划、验证、沙箱和评测闭环。需要先系统梳理现状、识别短板，并把后续开发拆成可执行、可验收的阶段路线图，避免盲目堆功能。

## What Changes
- 新增一份面向“专业测试集高分”的项目现状分析规格，覆盖已完成功能、核心能力、性能表现、架构短板、功能缺口、风险与瓶颈。
- 制定短期、中期、长期三阶段开发路线，分别聚焦稳定闭环、上下文与架构升级、高级能力与规模化评测。
- 为每个阶段定义目标里程碑、关键交付物、预期效果和验收标准。
- 明确下一步开发优先级，以 `pass@1`、成本、耗时、缓存命中率、回归通过率作为核心指标。
- 不在本次规格阶段修改业务代码，不提交实现。

## Impact
- Affected specs: Agent 编排、工具层、LLM 客户端、评测体系、未来 Context Engine、未来 Sandbox。
- Affected code: `agent/orchestrator/react.py`、`agent/llm/client.py`、`agent/tools/*`、`eval/baseline_runner.py`、`eval/regression_set/seed_cases.jsonl`、`tests/*`。

## Current State
### 已完成的功能模块
- CLI 入口：`agent/cli.py` 支持通过命令行传入任务、工作目录和步数预算，启动 `ReActAgent` 执行修复任务。
- LLM 客户端：`agent/llm/client.py` 封装 DeepSeek/OpenAI-compatible Chat API，支持每日预算熔断、缓存命中/未命中/输出 token 三段计费和本地 `spend.json` 状态持久化。
- ReAct 编排器：`agent/orchestrator/react.py` 实现单层 ReAct 循环，支持 function calling、工具调用结果回灌、最大步数终止、基于 `workdir` 的文件路径沙箱。
- 工具层：`agent/tools/base.py` 定义工具抽象，`agent/tools/fs.py` 提供读文件、写文件、列目录、grep，`agent/tools/exec.py` 提供 shell 执行。
- 测试体系：`tests/unit` 覆盖工具层和 LLM 计费逻辑，`tests/integration/test_react_toy.py` 覆盖一个真实 API toy 修复流程。
- 基线评测：`eval/baseline_runner.py` 可批量运行 5 个 toy regression case，输出 pass rate、耗时、花费、token 和缓存命中率。

### 已实现的核心能力
- 能把自然语言 bug 修复任务转化为 LLM 工具调用循环。
- 能通过文件读取、搜索、写入和运行 shell 命令完成小型代码修复。
- 能用 pytest 结果作为客观验证信号，并在 baseline runner 中按 case 汇总。
- 能追踪 API 预算和 prefix cache 命中数据，为后续成本优化提供基础。
- 能防止文件工具通过相对路径或符号链接逃逸 `workdir`。

### 现有性能表现评估
- 当前仓库没有已提交的 `eval/reports` 历史报告，因此无法直接证明真实 baseline 通过率、平均耗时或平均成本。
- 现有 B0 基线定义为“naive ReAct + full file reads”，预期只适合 5 个 toy case，不足以代表专业测试集表现。
- 当前性能瓶颈主要来自完整历史消息累积、完整文件读取、无检索压缩、工具输出 8K 硬截断、每次请求新建 HTTP client。
- 当前成本控制已有基础计费与预算熔断，但缺少 token budget 分层、prompt 稳定区管理、请求重试和缓存命中率自动回归阈值。

## ADDED Requirements
### Requirement: 现状分析报告
系统 SHALL 形成一份基于当前代码事实的项目现状分析，明确已完成功能、核心能力、性能基线和与目标架构的差距。

#### Scenario: 完整覆盖当前模块
- **WHEN** 开发者阅读规格文档
- **THEN** 能看到 CLI、LLM 客户端、ReAct 编排器、工具层、测试和评测脚本的职责与成熟度

#### Scenario: 区分已实现和规划中能力
- **WHEN** 开发者评估项目阶段
- **THEN** 能清晰区分已实现的 Phase 1 能力和仍未实现的 Context Engine、Plan-Execute-Critic、Sandbox、SWE-bench harness

### Requirement: 短板与提升空间分析
系统 SHALL 从架构设计、功能完整性、性能优化、错误处理和高分测试集适配性五个维度识别短板。

#### Scenario: 识别高优先级问题
- **WHEN** 开发者准备下一轮实现
- **THEN** 能优先定位影响专业测试集 pass@1 的 P0 问题，包括 shell 沙箱、专用测试工具、结构化工具结果、自动验证与回滚、检索能力不足

#### Scenario: 识别中长期技术债
- **WHEN** 开发者制定中长期计划
- **THEN** 能看到 Context Engine、混合检索、上下文压缩、三态编排、SWE-bench 评测和 ablation 的建设顺序

### Requirement: 分阶段高分路线图
系统 SHALL 以“专业测试集高分”为目标，制定短期、中期、长期三阶段路线图。

#### Scenario: 短期阶段
- **WHEN** 项目进入短期开发
- **THEN** 目标 SHALL 是稳定 B0 闭环、补齐安全和错误处理短板、扩充 toy regression、生成可重复 baseline

#### Scenario: 中期阶段
- **WHEN** 项目进入中期开发
- **THEN** 目标 SHALL 是引入上下文工程、局部编辑、Plan-Execute-Critic、回滚验证和性能指标阈值

#### Scenario: 长期阶段
- **WHEN** 项目进入长期迭代
- **THEN** 目标 SHALL 是接入 SWE-bench/Lite 或同类专业测试集、构建 ablation、做高级检索压缩和错误归因闭环

### Requirement: 阶段目标与交付物
系统 SHALL 为每个阶段设定目标里程碑、关键交付物、预期效果和可验证指标。

#### Scenario: 里程碑可验证
- **WHEN** 一个阶段完成
- **THEN** 开发者 SHALL 能通过测试命令、baseline 报告、评测报告或指标阈值判断是否达标

#### Scenario: 交付物可追踪
- **WHEN** 开发者回顾阶段进展
- **THEN** 每个阶段 SHALL 有明确文件、脚本、报告或模块作为交付物

### Requirement: 风险与瓶颈应对
系统 SHALL 识别潜在风险和瓶颈，并提供对应缓解策略。

#### Scenario: 风险驱动优先级
- **WHEN** 项目资源有限
- **THEN** 开发者 SHALL 优先处理会直接阻断高分测试集跑分的风险，而非低价值展示功能

#### Scenario: 预算与稳定性保护
- **WHEN** 运行批量评测
- **THEN** 系统 SHALL 有预算熔断、失败隔离、报告留存和可复现实验配置

## MODIFIED Requirements
### Requirement: 项目开发方式
项目后续开发 SHOULD 从“功能演示优先”调整为“评测驱动优先”：每个核心能力都需要绑定指标、回归集和 ablation，避免无法证明对专业测试集分数的贡献。

### Requirement: 评测指标
项目 SHOULD 把 `pass@1` 作为主指标，并同时跟踪单题成本、单题耗时、输入缓存命中率、输出 token、失败类型分布、回归集通过率。

## REMOVED Requirements
### Requirement: 非核心展示功能优先
**Reason**: Web UI、插件、多 Agent 协同、权限审计等功能短期内不能显著提升专业测试集分数，且会分散开发资源。
**Migration**: 在达到稳定专业测试集分数前，仅保留 CLI 和报告输出，把资源集中到检索、规划、验证、沙箱和评测。
