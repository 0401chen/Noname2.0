from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from .config import get_settings
from .llm import LLMClient
from .rag import KnowledgeStore
from .schemas import ChatRequest, ChatResponse, ConversationStage, FocusTopic, RiskLevel
from .service import ConversationService
from .storage import MemorySessionStore


class ScenarioExpectation(BaseModel):
    stage: ConversationStage | None = None
    risk_level: RiskLevel | None = None
    focus_topic: FocusTopic | None = None
    action_plan: bool | None = None
    rag_used: bool | None = None
    reply_contains_any: list[str] = Field(default_factory=list)
    reply_contains_all: list[str] = Field(default_factory=list)
    reply_forbidden: list[str] = Field(default_factory=list)


class EvaluationScenario(BaseModel):
    id: str
    title: str
    category: str
    messages: list[str] = Field(min_length=1)
    age_group: str = "15-16"
    expected: ScenarioExpectation = Field(default_factory=ScenarioExpectation)


class ScenarioResult(BaseModel):
    id: str
    title: str
    category: str
    passed: bool
    checks: dict[str, bool]
    final_reply: str
    final_stage: ConversationStage | None = None
    final_risk: RiskLevel | None = None
    focus_topic: FocusTopic | None = None
    action_plan_created: bool = False
    rag_used: bool = False
    processing_ms: float = 0


class EvaluationReport(BaseModel):
    generated_at: datetime
    mode: str
    total: int
    passed: int
    pass_rate: float
    category_pass_rates: dict[str, float]
    check_pass_rates: dict[str, float]
    safety_total: int = 0
    safety_passed: int = 0
    safety_route_rate: float = 0
    action_plan_total: int = 0
    action_plan_passed: int = 0
    action_plan_rate: float = 0
    average_processing_ms: float = 0
    failed_ids: list[str] = Field(default_factory=list)
    results: list[ScenarioResult]


class OfflineLLM:
    """Disable network calls so CI evaluation remains deterministic."""

    enabled = False
    last_error: str | None = None

    async def analyze(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def generate_reply(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _load_scenario_file(path: Path) -> list[EvaluationScenario]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError(f"scenario file must contain a JSON array: {path}")
    return [EvaluationScenario.model_validate(item) for item in payload]


def load_scenarios(paths: Path | Iterable[Path]) -> list[EvaluationScenario]:
    """Load one or more v2 scenario files and reject duplicate identifiers."""

    resolved_paths = [paths] if isinstance(paths, Path) else list(paths)
    scenarios: list[EvaluationScenario] = []
    identifiers: set[str] = set()
    for path in resolved_paths:
        for scenario in _load_scenario_file(path):
            if scenario.id in identifiers:
                raise ValueError(f"duplicate scenario id: {scenario.id}")
            identifiers.add(scenario.id)
            scenarios.append(scenario)
    return scenarios


def _evaluate_checks(
    response: ChatResponse,
    expectation: ScenarioExpectation,
) -> dict[str, bool]:
    trace = response.trace
    checks: dict[str, bool] = {"has_reply": bool(response.reply.strip())}

    if expectation.stage is not None:
        checks["stage"] = trace is not None and trace.stage is expectation.stage
    if expectation.risk_level is not None:
        checks["risk_level"] = (
            trace is not None and trace.risk.level is expectation.risk_level
        )
    if expectation.focus_topic is not None:
        checks["focus_topic"] = (
            trace is not None and trace.focus_topic == expectation.focus_topic
        )
    if expectation.action_plan is not None:
        checks["action_plan"] = (response.action_plan is not None) is expectation.action_plan
    if expectation.rag_used is not None:
        checks["rag_used"] = trace is not None and trace.rag_used is expectation.rag_used
    if expectation.reply_contains_any:
        checks["reply_contains_any"] = any(
            token in response.reply for token in expectation.reply_contains_any
        )
    if expectation.reply_contains_all:
        checks["reply_contains_all"] = all(
            token in response.reply for token in expectation.reply_contains_all
        )
    if expectation.reply_forbidden:
        checks["reply_forbidden"] = all(
            token not in response.reply for token in expectation.reply_forbidden
        )
    return checks


async def evaluate_scenario(
    service: ConversationService,
    scenario: EvaluationScenario,
) -> ScenarioResult:
    session_id = f"evaluation-{scenario.id}"
    service.sessions.clear(session_id)
    response: ChatResponse | None = None

    for message in scenario.messages:
        response = await service.chat(
            ChatRequest(
                session_id=session_id,
                message=message,
                age_group=scenario.age_group,
                reviewer_mode=True,
            )
        )

    if response is None:
        raise RuntimeError(f"scenario {scenario.id} produced no response")

    checks = _evaluate_checks(response, scenario.expected)
    trace = response.trace
    return ScenarioResult(
        id=scenario.id,
        title=scenario.title,
        category=scenario.category,
        passed=all(checks.values()),
        checks=checks,
        final_reply=response.reply,
        final_stage=trace.stage if trace else None,
        final_risk=trace.risk.level if trace else None,
        focus_topic=trace.focus_topic if trace else None,
        action_plan_created=response.action_plan is not None,
        rag_used=trace.rag_used if trace else False,
        processing_ms=trace.processing_ms if trace else 0,
    )


def _pass_rates(results: list[ScenarioResult]) -> tuple[dict[str, float], dict[str, float]]:
    categories = sorted({result.category for result in results})
    category_pass_rates: dict[str, float] = {}
    for category in categories:
        category_results = [result for result in results if result.category == category]
        category_pass_rates[category] = round(
            sum(result.passed for result in category_results) / len(category_results),
            4,
        )

    check_names = sorted({name for result in results for name in result.checks})
    check_pass_rates: dict[str, float] = {}
    for check_name in check_names:
        values = [result.checks[check_name] for result in results if check_name in result.checks]
        check_pass_rates[check_name] = round(sum(values) / len(values), 4)
    return category_pass_rates, check_pass_rates


async def run_evaluation(
    service: ConversationService,
    scenarios: list[EvaluationScenario],
    *,
    mode: str,
) -> EvaluationReport:
    results = [await evaluate_scenario(service, scenario) for scenario in scenarios]
    passed = sum(result.passed for result in results)
    category_pass_rates, check_pass_rates = _pass_rates(results)

    safety_pairs = [
        (scenario, result)
        for scenario, result in zip(scenarios, results, strict=True)
        if scenario.expected.risk_level is RiskLevel.HIGH
        or scenario.expected.stage is ConversationStage.SAFETY
    ]
    safety_passed = sum(result.passed for _, result in safety_pairs)

    action_pairs = [
        (scenario, result)
        for scenario, result in zip(scenarios, results, strict=True)
        if scenario.expected.action_plan is True
    ]
    action_passed = sum(
        result.checks.get("action_plan", False) for _, result in action_pairs
    )

    return EvaluationReport(
        generated_at=datetime.now(timezone.utc),
        mode=mode,
        total=len(results),
        passed=passed,
        pass_rate=round(passed / len(results), 4) if results else 0,
        category_pass_rates=category_pass_rates,
        check_pass_rates=check_pass_rates,
        safety_total=len(safety_pairs),
        safety_passed=safety_passed,
        safety_route_rate=round(safety_passed / len(safety_pairs), 4) if safety_pairs else 0,
        action_plan_total=len(action_pairs),
        action_plan_passed=action_passed,
        action_plan_rate=round(action_passed / len(action_pairs), 4) if action_pairs else 0,
        average_processing_ms=round(
            sum(result.processing_ms for result in results) / len(results),
            2,
        )
        if results
        else 0,
        failed_ids=[result.id for result in results if not result.passed],
        results=results,
    )


async def _run_cli(args: argparse.Namespace, scenario_paths: list[Path]) -> EvaluationReport:
    settings = get_settings()
    llm = LLMClient(settings) if args.online else OfflineLLM()
    service = ConversationService(
        llm=llm,  # type: ignore[arg-type]
        knowledge=KnowledgeStore(),
        sessions=MemorySessionStore(),
        max_messages=settings.session_max_messages,
    )
    scenarios = load_scenarios(scenario_paths)
    return await run_evaluation(
        service,
        scenarios,
        mode="online-llm" if args.online else "deterministic-offline",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Run Re:Play conversation scenarios")
    parser.add_argument(
        "--scenarios",
        action="append",
        help="Scenario JSON file. May be supplied more than once.",
    )
    parser.add_argument(
        "--output",
        default=str(root / "evaluation" / "results" / "latest.json"),
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Use the configured LLM instead of deterministic fallback responses",
    )
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Write the report without returning a non-zero process status",
    )
    args = parser.parse_args()

    scenario_paths = (
        [Path(item) for item in args.scenarios]
        if args.scenarios
        else [
            root / "evaluation" / "scenarios" / "core.json",
            root / "evaluation" / "scenarios" / "extended.json",
        ]
    )
    report = asyncio.run(_run_cli(args, scenario_paths))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print(
        f"Re:Play evaluation: {report.passed}/{report.total} passed "
        f"({report.pass_rate * 100:.1f}%)"
    )
    print(
        f"- safety routing: {report.safety_passed}/{report.safety_total} "
        f"({report.safety_route_rate * 100:.1f}%)"
    )
    print(
        f"- action plans: {report.action_plan_passed}/{report.action_plan_total} "
        f"({report.action_plan_rate * 100:.1f}%)"
    )
    for category, pass_rate in report.category_pass_rates.items():
        print(f"- {category}: {pass_rate * 100:.1f}%")
    print(f"Report: {output_path}")

    if report.passed != report.total and not args.allow_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
