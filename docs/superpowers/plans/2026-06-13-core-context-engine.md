# Core Context Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从企业级计划文档的 Phase 2/3 开始，实现一个可替换为 C++ tree-sitter 的 Python Context Engine MVP，让 Agent 能在真实代码库中定位相关文件和符号。

**Architecture:** 先用 Python AST 和轻量词法检索实现稳定接口：`CodeIndexer` 扫描 Python 文件并抽取函数/类符号，`ContextRetriever` 对查询做文件名、符号名、文本 token 评分，`SearchContext` 工具把检索结果暴露给 ReAct。后续可以在不改工具层和编排层的前提下，把 `CodeIndexer` 底层替换为 C++ tree-sitter/SQLite。

**Tech Stack:** Python 3.11、`ast`、`dataclasses`、pytest、现有 Tool/ReAct 架构。

---

## Task 1: Python Context Indexer MVP

**Files:**
- Create: `agent/context/__init__.py`
- Create: `agent/context/indexer.py`
- Test: `tests/unit/test_context_engine.py`

**交付:** 扫描仓库 Python 文件，抽取 `function`、`class`、`method` 符号、行号和源码片段。

**验证:** 单测创建临时代码库，确认能抽取函数、类、方法，并跳过 `.venv`、`__pycache__` 等目录。

## Task 2: Context Retriever MVP

**Files:**
- Create: `agent/context/retriever.py`
- Test: `tests/unit/test_context_engine.py`

**交付:** 根据自然语言查询返回 top-k 相关文件/符号，评分来源包括文件名、符号名和源码文本 token overlap。

**验证:** 单测查询 `timeout default config` 时，目标 `config.py` 排在 top-1 或 top-2。

## Task 3: SearchContext Tool

**Files:**
- Create: `agent/tools/search.py`
- Modify: `agent/orchestrator/react.py`
- Test: `tests/unit/test_context_tool.py`

**交付:** 新增 `search_context` 工具，接入 ReAct 默认工具集，返回结构化检索结果。

**验证:** 单测确认工具 schema、路径沙箱、检索结果字段，并确认 ReAct 默认工具包含 `search_context`。

## Task 4: Documentation and Verification

**Files:**
- Create: `docs/task-completions/task6-core-context-engine.md`

**交付:** 说明本任务如何对应企业级计划文档 Phase 2/3，以及为什么先做 Python MVP。

**验证:** 运行 `pytest` 和 `ruff`，提交并推送。
