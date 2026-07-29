from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, Field

from .config import Settings
from .reports import EvaluationSummary


class DiagnosticsResponse(BaseModel):
    version: str
    environment: str
    llm_enabled: bool
    model: str
    provider_host: str | None = None
    storage: str
    session_retention_hours: int = Field(ge=1)
    knowledge_entries: int = Field(ge=0)
    evaluation_ready: bool
    benchmark_ready: bool
    warnings: list[str] = Field(default_factory=list)


def build_diagnostics(
    *,
    settings: Settings,
    storage_kind: str,
    knowledge_entries: int,
    evaluation: EvaluationSummary,
    version: str,
) -> DiagnosticsResponse:
    parsed = urlparse(settings.llm_base_url)
    warnings: list[str] = []

    if not settings.llm_enabled:
        warnings.append("未配置API Key，聊天将使用确定性离线降级回复。")
    if storage_kind == "memory":
        warnings.append("当前使用内存会话，后端重启后会话会被清空。")
    if not evaluation.ready:
        warnings.append("尚未生成60场景评测报告。")
    if not evaluation.benchmark_ready:
        warnings.append("尚未生成完整系统与基线对比报告。")

    return DiagnosticsResponse(
        version=version,
        environment=settings.app_env,
        llm_enabled=settings.llm_enabled,
        model=settings.llm_model,
        provider_host=parsed.hostname,
        storage=storage_kind,
        session_retention_hours=settings.session_retention_hours,
        knowledge_entries=knowledge_entries,
        evaluation_ready=evaluation.ready,
        benchmark_ready=evaluation.benchmark_ready,
        warnings=warnings,
    )
