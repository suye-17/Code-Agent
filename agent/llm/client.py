import json
import os
import time
import httpx
from pathlib import Path
from typing import Any


class BudgetExceeded(Exception):
    """Raised when the daily token budget has been hit."""


# DeepSeek-v4-flash pricing (2026-05, CNY per token)
PRICE_IN_HIT = 0.02 / 1_000_000
PRICE_IN_MISS = 1.0 / 1_000_000
PRICE_OUT = 2.0 / 1_000_000


class LLMClient:
    """Thin wrapper around DeepSeek's OpenAI-compatible chat endpoint with
    daily-budget circuit breaker and 3-tier (cache-hit / miss / output) accounting.

    State is persisted to a JSON file so spend survives process restarts and
    resets at the day boundary (local time).
    """

    def __init__(self, state_path: Path = Path("spend.json")):
        self.api_key = os.environ["DEEPSEEK_API_KEY"]
        self.base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.budget = float(os.environ.get("DAILY_BUDGET_CNY", "30"))
        self.state_path = Path(state_path)
        s = self._load()
        self.spent = s["cny"]
        self.in_hit = s["in_hit"]
        self.in_miss = s["in_miss"]
        self.out_tok = s["out"]

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _load(self) -> dict:
        empty = {"cny": 0.0, "in_hit": 0, "in_miss": 0, "out": 0}
        if not self.state_path.exists():
            return empty
        try:
            d = json.loads(self.state_path.read_text())
        except json.JSONDecodeError:
            return empty
        if d.get("date") != self._today():
            return empty
        return {
            "cny": float(d.get("cny", 0.0)),
            "in_hit": int(d.get("in_hit", 0)),
            "in_miss": int(d.get("in_miss", 0)),
            "out": int(d.get("out", 0)),
        }

    def _save(self) -> None:
        self.state_path.write_text(json.dumps({
            "date": self._today(),
            "cny": self.spent,
            "in_hit": self.in_hit,
            "in_miss": self.in_miss,
            "out": self.out_tok,
        }))

    @property
    def cache_hit_rate(self) -> float:
        total = self.in_hit + self.in_miss
        return self.in_hit / total if total else 0.0

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             model: str | None = None) -> dict[str, Any]:
        if self.spent >= self.budget:
            raise BudgetExceeded(
                f"daily budget {self.budget} CNY hit; spent {self.spent:.4f}"
            )
        payload: dict[str, Any] = {
            "model": model or os.environ.get("MODEL", "deepseek-v4-flash"),
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        with httpx.Client(timeout=120) as c:
            r = c.post(
                f"{self.base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()

        u = data["usage"]
        hit = int(u.get("prompt_cache_hit_tokens", 0))
        # Some API versions only return prompt_tokens; derive miss as fallback
        miss = int(u.get("prompt_cache_miss_tokens",
                         u.get("prompt_tokens", 0) - hit))
        out = int(u["completion_tokens"])
        cost = hit * PRICE_IN_HIT + miss * PRICE_IN_MISS + out * PRICE_OUT

        self.spent += cost
        self.in_hit += hit
        self.in_miss += miss
        self.out_tok += out
        self._save()
        return data
