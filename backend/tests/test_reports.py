import json

from noname.reports import load_evaluation_summary


def test_evaluation_summary_is_safe_when_reports_are_missing(tmp_path) -> None:
    summary = load_evaluation_summary(tmp_path)

    assert summary.ready is False
    assert summary.benchmark_ready is False
    assert "尚未生成" in summary.note


def test_evaluation_summary_reads_compact_metrics(tmp_path) -> None:
    results = tmp_path / "evaluation" / "results"
    results.mkdir(parents=True)
    (results / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-29T00:00:00Z",
                "total": 60,
                "passed": 58,
                "pass_rate": 0.9667,
                "safety_route_rate": 1.0,
                "action_plan_rate": 0.9,
                "average_processing_ms": 12.5,
                "failed_ids": ["one", "two"],
            }
        ),
        encoding="utf-8",
    )
    (results / "benchmark.json").write_text(
        json.dumps(
            {
                "baseline_mode": "deterministic-naive",
                "full_system": {"average_score": 92.0},
                "baseline": {"average_score": 51.0},
                "average_score_delta": 41.0,
            }
        ),
        encoding="utf-8",
    )

    summary = load_evaluation_summary(tmp_path)

    assert summary.ready is True
    assert summary.total == 60
    assert summary.passed == 58
    assert summary.benchmark_ready is True
    assert summary.score_delta == 41.0
