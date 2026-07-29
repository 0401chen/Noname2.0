from noname.analysis_adapter import normalize_analysis_payload
from noname.schemas import (
    ConversationAnalysis,
    ConversationStage,
    MIStrategy,
    MotivationState,
    PsychologicalNeed,
    RiskAssessment,
    RiskLevel,
)


def _fallback() -> ConversationAnalysis:
    return ConversationAnalysis(
        summary="用户正在讨论睡眠和队友关系",
        stage=ConversationStage.FOCUS,
        focus_topic="sleep",
        emotions=["压力"],
        psychological_needs=[PsychologicalNeed(name="belonging", confidence=0.67)],
        motivation=MotivationState(importance=1),
        risk=RiskAssessment(level=RiskLevel.LOW, source="rules"),
        mi_strategies=[MIStrategy.SUMMARY, MIStrategy.OPEN_QUESTION],
        next_goal="共同确定优先问题",
    )


def test_missing_summary_and_provider_aliases_are_normalized() -> None:
    result = normalize_analysis_payload(
        {
            "current_emotions": ["担心"],
            "needs": [{"need": "belonging", "confidence": 67}],
            "mi_stage": "EVOKE",
            "strategies": ["READINESS_RULER", "AUTONOMY_SUPPORT"],
            "retrieval_needed": False,
            "risk_level": "LOW",
            "next_step": "理解为什么改变意愿不是零分",
        },
        _fallback(),
    )

    assert result.summary == "用户正在讨论睡眠和队友关系"
    assert result.stage is ConversationStage.EVOKE
    assert result.focus_topic == "sleep"
    assert result.emotions == ["担心"]
    assert result.psychological_needs[0].confidence == 0.67
    assert result.mi_strategies == [
        MIStrategy.READINESS_RULER,
        MIStrategy.AUTONOMY_SUPPORT,
    ]
    assert result.rag_required is False
    assert result.risk.level is RiskLevel.LOW


def test_singular_emotion_and_retrieval_query_aliases_are_supported() -> None:
    result = normalize_analysis_payload(
        {
            "analysis_summary": "用户愿意尝试一个小行动",
            "conversation_stage": "PLAN",
            "primary_focus": "sleep",
            "current_emotion": "有一点担心",
            "change_language": "愿意试三天提前20分钟",
            "motivation_state": {"confidence": "6"},
            "risk_assessment": {"risk_level": "LOW", "risk_signals": []},
            "recommended_strategies": ["ASK_PERMISSION", "ACTION_PLANNING"],
            "needs_retrieval": "true",
            "search_queries": ["青少年睡眠 微行动"],
        },
        _fallback(),
    )

    assert result.summary == "用户愿意尝试一个小行动"
    assert result.stage is ConversationStage.PLAN
    assert result.emotions == ["有一点担心"]
    assert result.change_talk == ["愿意试三天提前20分钟"]
    assert result.motivation.confidence == 6
    assert result.rag_required is True
    assert result.rag_queries == ["青少年睡眠 微行动"]


def test_invalid_enums_fall_back_to_deterministic_analysis() -> None:
    result = normalize_analysis_payload(
        {
            "summary": "供应商返回了无法识别的枚举",
            "stage": "ADVISE",
            "focus_topic": "gaming_time",
            "risk_level": "UNKNOWN",
            "mi_strategies": ["TELL_USER_WHAT_TO_DO"],
        },
        _fallback(),
    )

    assert result.stage is ConversationStage.FOCUS
    assert result.focus_topic == "sleep"
    assert result.risk.level is RiskLevel.LOW
    assert result.mi_strategies == [MIStrategy.SUMMARY, MIStrategy.OPEN_QUESTION]
