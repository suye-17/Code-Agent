"""Phase 1 baseline 跑分脚本。

用当前的 ReActAgent 跑完整个 seed 回归集，输出 markdown 报告，
包含每个用例的通过情况、累计花销和缓存命中率。
这是 baseline B0：朴素 ReAct + 完整文件读取，无索引、无检索、无压缩。
后续每个 Phase 改完都重跑此脚本，得到消融曲线。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))   # 让 `import agent.*` 在脚本式运行时也能找到

from dotenv import load_dotenv  # noqa: E402

TOY_DIR = ROOT / "tests" / "toy_cases"
CASES_FILE = ROOT / "eval" / "regression_set" / "seed_cases.jsonl"
REPORTS_DIR = ROOT / "eval" / "reports"


def run_one(case: dict, work_root: Path) -> dict:
    """跑单个用例，返回该用例的通过/失败、耗时、花销增量。"""
    from agent.orchestrator.react import ReActAgent
    from agent.llm.client import LLMClient

    # 每次都从源目录拷贝一份，保证可复现且不污染 toy_case 源
    work = work_root / case["id"]
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(TOY_DIR / case["repo"], work)

    # LLMClient 读 spend.json 共享累计状态，所以先快照再用差值算"本用例增量"
    llm = LLMClient()
    spent_before = llm.spent
    hit_before = llm.in_hit
    miss_before = llm.in_miss
    out_before = llm.out_tok

    agent = ReActAgent(workdir=work, max_steps=20, llm=llm)
    t0 = time.time()
    try:
        agent.run(case["task"])
        agent_err = None
    except Exception as e:
        # 单条用例炸了不能炸整批，记录错误后继续
        agent_err = f"{type(e).__name__}: {e}"
    elapsed = time.time() - t0

    # 客观验证：用子进程跑 pytest，returncode == 0 才算修复成功
    r = subprocess.run(
        ["python", "-m", "pytest", "-x", "--tb=line", "-q"],
        cwd=work, capture_output=True, text=True, timeout=60,
    )

    return {
        "id":        case["id"],
        "passed":    r.returncode == 0 and agent_err is None,
        "elapsed_s": round(elapsed, 1),
        "spend_cny": round(llm.spent - spent_before, 6),
        "tokens_in_hit":  llm.in_hit - hit_before,
        "tokens_in_miss": llm.in_miss - miss_before,
        "tokens_out":     llm.out_tok - out_before,
        "agent_err":      agent_err,
        # pytest 输出的最后一行通常是 summary（"5 passed" / "FAILED ..."），信息密度最高
        "pytest_tail":    r.stdout.strip().splitlines()[-1] if r.stdout else "",
    }


def main() -> None:
    load_dotenv()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # 工作目录放 /tmp，跑完不污染 git 仓库
    work_root = Path("/tmp") / f"baseline_{int(time.time())}"
    work_root.mkdir(parents=True, exist_ok=True)

    cases = [json.loads(line) for line in CASES_FILE.read_text().splitlines() if line.strip()]
    rows = [run_one(c, work_root) for c in cases]

    # 汇总：通过率、总花销、整体缓存命中率
    passed = sum(r["passed"] for r in rows)
    total = len(rows)
    total_spend = sum(r["spend_cny"] for r in rows)
    total_hit = sum(r["tokens_in_hit"] for r in rows)
    total_miss = sum(r["tokens_in_miss"] for r in rows)
    hit_rate = total_hit / (total_hit + total_miss) if (total_hit + total_miss) else 0.0

    # 拼 markdown 报告：顶部总览 + 每用例一行的表格
    md = []
    md.append("# Phase 1 Baseline (B0): naive ReAct + full file reads\n")
    md.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ")
    md.append(f"**Cases:** {total}  ")
    md.append(f"**Pass rate:** {passed}/{total} = {passed/total:.0%}  ")
    md.append(f"**Total spend:** ¥{total_spend:.4f}  ")
    md.append(f"**Cache hit rate:** {hit_rate:.1%}\n")
    md.append("| id | pass | time(s) | spend (¥) | in_hit | in_miss | out | pytest tail |")
    md.append("|----|------|---------|-----------|--------|---------|-----|-------------|")
    for r in rows:
        mark = "✅" if r["passed"] else "❌"
        md.append(
            f"| {r['id']} | {mark} | {r['elapsed_s']} | {r['spend_cny']} | "
            f"{r['tokens_in_hit']} | {r['tokens_in_miss']} | {r['tokens_out']} | "
            f"`{r['pytest_tail'][:80]}` |"
        )
    # 如果有 Agent 异常，单独列一节方便排查
    if any(r["agent_err"] for r in rows):
        md.append("\n### Agent errors")
        for r in rows:
            if r["agent_err"]:
                md.append(f"- **{r['id']}**: {r['agent_err']}")

    report = "\n".join(md) + "\n"
    out_path = REPORTS_DIR / f"baseline_{time.strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(report)
    print(report)
    print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
