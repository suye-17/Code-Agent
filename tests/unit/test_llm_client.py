import json
import pytest
from unittest.mock import patch, MagicMock
from agent.llm.client import LLMClient, BudgetExceeded


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DAILY_BUDGET_CNY", "1.0")
    monkeypatch.setenv("MODEL", "deepseek-v4-flash")
    return tmp_path


def _mock_response(in_hit=0, in_miss=100, out=50, content="hi"):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json = MagicMock(return_value={
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_cache_hit_tokens": in_hit,
            "prompt_cache_miss_tokens": in_miss,
            "prompt_tokens": in_hit + in_miss,
            "completion_tokens": out,
        },
    })
    return m


def test_budget_hard_stop_when_already_spent(fake_env, monkeypatch):
    monkeypatch.setenv("DAILY_BUDGET_CNY", "0.0001")
    state = fake_env / "spend.json"
    import time
    state.write_text(json.dumps({
        "date": time.strftime("%Y-%m-%d"),
        "cny": 0.001, "in_hit": 0, "in_miss": 0, "out": 0,
    }))
    client = LLMClient(state_path=state)
    with pytest.raises(BudgetExceeded):
        client.chat([{"role": "user", "content": "hi"}])


def test_three_tier_billing_accumulates_correctly(fake_env):
    client = LLMClient(state_path=fake_env / "spend.json")
    with patch("httpx.Client") as MC:
        instance = MC.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(in_hit=1_000_000, in_miss=1_000_000, out=1_000_000)
        client.chat([{"role": "user", "content": "x"}])
    # Expected cost: 1M*0.02 + 1M*1.0 + 1M*2.0 = 3.02 CNY... but budget=1.0 so first call passes (pre-call check)
    # then second call should fail
    assert client.in_hit == 1_000_000
    assert client.in_miss == 1_000_000
    assert client.out_tok == 1_000_000
    assert abs(client.spent - 3.02) < 1e-6


def test_budget_breaker_after_overspend(fake_env):
    client = LLMClient(state_path=fake_env / "spend.json")
    with patch("httpx.Client") as MC:
        instance = MC.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(in_hit=0, in_miss=2_000_000, out=0)  # 2.0 CNY
        client.chat([{"role": "user", "content": "x"}])  # pushes spent to 2.0, budget=1.0
    # next call must fail BEFORE making HTTP call
    with pytest.raises(BudgetExceeded):
        client.chat([{"role": "user", "content": "y"}])


def test_cache_hit_rate(fake_env):
    client = LLMClient(state_path=fake_env / "spend.json")
    with patch("httpx.Client") as MC:
        instance = MC.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(in_hit=300, in_miss=200, out=10)
        client.chat([{"role": "user", "content": "x"}])
    assert abs(client.cache_hit_rate - 0.6) < 1e-9


def test_state_resets_on_new_day(fake_env, monkeypatch):
    state = fake_env / "spend.json"
    state.write_text(json.dumps({
        "date": "1999-01-01", "cny": 99.0,
        "in_hit": 1, "in_miss": 1, "out": 1,
    }))
    client = LLMClient(state_path=state)
    assert client.spent == 0.0
    assert client.in_hit == 0


def test_state_persists_across_instances(fake_env):
    state = fake_env / "spend.json"
    c1 = LLMClient(state_path=state)
    with patch("httpx.Client") as MC:
        instance = MC.return_value.__enter__.return_value
        instance.post.return_value = _mock_response(in_hit=0, in_miss=100_000, out=50_000)
        c1.chat([{"role": "user", "content": "x"}])
    c2 = LLMClient(state_path=state)
    assert c2.spent > 0
    assert c2.in_miss == 100_000
    assert c2.out_tok == 50_000


def test_uses_model_from_env_by_default(fake_env, monkeypatch):
    monkeypatch.setenv("MODEL", "some-other-model")
    client = LLMClient(state_path=fake_env / "spend.json")
    captured = {}
    with patch("httpx.Client") as MC:
        instance = MC.return_value.__enter__.return_value
        def fake_post(url, headers=None, json=None):
            captured["payload"] = json
            return _mock_response()
        instance.post.side_effect = fake_post
        client.chat([{"role": "user", "content": "x"}])
    assert captured["payload"]["model"] == "some-other-model"


def test_explicit_model_arg_overrides_env(fake_env):
    client = LLMClient(state_path=fake_env / "spend.json")
    captured = {}
    with patch("httpx.Client") as MC:
        instance = MC.return_value.__enter__.return_value
        def fake_post(url, headers=None, json=None):
            captured["payload"] = json
            return _mock_response()
        instance.post.side_effect = fake_post
        client.chat([{"role": "user", "content": "x"}], model="qwen-coder-plus")
    assert captured["payload"]["model"] == "qwen-coder-plus"
