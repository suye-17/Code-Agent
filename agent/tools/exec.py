import subprocess

from .base import Tool


class RunShell(Tool):
    name = "run_shell"
    description = (
        "Run a shell command (bash). Returns dict with stdout/stderr/returncode. "
        "Hard timeout enforced. Returncode -1 means TIMEOUT."
    )
    parameters = {
        "type": "object",
        "properties": {
            "cmd": {"type": "string"},
            "timeout": {"type": "integer", "default": 60, "minimum": 1, "maximum": 600},
        },
        "required": ["cmd"],
    }

    def run(self, cmd: str, timeout: int = 60) -> dict:
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            )
            return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "TIMEOUT", "returncode": -1}
