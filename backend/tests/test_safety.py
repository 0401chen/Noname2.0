from noname.safety import assess_rule_risk, merge_risk
from noname.schemas import RiskAssessment, RiskLevel


def test_high_risk_self_harm_expression_is_detected() -> None:
    result = assess_rule_risk("反正活着没意思，游戏关了更没意思")

    assert result.level is RiskLevel.HIGH
    assert "self_harm_intent" in result.signals


def test_negated_self_harm_expression_is_not_escalated_by_simple_rule() -> None:
    result = assess_rule_risk("我没有想死，只是最近真的很累")

    assert result.level is RiskLevel.LOW


def test_concern_level_for_multiple_days_without_sleep() -> None:
    result = assess_rule_risk("我已经连续三天没睡好了")

    assert result.level is RiskLevel.CONCERN


def test_semantic_assessment_can_raise_but_not_lower_rule_level() -> None:
    rule = RiskAssessment(level=RiskLevel.HIGH, signals=["self_harm_intent"])
    semantic = RiskAssessment(level=RiskLevel.LOW, signals=[])

    merged = merge_risk(rule, semantic)

    assert merged.level is RiskLevel.HIGH
    assert "self_harm_intent" in merged.signals
