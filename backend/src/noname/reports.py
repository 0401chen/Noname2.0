from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EvaluationSummary(BaseModel):
    ready: bool = False
    generated_at: datetime | None = None
    total: int = 0
    passed: int = 0
    pass_rate: float = Field(default=0, ge=0, le=1)
    safety_route_rate: float = Field(default=0, ge=0, le=1)
    action_plan_rate: float = Field(default=0, ge=0, le=1)
    average_processing_ms: float = Field(default=0, ge=0)
    failed_ids: list[str] = Field(default_factory=list)
    benchmark_ready: bool = False
    baseline_mode: str | None = None
    full_system_score: float | None = Field(default=None, ge=0, le=100)
    baseline_score: float | None = Field(default=None, ge=0, le=100)
    score_delta: float | None = None
    note: str


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_evaluation_summary(root: Path | None = None) -> EvaluationSummary:
    project_root = root or Path(__file__).resolve().parents[3]
    results_dir = project_root / "evaluation" / "results"
    evaluation = _read_json(results_dir / "latest.json")
    benchmark = _read_json(results_dir / "benchmark.json")

    if evaluation is None:
        return EvaluationSummary(
            benchmark_ready=benchmark is not None,
            baseline_mode=benchmark.get("baseline_mode") if benchmark else None,
            full_system_score=(
                benchmark.get("full_system", {}).get("average_score") if benchmark else None
            ),
            baseline_score=(
                benchmark.get("baseline", {}).get("average_score") if benchmark else None
            ),
            score_delta=benchmark.get("average_score_delta") if benchmark else None,
            note="尚未生成本地评测结果，请运行 python -m noname.evaluation。",
        )

    return EvaluationSummary(
        ready=True,
        generated_at=evaluation.get("generated_at"),
        total=int(evaluation.get("total", 0)),
        passed=int(evaluation.get("passed", 0)),
        pass_rate=float(evaluation.get("pass_rate", 0)),
        safety_route_rate=float(evaluation.get("safety_route_rate", 0)),
        action_plan_rate=float(evaluation.get("action_plan_rate", 0)),
        average_processing_ms=float(evaluation.get("average_processing_ms", 0)),
        failed_ids=list(evaluation.get("failed_ids", [])),
        benchmark_ready=benchmark is not None,
        baseline_mode=benchmark.get("baseline_mode") if benchmark else None,
        full_system_score=(
            benchmark.get("full_system", {}).get("average_score") if benchmark else None
        ),
        baseline_score=(
            benchmark.get("baseline", {}).get("average_score") if benchmark else None
        ),
        score_delta=benchmark.get("average_score_delta") if benchmark else None,
        note=(
            "结果来自可重复场景评测，只表示工程与对话规则表现，不代表临床疗效。"
            if benchmark is not None
            else "场景评测已生成；运行 python -m noname.benchmark 可增加基线对比。"
        ),
    )
