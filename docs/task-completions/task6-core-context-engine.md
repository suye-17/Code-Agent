# Task 6 完成文档：Core Context Engine MVP

## 任务目标

本任务根据 `docs/superpowers/plans/2026-05-22-enterprise-code-agent.md` 中未完成的 Phase 2/3，开始实现 Code Agent 的核心上下文能力。

原文档目标：

- Phase 2：C++ tree-sitter 索引器。
- Phase 3：BM25 + embedding + 调用图混合检索。

当前交付不是最终 C++ 版本，而是同接口的 Python MVP：

- `CodeIndexer`：用 Python `ast` 扫描代码并抽取符号。
- `ContextRetriever`：用文件名、符号名、源码 token overlap 做轻量检索。
- `SearchContext`：把检索能力暴露为 ReAct 工具 `search_context`。

这样做的原因是：当前仓库没有 `core/`、CMake、tree-sitter、pybind11 构建链路。先落地 Python MVP，可以立刻让 Agent 具备“先检索相关文件/符号，再读文件修复”的能力；后续再把 `CodeIndexer` 后端替换为 C++ tree-sitter。

## 实现思路

### 1. 建立稳定数据结构

新增 `agent/context/indexer.py`：

- `CodeSymbol`：表示函数、类、方法。
- `CodeFile`：表示一个 Python 文件及其符号列表。
- `CodeIndex`：表示整个代码库索引。

这些结构是后续替换底层索引器的边界。无论底层是 Python AST 还是 C++ tree-sitter，上层工具都只依赖这些结构。

### 2. Python AST 索引

`CodeIndexer.build(root)` 会：

- 遍历 `root/**/*.py`。
- 跳过 `.git`、`.venv`、`__pycache__`、build/cache 目录。
- 使用 `ast.parse()` 解析 Python 文件。
- 抽取顶层 function、class，以及 class 内 method。
- 保存符号名、类型、文件路径、起止行号和源码片段。

### 3. 轻量检索

新增 `agent/context/retriever.py`：

- 查询和代码都转成 token。
- 文件名命中加权最高。
- 符号名命中其次。
- 源码文本命中作为补充。
- 返回 `SearchResult`，包含路径、分数、命中原因、符号、snippet。

这不是最终 BM25/RRF，但已经具备真实代码库中定位相关文件的基础能力。

### 4. 工具接入

新增 `agent/tools/search.py`：

```python
SearchContext().run(path, query, top_k)
```

返回：

```python
{
    "query": "...",
    "root": "...",
    "results": [
        {
            "path": "...",
            "score": 12,
            "reason": "path:config, symbol:timeout",
            "snippet": "...",
            "symbols": [...]
        }
    ],
}
```

同时在 `ReActAgent` 默认工具中加入 `SearchContext()`，让 LLM 能通过 function calling 使用它。

## TDD 过程

### Red

先写 `tests/unit/test_context_engine.py`，验证：

- 能抽取 class、method、function。
- 能跳过 `.venv` 和 `__pycache__`。
- 查询 `timeout default config` 能定位 `config.py`。

首次运行失败：

```text
ModuleNotFoundError: No module named 'agent.context'
```

再写 `tests/unit/test_context_tool.py`，验证：

- `search_context` 返回排序结果。
- ReAct 默认工具包含 `search_context`。
- `search_context` 的 path 会被 ReAct 沙箱拦截。

首次运行失败：

```text
ModuleNotFoundError: No module named 'agent.tools.search'
```

### Green

实现：

- `agent/context/__init__.py`
- `agent/context/indexer.py`
- `agent/context/retriever.py`
- `agent/tools/search.py`
- 修改 `agent/orchestrator/react.py` 接入 `SearchContext`

目标测试通过：

```text
6 passed in 0.14s
```

## 核心代码说明

### `CodeIndexer`

```python
index = CodeIndexer().build(root)
```

返回 `CodeIndex`，上层可以直接使用：

- `index.files`
- `index.symbols`

### `ContextRetriever`

```python
results = ContextRetriever(index).search("timeout default config", top_k=5)
```

返回按分数排序的 `SearchResult`。`reason` 字段用于解释为什么命中，方便调试检索质量。

### `SearchContext`

`SearchContext` 是面向 Agent 的工具包装层。它隐藏索引和检索细节，只给 LLM 返回可读的路径、符号、代码片段。

## 与企业级计划文档的对应关系

| 企业级计划阶段 | 当前交付 | 后续升级 |
|---|---|---|
| Phase 2 C++ tree-sitter 索引器 | Python AST `CodeIndexer` | 替换为 C++/tree-sitter/SQLite |
| Phase 3 混合检索 | token overlap `ContextRetriever` | 增加 BM25、embedding、调用图、RRF |
| Tool Layer `search.py` | `SearchContext` 工具 | 接入持久化索引和压缩结果 |
| ReAct Phase 1 | 默认工具加入 `search_context` | 后续 Planner 节点优先调用检索 |

## 测试结果

### Context Engine 与工具测试

```bash
.venv/bin/python -m pytest tests/unit/test_context_engine.py tests/unit/test_context_tool.py -q
```

结果：

```text
6 passed in 0.14s
```

## 后续建议

下一步应该继续企业级计划核心路径，而不是继续扩 toy case：

1. 给 `search_context` 增加调用图启发式：从测试失败栈、import、函数调用关系扩大候选文件。
2. 实现 `compressor.py`：返回签名、相关函数、邻近上下文，而不是整文件 snippet。
3. 实现 `planner.py/executor.py/critic.py`：让 Agent 先检索、再计划、再编辑、最后验证回滚。
4. 再开始 C++ tree-sitter 后端，把 `CodeIndexer` 替换为高性能实现。
