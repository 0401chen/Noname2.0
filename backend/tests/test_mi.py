from noname.mi import heuristic_analysis
from noname.schemas import (
    ChatMessage,
    ConversationAnalysis,
    ConversationStage,
    MIStrategy,
    PsychologicalNeed,
    RiskAssessment,
    RiskLevel,
    SessionState,
)


def test_heuristic_analysis_finds_focus_needs_and_change_talk() -> None:
    state = SessionState(session_id="demo")
    message = "队友每天都等我开黑，但我希望能早点停，不想第二天上课一直困"

    result = heuristic_analysis(
        state,
        message,
        RiskAssessment(level=RiskLevel.LOW),
    )

    assert result.focus_topic == "sleep"
    assert any(item.name == "belonging" for item in result.psychological_needs)
    assert result.change_talk
    assert result.mi_strategies


def test_bare_readiness_score_uses_previous_context() -> None:
    state = SessionState(
        session_id="ruler-demo",
        messages=[
            ChatMessage(role="user", content="队友每天都等我，我第二天又很困"),
            ChatMessage(role="assistant", content="你现在对改变这件事有多愿意？"),
        ],
        analysis=ConversationAnalysis(
            summary="睡眠和队友关系",
            stage=ConversationStage.FOCUS,
            focus_topic="sleep",
            psychological_needs=[PsychologicalNeed(name="belonging", confidence=0.8)],
        ),
    )

    result = heuristic_analysis(
        state,
        "1",
        RiskAssessment(level=RiskLevel.LOW),
    )

    assert result.stage is ConversationStage.EVOKE
    assert result.focus_topic == "sleep"
    assert result.motivation.importance == 1
    assert result.psychological_needs[0].name == "belonging"
    assert MIStrategy.READINESS_RULER in result.mi_strategies
    assert MIStrategy.AUTONOMY_SUPPORT in result.mi_strategies


def test_first_message_number_is_not_assumed_to_be_a_rating() -> None:
    result = heuristic_analysis(
        SessionState(session_id="first-number"),
        "1",
        RiskAssessment(level=RiskLevel.LOW),
    )

    assert result.motivation.importance is None
    assert result.stage is ConversationStage.ENGAGE


def test_high_risk_forces_safety_stage() -> None:
    state = SessionState(session_id="demo")
    result = heuristic_analysis(
        state,
        "我不想活了",
        RiskAssessment(level=RiskLevel.HIGH, signals=["self_harm_intent"]),
    )

    assert result.stage.value == "SAFETY"
    assert result.rag_required is False
