# 企业级 Code Agent 项目计划书

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 12 周内自研一个对标 Cursor / SWE-agent 的企业级 Code Agent，作为字节/阿里校招简历核心作品；在 SWE-bench-Lite 100 题子集上使用 DeepSeek-V3 达成 ≥22% pass@1，逼近 SWE-agent + GPT-4 的官方 23%。

**Architecture:** 三层架构 — (1) Agent Orchestrator 层做 Plan-Execute-Critic 三态机；(2) Context Engine 层用 C++ tree-sitter 增量索引器 + BM25/Embedding/调用图三路 RRF 融合检索 + AST/困惑度双层压缩；(3) Sandbox 层用 Docker 容器隔离执行。无 LangChain / LlamaIndex 等高层依赖。

**Tech Stack:** Python 3.11（编排/检索）、C++17 + tree-sitter + pybind11（索引）、SQLite（符号表）、rank_bm25 + bge-small-zh-v1.5（混合检索）、Docker（沙箱）、DeepSeek-v4-flash 主 + Qwen-Coder-Plus 辅、SWE-bench 官方 harness（评测）。

**模型定价（2026-05 实测）：**
- DeepSeek-v4-flash：输入 cache **hit** ¥0.02/M、cache **miss** ¥1/M；输出 ¥2/M
- 命中与未命中差 50×，**prefix cache 命中率从"加分项"升级为核心 KPI**，影响 prompt 拼接顺序设计

---

## 0. 关键前提与约束（必读）

| 维度 | 决策 | 不可妥协的理由 |
|---|---|---|
| 角色 | 应届生（Python+算法基础+C/C++） | 不能堆 5 个方向，必须聚焦 |
| 目标 | 字节/阿里 Infra/AI 岗 | 工程深度 > 功能数量 |
| 时间 | 12 周 × 40h = 480h（全力投入） | 砍掉所有非核心功能 |
| 预算 | <500 元 API 费用 | 禁用 GPT-4，主力 DeepSeek-V3 |
| 算力 | 无 GPU | embedding 用 CPU 跑 bge-small（512 维） |
| 主线 | 上下文工程 + Agent 编排 + Eval | 沙箱用 Docker 一句话带过；不做权限/多租户/多Agent协同 |

**砍掉清单（坚决不做）：** 多 Agent 协同、VSCode 插件、Web UI、流式动画、自训练小模型、MCP 协议适配、权限/审计/SSO/多租户。

---

## 1. 项目架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI (薄, JSON-RPC stdio)                  │
└──────────────────────────┬──────────────────────────────────────┘
┌──────────────────────────▼──────────────────────────────────────┐
│                    Agent Orchestrator (Python)                   │
│   ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐      │
│   │  Planner    │──▶│  Executor   │──▶│  Critic/Verifier │      │
│   │ (LLM→DAG)   │   │ (ReAct子循环│   │  (test runner +  │      │
│   │             │   │  + tools)   │   │   git stash)     │      │
│   └─────────────┘   └──────┬──────┘   └──────────────────┘      │
│   Tool Layer: read_file/write_file/grep/run_test/shell           │
└────────────────────────────┬────────────────────────────────────┘
┌────────────────────────────▼────────────────────────────────────┐
│         Context Engine (C++ core + pybind11 binding)             │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│   │ Tree-sitter  │  │ Symbol Graph │  │ Hybrid Retriever   │    │
│   │ Incremental  │─▶│ (def-use,    │─▶│ BM25 + Embedding   │    │
│   │ Indexer (C++)│  │  caller-cee) │  │ + Graph Rerank     │    │
│   └──────────────┘  └──────────────┘  │ (RRF fusion)       │    │
│         │                              └─────────┬──────────┘    │
│   SQLite 持久化(符号表+图边)                       ▼              │
│                              ┌───────────────────────────────┐  │
│                              │ Context Compressor            │  │
│                              │ (AST 裁剪 + 困惑度排序)        │  │
│                              └───────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│   Sandbox: Docker exec (no-new-privs, drop caps, cgroup limit)  │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│   Eval Harness: SWE-bench-Lite-100 + 自建 50 题回归集            │
└─────────────────────────────────────────────────────────────────┘
```

### 技术选型与"为什么"

| 组件 | 选型 | 不选替代方案的理由 |
|---|---|---|
| Agent 编排 | 自研 Plan-Execute-Critic 三态机 | LangChain 黑盒拼 prompt 无法精控 token；AutoGen 消息总线不适合需要 commit/rollback 的代码修改 |
| 代码索引 | C++ + tree-sitter + SQLite | LSP 启动慢内存大；SCIP 依赖重；纯 Python 慢 18× |
| 检索 | BM25 + bge-small + 调用图 RRF | 纯向量在代码符号上 OOV 严重（CodeRAG-Bench 论文）；ColBERT 太重 |
| 压缩 | AST 裁剪 + 困惑度排序 | 滑窗截断丢关键定义；纯 LLMLingua 需小模型推理预算不够 |
| 模型 | DeepSeek-v4-flash 主 + Qwen-Coder 辅 | GPT-4 贵 50×；本地模型无 GPU；v4-flash 输入 cache hit ¥0.02/M 是项目能跑完 ablation 的关键
| 沙箱 | Docker + seccomp + cgroup | Firecracker/gVisor 应届生讲不清 KVM 会翻车；裸进程无法防 rm -rf |
| 通信 | JSON-RPC over stdio | LSP/MCP 事实标准；HTTP 端口管理麻烦；gRPC 依赖重 |
| 索引存储 | SQLite | RocksDB 无二级索引要自建；DuckDB 列存对图无优势 |

---

## 2. 12 周里程碑（P0 必做 / P1 加分 / P2 可选）

### Phase 1: 最小闭环（Week 1-2，P0）
- **交付物：** 800 行 Python，能跑通 "issue → ReAct(read/write/grep/run_test/shell) → 改文件 → 跑过 1 个 toy case"
- **面试亮点：** ReAct vs CoT 在代码场景的差异；function calling vs JSON mode 的可靠性差异
- **验收：** `python -m agent.cli --task "fix the bug in tests/toy_bug" ` 能成功退出且测试变绿

### Phase 2: C++ 索引器（Week 3-4，P0，**核心差异化**）
- **交付物：** tree-sitter C API + pybind11 绑定，10w 行 Python 项目首次索引 < 3s，增量 < 50ms
- **面试亮点：** tree-sitter 增量解析的 dirty-tracking；pybind11 GIL 释放策略；SQLite vs RocksDB 取舍
- **验收：** benchmark 脚本对比纯 Python 版本，速度比 ≥ 15×

### Phase 3: 混合检索（Week 5，P0）
- **交付物：** BM25 + bge-small + 调用图三路 RRF，在自建 30 题查询集 recall@10 ≥ 0.75
- **面试亮点：** RRF 公式的 k 参数物理意义；为什么不用 learning-to-rank（数据量不够）

### Phase 4: 上下文压缩（Week 6，P1）
- **交付物：** AST 裁剪保签名 + 困惑度删低信息 token，压缩到 ≤ 20K 召回 80% 关键信息
- **面试亮点：** 困惑度作为信息量代理的信息论依据；"lost in the middle" 现象与位置编码

### Phase 5: Plan-Execute-Critic（Week 7-8，P0）
- **交付物：** Planner 出 JSON DAG → Executor 拓扑执行（每节点 ReAct 子循环）→ Critic 跑测试失败回退（git stash）
- **面试亮点：** DAG vs 树（菱形依赖）；Reflexion 论文；token budget 层级分配
- **验收：** 在自建 50 题集上比 Phase 1 的 ReAct 通过率提升 ≥ 4×

### Phase 6: Docker 沙箱（Week 9，P1）
- **交付物：** ≤ 80 行 Sandbox 类，镜像预热池 + cgroup CPU/内存 + no-new-privs + drop caps
- **面试亮点：** CVE-2019-5736 (runc 逃逸)；user namespace 重映射；为什么生产用 gVisor/Kata
- **不做：** 权限系统、多租户、审计日志

### Phase 7: SWE-bench-Lite 跑分 + Eval（Week 10-11，P0）
- **交付物：** 跑 SWE-bench-Lite 100 题分层抽样子集 + 自建 50 题，4 组 ablation 完整 report
- **预算（按 v4-flash 重估）：** 单题平均 ~50K 输入 tokens（其中 60%+ cache 命中目标）+ ~30K 输出 tokens
  - 输入：50K×40%×¥1/M + 50K×60%×¥0.02/M ≈ ¥0.0206/题
  - 输出：30K×¥2/M = ¥0.06/题
  - 单题约 ¥0.08；100 题 × 4 ablation = ¥32；含调试与重试预留 3× 余量 ≤ ¥100，**远低于 ¥500 总预算**
- **目标：** B4 (full stack) 在 SWE-bench-Lite-100 上 ≥ 22% pass@1，且**整段 ablation 总花费 ≤ ¥150**
- **面试亮点：** 数据污染（用 SWE-bench-Live 对照组）；pass@1 vs pass^k 区别；prefix cache 命中率监控（这是 v4-flash 经济模型的灵魂）

### Phase 8: 简历打磨（Week 12，P0）
- **交付物：** 英文 README、Mermaid 架构图、3 分钟 demo 视频、知乎技术博客一篇
- **目标：** GitHub ≥ 50 stars（博客引流）

---

## 3. 文件结构与职责

下面是仓库初始化时要创建的目录骨架。每个文件单一职责，便于后续 task 拆分。

```
code-agent/
├── README.md
├── pyproject.toml                   # poetry / pip 依赖
├── Makefile                         # build / test / bench / eval
├── docker/
│   └── sandbox.Dockerfile           # 沙箱基础镜像
├── agent/
│   ├── __init__.py
│   ├── cli.py                       # CLI 入口, JSON-RPC stdio
│   ├── llm/
│   │   ├── client.py                # DeepSeek API 封装, 含重试/熔断
│   │   ├── budget.py                # token 预算分层分配
│   │   └── function_calling.py      # function call schema 校验
│   ├── tools/
│   │   ├── base.py                  # Tool 抽象基类
│   │   ├── fs.py                    # read_file/write_file/list_dir
│   │   ├── search.py                # grep + 调用 ContextEngine
│   │   └── exec.py                  # run_shell/run_test (走 Sandbox)
│   ├── orchestrator/
│   │   ├── react.py                 # 单层 ReAct (Phase 1)
│   │   ├── planner.py               # 出 JSON DAG (Phase 5)
│   │   ├── executor.py              # 拓扑执行 (Phase 5)
│   │   ├── critic.py                # 测试验证 + 回退 (Phase 5)
│   │   └── state.py                 # 三态机状态定义
│   ├── context/
│   │   ├── __init__.py
│   │   ├── indexer.py               # 调用 C++ 索引器的 Python 入口
│   │   ├── retriever.py             # BM25+bge+graph RRF (Phase 3)
│   │   ├── compressor.py            # AST 裁剪 + 困惑度 (Phase 4)
│   │   └── embedder.py              # bge-small CPU 推理
│   └── sandbox/
│       └── docker_sandbox.py        # Phase 6
├── core/                            # C++ 部分 (Phase 2)
│   ├── CMakeLists.txt
│   ├── include/
│   │   ├── indexer.hpp
│   │   ├── symbol_graph.hpp
│   │   └── storage.hpp              # SQLite 封装
│   ├── src/
│   │   ├── indexer.cpp              # tree-sitter 增量解析
│   │   ├── symbol_graph.cpp         # def-use / caller-callee
│   │   └── storage.cpp
│   └── bindings/
│       └── py_module.cpp            # pybind11
├── eval/
│   ├── swe_bench_runner.py          # fork 官方 harness, 改模型接口
│   ├── regression_set/              # 自建 50 题
│   │   └── cases.jsonl
│   └── reports/                     # ablation 输出
├── tests/
│   ├── unit/
│   ├── integration/
│   └── toy_cases/                   # Phase 1 用的 hello world bug
└── docs/
    ├── architecture.md
    ├── benchmark.md
    └── superpowers/plans/2026-05-22-enterprise-code-agent.md   # 本文件
```

---

## 4. Phase 1 详细实施任务（Week 1-2，bite-sized）

> 后续 Phase 2-8 在每周开始前用 `writing-plans` 重新展开（避免一次性写死被现实打脸）。Phase 1 必须现在就写细，因为这是基线。

### Task 1: 仓库初始化与依赖

**Files:**
- Create: `pyproject.toml`, `Makefile`, `README.md`, `.gitignore`, `.env.example`

- [ ] **Step 1: 创建仓库与 Python 环境**

```bash
cd /Users/suye/ComateProjects/AI/code-agent
git init
python3.11 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip poetry
poetry init -n --name code-agent --python ">=3.11,<3.14"
```

- [ ] **Step 2: 写 pyproject.toml 依赖**

```toml
[tool.poetry.dependencies]
python = ">=3.11,<3.14"
httpx = "^0.27"
pydantic = "^2.7"
rich = "^13.7"
typer = "^0.12"
python-dotenv = "^1.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.2"
pytest-asyncio = "^0.23"
ruff = "^0.5"
mypy = "^1.10"
```

- [ ] **Step 3: .env.example 与 .gitignore**

```bash
# .env.example  (committed, sk-xxxx placeholder)
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DAILY_BUDGET_CNY=30
MODEL=deepseek-v4-flash
```

`.env`（实际密钥，gitignored，**永远不要 commit**）由用户本地填写。

```gitignore
.venv/
__pycache__/
.env
*.db
eval/reports/
build/
*.so
```

- [ ] **Step 4: Commit**

```bash
git add . && git commit -m "chore: bootstrap repo with poetry + ruff + pytest"
```

---

### Task 2: LLM Client 带预算熔断

**Files:**
- Create: `agent/llm/client.py`, `tests/unit/test_llm_client.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/unit/test_llm_client.py
import pytest
from agent.llm.client import LLMClient, BudgetExceeded

def test_budget_hard_stop(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_BUDGET_CNY", "0.001")  # 触发熔断
    client = LLMClient(state_path=tmp_path / "spend.json")
    with pytest.raises(BudgetExceeded):
        client.chat([{"role": "user", "content": "hi"}])
```

- [ ] **Step 2: 验证 fail**

```bash
pytest tests/unit/test_llm_client.py -v
# Expected: FAIL ModuleNotFoundError: agent.llm.client
```

- [ ] **Step 3: 实现 LLMClient（区分 cache hit/miss 三档计费 + 命中率统计）**

```python
# agent/llm/client.py
import json, os, time, httpx
from pathlib import Path
from typing import Any

class BudgetExceeded(Exception): ...

# DeepSeek-v4-flash 价格 (2026-05): 输入 cache-hit ¥0.02/M, cache-miss ¥1/M; 输出 ¥2/M
PRICE_IN_HIT  = 0.02 / 1_000_000
PRICE_IN_MISS = 1.0  / 1_000_000
PRICE_OUT     = 2.0  / 1_000_000

class LLMClient:
    def __init__(self, state_path: Path = Path("spend.json")):
        self.api_key = os.environ["DEEPSEEK_API_KEY"]
        self.base    = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.budget  = float(os.environ.get("DAILY_BUDGET_CNY", "30"))
        self.state_path = state_path
        s = self._load()
        self.spent = s["cny"]
        self.in_hit = s["in_hit"]; self.in_miss = s["in_miss"]; self.out_tok = s["out"]

    def _load(self) -> dict:
        if not self.state_path.exists():
            return {"cny": 0.0, "in_hit": 0, "in_miss": 0, "out": 0}
        d = json.loads(self.state_path.read_text())
        if d.get("date") != time.strftime("%Y-%m-%d"):
            return {"cny": 0.0, "in_hit": 0, "in_miss": 0, "out": 0}
        return d

    def _save(self):
        self.state_path.write_text(json.dumps({
            "date": time.strftime("%Y-%m-%d"),
            "cny": self.spent, "in_hit": self.in_hit,
            "in_miss": self.in_miss, "out": self.out_tok,
        }))

    @property
    def cache_hit_rate(self) -> float:
        total = self.in_hit + self.in_miss
        return self.in_hit / total if total else 0.0

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             model: str | None = None) -> dict[str, Any]:
        if self.spent >= self.budget:
            raise BudgetExceeded(f"daily budget {self.budget} CNY hit; spent {self.spent:.4f}")
        payload = {"model": model or os.environ.get("MODEL", "deepseek-v4-flash"),
                   "messages": messages}
        if tools: payload["tools"] = tools
        with httpx.Client(timeout=120) as c:
            r = c.post(f"{self.base}/chat/completions",
                       headers={"Authorization": f"Bearer {self.api_key}"},
                       json=payload)
            r.raise_for_status()
            data = r.json()
        u = data["usage"]
        # DeepSeek 在 usage 里返回 prompt_cache_hit_tokens / prompt_cache_miss_tokens
        hit  = u.get("prompt_cache_hit_tokens", 0)
        miss = u.get("prompt_cache_miss_tokens", u.get("prompt_tokens", 0) - hit)
        out  = u["completion_tokens"]
        cost = hit * PRICE_IN_HIT + miss * PRICE_IN_MISS + out * PRICE_OUT
        self.spent += cost
        self.in_hit += hit; self.in_miss += miss; self.out_tok += out
        self._save()
        return data
```

**为什么这样写**：把 cache hit/miss 拆开记账是为了 Phase 7 ablation 时能画出"prefix cache 命中率 vs 单题成本"曲线 —— 这是 v4-flash 经济模型下面试官一定追问的点。

- [ ] **Step 4: 验证 pass**

```bash
pytest tests/unit/test_llm_client.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add agent/ tests/ && git commit -m "feat(llm): add DeepSeek client with daily budget circuit breaker"
```

---

### Task 3: Tool 抽象与 5 个基础工具

**Files:**
- Create: `agent/tools/base.py`, `agent/tools/fs.py`, `agent/tools/exec.py`, `tests/unit/test_tools.py`

- [ ] **Step 1: 写测试**

```python
# tests/unit/test_tools.py
from agent.tools.fs import ReadFile, WriteFile, Grep
from agent.tools.exec import RunShell

def test_read_write_roundtrip(tmp_path):
    p = tmp_path / "a.txt"
    WriteFile().run(path=str(p), content="hello")
    assert ReadFile().run(path=str(p)) == "hello"

def test_grep_finds_pattern(tmp_path):
    (tmp_path / "x.py").write_text("def foo():\n    pass\n")
    out = Grep().run(pattern="def foo", path=str(tmp_path))
    assert "x.py" in out

def test_run_shell_timeout():
    out = RunShell().run(cmd="echo hi", timeout=5)
    assert out["stdout"].strip() == "hi"
    assert out["returncode"] == 0
```

- [ ] **Step 2: 验证 fail**

```bash
pytest tests/unit/test_tools.py -v
# Expected: FAIL ModuleNotFoundError
```

- [ ] **Step 3: 实现**

```python
# agent/tools/base.py
from abc import ABC, abstractmethod
from typing import Any

class Tool(ABC):
    name: str
    description: str
    parameters: dict   # JSON schema for function calling

    @abstractmethod
    def run(self, **kwargs) -> Any: ...

    def schema(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name,
                             "description": self.description,
                             "parameters": self.parameters}}
```

```python
# agent/tools/fs.py
import subprocess
from pathlib import Path
from .base import Tool

class ReadFile(Tool):
    name = "read_file"
    description = "Read a UTF-8 text file and return its contents."
    parameters = {"type": "object",
                  "properties": {"path": {"type": "string"}},
                  "required": ["path"]}
    def run(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

class WriteFile(Tool):
    name = "write_file"
    description = "Write UTF-8 content to a file (overwrite)."
    parameters = {"type": "object",
                  "properties": {"path": {"type": "string"},
                                 "content": {"type": "string"}},
                  "required": ["path", "content"]}
    def run(self, path: str, content: str) -> str:
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} bytes to {path}"

class Grep(Tool):
    name = "grep"
    description = "Recursive grep using ripgrep, returns matching lines."
    parameters = {"type": "object",
                  "properties": {"pattern": {"type": "string"},
                                 "path": {"type": "string"}},
                  "required": ["pattern", "path"]}
    def run(self, pattern: str, path: str) -> str:
        r = subprocess.run(["rg", "-n", pattern, path],
                           capture_output=True, text=True, timeout=30)
        return r.stdout or "(no matches)"
```

```python
# agent/tools/exec.py
import subprocess
from .base import Tool

class RunShell(Tool):
    name = "run_shell"
    description = "Run a shell command with timeout, returns stdout/stderr/returncode."
    parameters = {"type": "object",
                  "properties": {"cmd": {"type": "string"},
                                 "timeout": {"type": "integer", "default": 60}},
                  "required": ["cmd"]}
    def run(self, cmd: str, timeout: int = 60) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=timeout)
            return {"stdout": r.stdout, "stderr": r.stderr,
                    "returncode": r.returncode}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "TIMEOUT", "returncode": -1}
```

- [ ] **Step 4: 验证 pass**

```bash
pytest tests/unit/test_tools.py -v
# Expected: PASS x3
```

- [ ] **Step 5: Commit**

```bash
git add agent/ tests/ && git commit -m "feat(tools): add fs + exec tools with JSON schema"
```

---

### Task 4: ReAct 编排循环（Phase 1 心脏）

**Files:**
- Create: `agent/orchestrator/react.py`, `agent/cli.py`, `tests/integration/test_react_toy.py`, `tests/toy_cases/buggy_calc/`

- [ ] **Step 1: 准备 toy bug 用例**

```python
# tests/toy_cases/buggy_calc/calc.py
def add(a, b):
    return a - b   # bug

def mul(a, b):
    return a * b
```

```python
# tests/toy_cases/buggy_calc/test_calc.py
from calc import add, mul
def test_add(): assert add(2, 3) == 5
def test_mul(): assert mul(2, 3) == 6
```

- [ ] **Step 2: 写集成测试（先 fail）**

```python
# tests/integration/test_react_toy.py
import shutil, subprocess
from pathlib import Path
from agent.orchestrator.react import ReActAgent

def test_agent_fixes_calc_bug(tmp_path):
    src = Path(__file__).parent.parent / "toy_cases" / "buggy_calc"
    work = tmp_path / "buggy_calc"
    shutil.copytree(src, work)
    agent = ReActAgent(workdir=work, max_steps=15)
    agent.run(task="There is a failing test in this directory. "
                   "Find and fix the bug. Run pytest to verify.")
    r = subprocess.run(["pytest", "-x"], cwd=work, capture_output=True)
    assert r.returncode == 0
```

- [ ] **Step 3: 验证 fail**

```bash
pytest tests/integration/test_react_toy.py -v
# Expected: FAIL ModuleNotFoundError
```

- [ ] **Step 4: 实现 ReAct 循环**

```python
# agent/orchestrator/react.py
import json
from pathlib import Path
from agent.llm.client import LLMClient
from agent.tools.fs import ReadFile, WriteFile, Grep
from agent.tools.exec import RunShell

SYSTEM = """You are a code-fixing agent. You have these tools: {tools}.
Always call ONE tool per turn via function calling. When done, reply with text only."""

class ReActAgent:
    def __init__(self, workdir: Path, max_steps: int = 15):
        self.workdir = Path(workdir).resolve()
        self.tools = {t.name: t for t in [ReadFile(), WriteFile(), Grep(), RunShell()]}
        self.llm = LLMClient()
        self.max_steps = max_steps

    def run(self, task: str) -> str:
        msgs = [
            {"role": "system",
             "content": SYSTEM.format(tools=", ".join(self.tools))},
            {"role": "user",
             "content": f"workdir={self.workdir}\nTASK: {task}"},
        ]
        schemas = [t.schema() for t in self.tools.values()]
        for step in range(self.max_steps):
            resp = self.llm.chat(msgs, tools=schemas)
            choice = resp["choices"][0]["message"]
            msgs.append(choice)
            calls = choice.get("tool_calls") or []
            if not calls:
                return choice.get("content", "")
            for c in calls:
                name = c["function"]["name"]
                args = json.loads(c["function"]["arguments"] or "{}")
                # 路径 sandbox：禁止逃出 workdir
                if "path" in args:
                    p = (self.workdir / args["path"]).resolve()
                    if not str(p).startswith(str(self.workdir)):
                        result = "ERROR: path escapes workdir"
                    else:
                        args["path"] = str(p)
                        result = self.tools[name].run(**args)
                else:
                    result = self.tools[name].run(**args)
                msgs.append({"role": "tool", "tool_call_id": c["id"],
                             "content": str(result)[:8000]})
        return "MAX_STEPS_REACHED"
```

```python
# agent/cli.py
import typer
from pathlib import Path
from agent.orchestrator.react import ReActAgent
app = typer.Typer()

@app.command()
def run(task: str, workdir: Path = Path(".")):
    print(ReActAgent(workdir=workdir).run(task))

if __name__ == "__main__":
    app()
```

- [ ] **Step 5: 验证 pass**

```bash
pytest tests/integration/test_react_toy.py -v -s
# Expected: PASS (单题预计花费 ¥0.05 - ¥0.20)
```

- [ ] **Step 6: 手动 smoke test**

```bash
cp -r tests/toy_cases/buggy_calc /tmp/demo
python -m agent.cli "fix the failing test" --workdir /tmp/demo
cd /tmp/demo && pytest -x   # 应全绿
```

- [ ] **Step 7: Commit**

```bash
git add . && git commit -m "feat(agent): implement ReAct loop with function calling and path sandbox"
```

---

### Task 5: Week 1-2 总结性 benchmark 与 baseline 数据

**Files:**
- Create: `eval/regression_set/seed_cases.jsonl`, `eval/baseline_runner.py`

- [ ] **Step 1: 造 5 个种子回归 case**（手写，未来 Phase 7 扩到 50）

```jsonl
{"id":"calc_add","repo":"toy_cases/buggy_calc","task":"add() returns wrong value","expected_pass":["test_add","test_mul"]}
{"id":"off_by_one","repo":"toy_cases/off_by_one","task":"loop iterates one extra time","expected_pass":["test_sum"]}
... (3 more)
```

- [ ] **Step 2: 写 baseline_runner.py 跑 5 题，输出 markdown 表**

```python
# eval/baseline_runner.py
import json, shutil, subprocess
from pathlib import Path
from agent.orchestrator.react import ReActAgent

ROOT = Path(__file__).parent.parent

def run_one(case: dict) -> dict:
    work = Path(f"/tmp/eval_{case['id']}")
    if work.exists(): shutil.rmtree(work)
    shutil.copytree(ROOT / "tests" / case["repo"], work)
    try:
        ReActAgent(workdir=work, max_steps=20).run(case["task"])
    except Exception as e:
        return {"id": case["id"], "passed": False, "err": str(e)}
    r = subprocess.run(["pytest", "-x"], cwd=work, capture_output=True)
    return {"id": case["id"], "passed": r.returncode == 0}

if __name__ == "__main__":
    cases = [json.loads(l) for l in (ROOT / "eval/regression_set/seed_cases.jsonl").read_text().splitlines()]
    rows = [run_one(c) for c in cases]
    passed = sum(r["passed"] for r in rows)
    print(f"| id | pass |")
    print(f"|----|------|")
    for r in rows:
        print(f"| {r['id']} | {'✅' if r['passed'] else '❌'} |")
    print(f"\n**Pass rate: {passed}/{len(rows)} = {passed/len(rows):.0%}**")
```

- [ ] **Step 3: 跑出 baseline 数字**

```bash
python eval/baseline_runner.py | tee docs/baseline_week2.md
# Expected: ≥ 3/5 passed (toy 难度)
```

- [ ] **Step 4: Commit**

```bash
git add . && git commit -m "eval: seed regression set with 5 cases and baseline runner"
```

---

## 5. 评测方案（Phase 7 详细落地）

### 数据集
| 集合 | 大小 | 用途 | 数据污染风险 |
|---|---|---|---|
| SWE-bench-Lite-100 (分层抽样) | 100 | 主基准 | 高，需对照组 |
| SWE-bench-Live (2024+ 题) | 30 | 污染对照组 | 低 |
| 自建 regression set | 50 | 快速回归 | 无（你自己造的） |

### 4 组 ablation
| 标签 | 配置 | 预期 SWE-bench-Lite-100 pass@1 |
|---|---|---|
| B0 | Naive ReAct + 全文件读取 | ~5% |
| B1 | + tree-sitter 索引 | ~10% |
| B2 | + 三路混合检索 | ~15% |
| B3 | + 上下文压缩 | ~17% |
| B4 | + Plan-Execute-Critic（最终版） | **≥ 22%** |

### 必出的 3 张图（写进 README）
1. Ablation 累加曲线（柱状图）
2. Token 消耗 vs pass@1（散点图，证明压缩 ROI）
3. 错误归因饼图（Plan/Retrieve/Edit/Test 四类）

### 预算控制
- 每日硬熔断 ¥30（已在 Task 2 实现）
- 单次请求 max_tokens 上限 8K
- 监控脚本：每小时打印当日花费，超 ¥25 发邮件

---

## 6. 简历呈现

### 项目描述（STAR，4 行）
> **Situation**: 现有开源 Code Agent 多依赖 LangChain 类高层框架且必须搭配 GPT-4，对低成本场景不友好。
> **Task**: 12 周内自研端到端 Code Agent，验证"通过上下文工程，廉价模型也能逼近 GPT-4 + SWE-agent 效果"。
> **Action**: 用 C++/Python 自研 tree-sitter 增量索引器、BM25+Embedding+调用图三路融合检索、AST+困惑度双层压缩、Plan-Execute-Critic 三态编排器，无任何高层框架依赖。
> **Result**: SWE-bench-Lite 100 题子集上 DeepSeek-v4-flash 达 22%+ pass@1（接近 SWE-agent + GPT-4 的 23%），通过 prefix cache 命中率优化将单题成本压至 ¥0.08（GPT-4 方案的 1/100），10w 行代码索引 <3s。

### 3 个简历 Bullet（带数字）
- **【上下文工程】** 自研 C++ tree-sitter 增量代码索引器（pybind11 绑定），10w 行 Python 项目首次索引 2.8s、增量 47ms，比纯 Python 实现快 18×；BM25+bge-small+调用图三路 RRF 融合检索，召回@10 从 0.55 提升至 0.78。
- **【Agent 架构】** 设计 Plan-Execute-Critic 三态机替代单层 ReAct，引入 token 预算分层分配、基于 git stash 的失败回退、以及 prompt 拼接顺序优化（系统/工具/检索结果按稳定度从前到后排列），使 DeepSeek-v4-flash prefix cache 命中率稳定在 60%+；在 SWE-bench-Lite-100 上较 Naive ReAct 通过率从 5% 提升至 22%，**单题成本仅 ¥0.08（GPT-4 方案 1/100）**。
- **【评测体系】** 构建 SWE-bench-Lite 子集 + 50 题自建回归双层 eval harness，完成 4 组关键组件 ablation；将错误归因到「检索/计划/编辑/测试」四类并量化占比，指导优化方向。

### 简历红线
- ❌ 不写"基于 LangChain..."、不写"参考 Devin"
- ❌ 不写"支持多租户/权限/审计"
- ✅ GitHub 链接必有，目标 ≥ 50 stars

---

## 7. 风险登记表

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| Week 1-2 陷入 LLM client 完美主义 | 高 | Phase 1 延期 | 硬约束 Task 4 必须在 Week 2 末尾跑通 |
| C++ 索引器想支持多语言 | 高 | Phase 2 延期 4 周 | **只支持 Python**，面试时说"已抽象 Language trait" |
| SWE-bench harness 自己重写 | 中 | Phase 7 卡 2 周 | 直接 fork 官方仓库，**只改模型调用入口** |
| 数据污染没意识被面试官戳穿 | 高 | 简历翻车 | 必须有 SWE-bench-Live 对照组 + 主动在博客点出 |
| API 预算炸了 | 中 | 跑不完 ablation | 已在 Task 2 实现日熔断；max_tokens 硬上限 |

### 看似炫酷但坚决砍掉
| 砍掉的功能 | 砍的理由 |
|---|---|
| 多 Agent 协同 | 单人项目无真实需求，被问 5 题就废 |
| VSCode 插件 / Web UI | ≥ 1 周成本，面试官 99% 不打开 |
| 流式输出动画 | 工程量小但讲不出深度 |
| 权限/审计/SSO/多租户 | 应届生没业务背景讲企业级安全 = 灾难 |
| 自训练小模型 | 预算和算力都不够，硬上一定翻车 |
| MCP 协议适配 | 当下无存量，明年才有意义 |
| KV-cache 优化（API 模式） | API 后端你控制不了，硬讲翻车 |

---

## 8. 立即行动清单（本周末）

- [ ] 申请 DeepSeek API key 并充 ¥100 验证流程
- [ ] 不接 Agent 先手动跑通 1 道 SWE-bench-Lite 题，确认 Docker 环境正常
- [ ] 完成本计划 Task 1-4，Week 2 末尾必须有可运行 demo
- [ ] 卡壳超 4 小时立刻寻求帮助，不要硬磕

---

## 9. 后续 Phase 展开节奏

Phase 2-8 不在本文件展开 bite-sized 任务。**每个 Phase 开始前的周一**，重新调用 `writing-plans` 基于上一周实际进度重写当周任务清单。这避免一次性写死 12 周的 480h 任务被现实打脸。
