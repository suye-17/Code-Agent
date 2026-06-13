from __future__ import annotations

from agent.context import CodeIndexer, ContextRetriever

from .base import Tool


class SearchContext(Tool):
    name = "search_context"
    description = (
        "Index a Python codebase and return ranked files, symbols and snippets "
        "relevant to a natural-language bug or task query."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
        },
        "required": ["path", "query"],
    }

    def run(self, path: str, query: str, top_k: int = 5) -> dict:
        index = CodeIndexer().build(path)
        results = ContextRetriever(index).search(query=query, top_k=top_k)
        return {
            "query": query,
            "root": str(index.root),
            "results": [
                {
                    "path": str(result.path),
                    "score": result.score,
                    "reason": result.reason,
                    "snippet": result.snippet,
                    "symbols": [
                        {
                            "name": symbol.name,
                            "kind": symbol.kind,
                            "lineno": symbol.lineno,
                            "end_lineno": symbol.end_lineno,
                        }
                        for symbol in result.symbols
                    ],
                }
                for result in results
            ],
        }
