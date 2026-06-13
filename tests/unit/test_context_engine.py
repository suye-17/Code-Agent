from __future__ import annotations

from agent.context.indexer import CodeIndexer
from agent.context.retriever import ContextRetriever


def test_code_indexer_extracts_python_symbols(tmp_path):
    (tmp_path / "service.py").write_text(
        "class UserService:\n"
        "    def get_user(self, user_id):\n"
        "        return user_id\n\n"
        "def normalize_name(name):\n"
        "    return name.strip().lower()\n"
    )

    index = CodeIndexer().build(tmp_path)

    symbols = {(s.kind, s.name, s.path.name) for s in index.symbols}
    assert ("class", "UserService", "service.py") in symbols
    assert ("method", "UserService.get_user", "service.py") in symbols
    assert ("function", "normalize_name", "service.py") in symbols
    assert index.files[0].path.name == "service.py"
    assert "normalize_name" in index.files[0].text


def test_code_indexer_skips_virtualenv_and_cache_dirs(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("def ignored():\n    pass\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text("def cached():\n    pass\n")
    (tmp_path / "real.py").write_text("def real():\n    pass\n")

    index = CodeIndexer().build(tmp_path)

    assert [file.path.name for file in index.files] == ["real.py"]
    assert [symbol.name for symbol in index.symbols] == ["real"]


def test_context_retriever_ranks_relevant_file_for_query(tmp_path):
    (tmp_path / "config.py").write_text(
        "DEFAULT_TIMEOUT = 30\n\n"
        "def get_timeout(settings):\n"
        "    return settings.get('timeout', DEFAULT_TIMEOUT)\n"
    )
    (tmp_path / "math_utils.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    index = CodeIndexer().build(tmp_path)
    results = ContextRetriever(index).search("timeout default config", top_k=2)

    assert results[0].path.name == "config.py"
    assert [result.path.name for result in results] == ["config.py"]
    assert any(symbol.name == "get_timeout" for symbol in results[0].symbols)
