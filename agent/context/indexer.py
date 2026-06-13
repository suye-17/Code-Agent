from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


SKIP_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "build", "dist"}


@dataclass(frozen=True)
class CodeSymbol:
    name: str
    kind: str
    path: Path
    lineno: int
    end_lineno: int
    source: str


@dataclass(frozen=True)
class CodeFile:
    path: Path
    text: str
    symbols: list[CodeSymbol]


@dataclass(frozen=True)
class CodeIndex:
    root: Path
    files: list[CodeFile]
    symbols: list[CodeSymbol]


class CodeIndexer:
    """Python AST indexer MVP; later replaceable by tree-sitter backend."""

    def build(self, root: Path | str) -> CodeIndex:
        root_path = Path(root).resolve()
        files: list[CodeFile] = []
        all_symbols: list[CodeSymbol] = []

        for path in sorted(root_path.rglob("*.py")):
            if self._should_skip(path, root_path):
                continue
            text = path.read_text(encoding="utf-8")
            symbols = self._extract_symbols(path, text)
            files.append(CodeFile(path=path, text=text, symbols=symbols))
            all_symbols.extend(symbols)

        return CodeIndex(root=root_path, files=files, symbols=all_symbols)

    def _should_skip(self, path: Path, root: Path) -> bool:
        try:
            relative = path.relative_to(root)
        except ValueError:
            return True
        return any(part in SKIP_DIRS for part in relative.parts)

    def _extract_symbols(self, path: Path, text: str) -> list[CodeSymbol]:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []

        lines = text.splitlines()
        symbols: list[CodeSymbol] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                symbols.append(self._symbol(path, lines, node.name, "class", node))
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(
                            self._symbol(path, lines, f"{node.name}.{child.name}", "method", child)
                        )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._symbol(path, lines, node.name, "function", node))
        return symbols

    def _symbol(
        self,
        path: Path,
        lines: list[str],
        name: str,
        kind: str,
        node: ast.AST,
    ) -> CodeSymbol:
        lineno = getattr(node, "lineno", 1)
        end_lineno = getattr(node, "end_lineno", lineno)
        source = "\n".join(lines[lineno - 1:end_lineno])
        return CodeSymbol(
            name=name,
            kind=kind,
            path=path,
            lineno=lineno,
            end_lineno=end_lineno,
            source=source,
        )
