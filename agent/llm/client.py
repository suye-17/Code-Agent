import json
import os
import time
import httpx
from pathlib import Path
from typing import Any


class BudgetExceeded(Exception):
    """当日 token 预算耗尽时抛出。"""


# DeepSeek-v4-flash 计价（2026-05，单位：人民币/token）
PRICE_IN_HIT = 0.02 / 1_000_000   # prompt 缓存命中部分
PRICE_IN_MISS = 1.0 / 1_000_000   # prompt 缓存未命中部分
PRICE_OUT = 2.0 / 1_000_000       # 输出 token


class LLMClient:
    """对 DeepSeek 兼容 OpenAI 格式的 chat 接口的轻量封装。

    特性：
      - 每日预算熔断（达到上限即抛 BudgetExceeded，硬阻断）
      - 三段计费分账（缓存命中 / 未命中 / 输出 各自累计）
      - 状态持久化：写入 JSON 文件，进程重启不丢；按本地日期跨日自动归零
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
        # 没有状态文件 / 跨日 / 文件损坏 → 全部按零状态返回
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
        # 每次请求结束都写盘，保证进程崩溃也不丢累计花销
        self.state_path.write_text(json.dumps({
            "date": self._today(),
            "cny": self.spent,
            "in_hit": self.in_hit,
            "in_miss": self.in_miss,
            "out": self.out_tok,
        }))

    @property
    def cache_hit_rate(self) -> float:
        # 命中率：命中 token / (命中 + 未命中)，无样本时返回 0
        total = self.in_hit + self.in_miss
        return self.in_hit / total if total else 0.0

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             model: str | None = None) -> dict[str, Any]:
        # 预算熔断：请求前检查，避免越界后才发现
        if self.spent >= self.budget:
            raise BudgetExceeded(
                f"已达每日预算 {self.budget} 元；当前累计 {self.spent:.4f}"
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

        # 三段计费：分别从 usage 字段拆出命中/未命中/输出
        u = data["usage"]
        hit = int(u.get("prompt_cache_hit_tokens", 0))
        # 部分 API 版本只返回 prompt_tokens，用减法兜底推导 miss
        miss = int(u.get("prompt_cache_miss_tokens",
                         u.get("prompt_tokens", 0) - hit))
        out = int(u["completion_tokens"])
        cost = hit * PRICE_IN_HIT + miss * PRICE_IN_MISS + out * PRICE_OUT

        # 累计 + 落盘（顺序不能颠倒，否则中途崩溃会丢这一次的统计）
        self.spent += cost
        self.in_hit += hit
        self.in_miss += miss
        self.out_tok += out
        self._save()
        return data
