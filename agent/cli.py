"""命令行入口。

用法：
    poetry run python -m agent.cli "fix the failing tests" --workdir /path/to/repo
"""
from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from agent.orchestrator.react import ReActAgent

app = typer.Typer(add_completion=False)


@app.command()
def run(
    task: str,
    workdir: Path = typer.Option(Path("."), "--workdir", "-w",
                                 help="Agent 工作目录"),
    max_steps: int = typer.Option(20, "--max-steps", help="步数预算上限"),
):
    """在指定 workdir 上运行 Agent 完成 task。"""
    # 仅在用户进程入口加载 .env，库代码本身不该有这种副作用
    load_dotenv()
    agent = ReActAgent(workdir=workdir, max_steps=max_steps)
    final = agent.run(task)
    typer.echo("\n=== AGENT FINAL ===")
    typer.echo(final)
    # 输出本次累计花销和缓存命中率，方便用户每跑一次就能看到反馈
    typer.echo(
        f"\nspent: ¥{agent.llm.spent:.4f}  "
        f"cache_hit_rate: {agent.llm.cache_hit_rate:.1%}"
    )


if __name__ == "__main__":
    app()
