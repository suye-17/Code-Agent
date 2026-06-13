from eval.baseline_runner import render_report, summarize_rows


def test_summarize_rows_computes_baseline_metrics():
    rows = [
        {
            "id": "case_ok",
            "passed": True,
            "elapsed_s": 1.2,
            "spend_cny": 0.1,
            "tokens_in_hit": 80,
            "tokens_in_miss": 20,
            "tokens_out": 10,
            "agent_err": None,
            "pytest_tail": "1 passed",
        },
        {
            "id": "case_fail",
            "passed": False,
            "elapsed_s": 2.5,
            "spend_cny": 0.2,
            "tokens_in_hit": 20,
            "tokens_in_miss": 80,
            "tokens_out": 30,
            "agent_err": "RuntimeError: boom",
            "pytest_tail": "FAILED test_example.py::test_bug",
        },
    ]

    summary = summarize_rows(rows)

    assert summary == {
        "total": 2,
        "passed": 1,
        "pass_rate": 0.5,
        "total_spend": 0.3,
        "total_hit": 100,
        "total_miss": 100,
        "cache_hit_rate": 0.5,
    }


def test_render_report_includes_required_baseline_fields():
    rows = [
        {
            "id": "case_ok",
            "passed": True,
            "elapsed_s": 1.2,
            "spend_cny": 0.1,
            "tokens_in_hit": 80,
            "tokens_in_miss": 20,
            "tokens_out": 10,
            "agent_err": None,
            "pytest_tail": "1 passed",
        },
        {
            "id": "case_fail",
            "passed": False,
            "elapsed_s": 2.5,
            "spend_cny": 0.2,
            "tokens_in_hit": 20,
            "tokens_in_miss": 80,
            "tokens_out": 30,
            "agent_err": "RuntimeError: boom",
            "pytest_tail": "FAILED test_example.py::test_bug",
        },
    ]

    report = render_report(rows, generated_at="2026-06-13 12:00:00")

    assert "# Phase 1 Baseline (B0): naive ReAct + full file reads" in report
    assert "**Date:** 2026-06-13 12:00:00" in report
    assert "**Cases:** 2" in report
    assert "**Pass rate:** 1/2 = 50%" in report
    assert "**Total spend:** ¥0.3000" in report
    assert "**Cache hit rate:** 50.0%" in report
    assert "| id | pass | time(s) | spend (¥) | in_hit | in_miss | out | pytest tail |" in report
    assert "| case_ok | PASS | 1.2 | 0.1 | 80 | 20 | 10 | `1 passed` |" in report
    assert "| case_fail | FAIL | 2.5 | 0.2 | 20 | 80 | 30 | `FAILED test_example.py::test_bug` |" in report
    assert "### Agent errors" in report
    assert "- **case_fail**: RuntimeError: boom" in report
