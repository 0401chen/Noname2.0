from noname.mi import heuristic_analysis
from noname.schemas import RiskAssessment, RiskLevel, SessionState


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


def test_high_risk_forces_safety_stage() -> None:
    state = SessionState(session_id="demo")
    result = heuristic_analysis(
        state,
        "我不想活了",
        RiskAssessment(level=RiskLevel.HIGH, signals=["self_harm_intent"]),
    )

    assert result.stage.value == "SAFETY"
    assert result.rag_required is False
