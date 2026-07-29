from types import SimpleNamespace

from noname.config import Settings
from noname.llm import LLMClient
from noname.schemas import (
    ConversationAnalysis,
    ConversationStage,
    MIStrategy,
    RiskAssessment,
    RiskLevel,
    SessionState,
)


class AliasCompletions:
    async def create(self, **kwargs):  # noqa: ANN003, ANN201
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"current_emotions": [], "mi_stage": "EVOKE", '
                            '"focus": "sleep", "strategies": ["READINESS_RULER"], '
                            '"retrieval_needed": false, "risk_level": "LOW", '
                            '"next_step": "理解低分背后的理由"}'
                        )
                    )
                )
            ]
        )


class AliasClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=AliasCompletions())


async def test_llm_analyze_repairs_provider_aliases_instead_of_falling_back() -> None:
    settings = Settings(
        _env_file=None,
        LLM_API_KEY="test-key",
        LLM_BASE_URL="https://provider.example/v1",
        LLM_MODEL="test-model",
    )
    client = LLMClient(settings)
    client.client = AliasClient()  # type: ignore[assignment]
    fallback = ConversationAnalysis(
        summary="用户正在讨论睡眠影响",
        stage=ConversationStage.FOCUS,
        focus_topic="sleep",
        risk=RiskAssessment(level=RiskLevel.LOW),
        mi_strategies=[MIStrategy.SUMMARY, MIStrategy.OPEN_QUESTION],
    )

    result = await client.analyze(SessionState(session_id="analysis-demo"), "1", fallback)

    assert result is not None
    assert result.summary == "用户正在讨论睡眠影响"
    assert result.stage is ConversationStage.EVOKE
    assert result.focus_topic == "sleep"
    assert result.mi_strategies == [MIStrategy.READINESS_RULER]
    assert client.last_analysis_mode == "llm-normalized"
    assert client.last_error is None
