"""CLI entry point.

Usage:
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
                                 help="Working directory for the agent"),
    max_steps: int = typer.Option(20, "--max-steps", help="Hard step budget"),
):
    """Run the agent on a task in the given workdir."""
    load_dotenv()
    agent = ReActAgent(workdir=workdir, max_steps=max_steps)
    final = agent.run(task)
    typer.echo("\n=== AGENT FINAL ===")
    typer.echo(final)
    typer.echo(
        f"\nspent: ¥{agent.llm.spent:.4f}  "
        f"cache_hit_rate: {agent.llm.cache_hit_rate:.1%}"
    )


if __name__ == "__main__":
    app()
