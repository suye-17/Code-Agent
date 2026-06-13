from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .indexer import CodeFile, CodeIndex, CodeSymbol


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


@dataclass(frozen=True)
class SearchResult:
    path: Path
    score: float
    reason: str
    symbols: list[CodeSymbol]
    snippet: str


class ContextRetriever:
    """Lightweight lexical retriever for the first production-grade context loop."""

    def __init__(self, index: CodeIndex):
        self.index = index

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query_tokens = set(_tokens(query))
        scored: list[SearchResult] = []

        for code_file in self.index.files:
            score, reasons = self._score_file(code_file, query_tokens)
            if score <= 0:
                continue
            scored.append(
                SearchResult(
                    path=code_file.path,
                    score=score,
                    reason=", ".join(reasons),
                    symbols=code_file.symbols[:10],
                    snippet=self._snippet(code_file, query_tokens),
                )
            )

        return sorted(scored, key=lambda result: (-result.score, str(result.path)))[:top_k]

    def _score_file(self, code_file: CodeFile, query_tokens: set[str]) -> tuple[float, list[str]]:
        path_tokens = set(_tokens(code_file.path.stem))
        text_tokens = set(_tokens(code_file.text))
        symbol_tokens = set()
        for symbol in code_file.symbols:
            symbol_tokens.update(_tokens(symbol.name))

        score = 0.0
        reasons: list[str] = []

        path_hits = query_tokens & path_tokens
        if path_hits:
            score += 5 * len(path_hits)
            reasons.append(f"path:{','.join(sorted(path_hits))}")

        symbol_hits = query_tokens & symbol_tokens
        if symbol_hits:
            score += 3 * len(symbol_hits)
            reasons.append(f"symbol:{','.join(sorted(symbol_hits))}")

        text_hits = query_tokens & text_tokens
        if text_hits:
            score += len(text_hits)
            reasons.append(f"text:{','.join(sorted(text_hits))}")

        return score, reasons

    def _snippet(self, code_file: CodeFile, query_tokens: set[str], max_lines: int = 8) -> str:
        lines = code_file.text.splitlines()
        for index, line in enumerate(lines):
            if query_tokens & set(_tokens(line)):
                start = max(0, index - 2)
                end = min(len(lines), index + max_lines)
                return "\n".join(lines[start:end])
        return "\n".join(lines[:max_lines])


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text.replace("-", "_"))]
