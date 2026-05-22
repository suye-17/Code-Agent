import subprocess
from pathlib import Path

from .base import Tool


class ReadFile(Tool):
    name = "read_file"
    description = "Read a UTF-8 text file and return its full contents."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
        },
        "required": ["path"],
    }

    def run(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")


class WriteFile(Tool):
    name = "write_file"
    description = "Overwrite a UTF-8 text file with the given content. Creates parent dirs."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def run(self, path: str, content: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        n = p.write_text(content, encoding="utf-8")
        return f"wrote {n} bytes to {path}"


class ListDir(Tool):
    name = "list_dir"
    description = "List entries in a directory (one per line, dirs suffixed with /)."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def run(self, path: str) -> str:
        p = Path(path)
        if not p.is_dir():
            raise NotADirectoryError(path)
        lines = []
        for entry in sorted(p.iterdir()):
            lines.append(entry.name + ("/" if entry.is_dir() else ""))
        return "\n".join(lines)


class Grep(Tool):
    name = "grep"
    description = "Recursive ripgrep search. Returns matching lines with file:line prefixes."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["pattern", "path"],
    }

    def run(self, pattern: str, path: str) -> str:
        try:
            r = subprocess.run(
                ["rg", "-n", "--no-heading", pattern, path],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            # ripgrep not installed; fall back to grep
            r = subprocess.run(
                ["grep", "-rn", pattern, path],
                capture_output=True,
                text=True,
                timeout=30,
            )
        return r.stdout if r.stdout else "(no matches)"
