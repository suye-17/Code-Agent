from __future__ import annotations

import subprocess
import sys
import time

from .base import Tool


def _tail(text: str, max_chars: int) -> str:
    """保留输出尾部；pytest summary 通常在最后，信息密度最高。"""
    if max_chars <= 0:
        return ""
    return text[-max_chars:]


class RunTest(Tool):
    name = "run_test"
    description = (
        "Run pytest for a file or directory. Returns passed, returncode, "
        "stdout_tail, stderr_tail, elapsed_s and timed_out."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "timeout": {"type": "integer", "default": 60, "minimum": 1, "maximum": 600},
            "max_output_chars": {
                "type": "integer",
                "default": 4000,
                "minimum": 200,
                "maximum": 20000,
            },
        },
        "required": ["path"],
    }

    def run(self, path: str = ".", timeout: int = 60, max_output_chars: int = 4000) -> dict:
        started = time.time()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = round(time.time() - started, 3)
            return {
                "passed": result.returncode == 0,
                "returncode": result.returncode,
                "stdout_tail": _tail(result.stdout, max_output_chars),
                "stderr_tail": _tail(result.stderr, max_output_chars),
                "elapsed_s": elapsed,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            elapsed = round(time.time() - started, 3)
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            return {
                "passed": False,
                "returncode": -1,
                "stdout_tail": _tail(stdout, max_output_chars),
                "stderr_tail": _tail(f"{stderr}\nTIMEOUT after {timeout}s", max_output_chars),
                "elapsed_s": elapsed,
                "timed_out": True,
            }
