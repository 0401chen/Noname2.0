from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import RiskAssessment, RiskLevel


@dataclass(frozen=True)
class RiskRule:
    name: str
    pattern: re.Pattern[str]
    level: RiskLevel
    immediate_danger: bool = False


HIGH_RISK_RULES = (
    RiskRule(
        "self_harm_intent",
        re.compile(r"(不想活|活着没意思|想死|去死|自杀|结束生命|伤害自己|割腕|跳楼)"),
        RiskLevel.HIGH,
    ),
    RiskRule(
        "immediate_plan",
        re.compile(r"(已经准备|现在就|今晚就|马上).{0,12}(自杀|去死|跳楼|割腕|伤害自己)"),
        RiskLevel.HIGH,
        immediate_danger=True,
    ),
    RiskRule(
        "cannot_stay_safe",
        re.compile(
            r"(无法|不能|没法).{0,6}(保证|确保).{0,4}(自己|我)?.{0,4}安全|"
            r"我现在不安全|我现在感觉很危险"
        ),
        RiskLevel.HIGH,
        immediate_danger=True,
    ),
    RiskRule(
        "violence_or_abuse",
        re.compile(r"(被打|家暴|虐待|性侵|强迫我|威胁我|不让我出门)"),
        RiskLevel.HIGH,
    ),
)

CONCERN_RULES = (
    RiskRule(
        "severe_hopelessness",
        re.compile(r"(什么都没意义|没有希望|没人会在乎我|我消失也没关系)"),
        RiskLevel.CONCERN,
    ),
    RiskRule(
        "severe_sleep_loss",
        re.compile(r"(连续|已经).{0,6}(两天|三天|几天).{0,8}(没睡|睡不着|只睡)"),
        RiskLevel.CONCERN,
    ),
    RiskRule(
        "major_function_loss",
        re.compile(r"(不去上学|退学|不吃饭|不出门|整天躺着|什么都做不了)"),
        RiskLevel.CONCERN,
    ),
    RiskRule(
        "bullying",
        re.compile(r"(校园欺凌|霸凌|被同学欺负|被孤立|被勒索)"),
        RiskLevel.CONCERN,
    ),
)

NEGATION_WINDOW = re.compile(r"(没有|不会|并不|不是).{0,4}(想死|自杀|伤害自己)")


def assess_rule_risk(text: str) -> RiskAssessment:
    """Conservative and auditable first-pass risk scan.

    Explicitly negated phrases are removed before matching. This avoids treating
    “我没有想死” as an affirmative disclosure while preserving later, separate
    risk statements in the same message.
    """

    normalized = " ".join(text.strip().split())
    scan_text = NEGATION_WINDOW.sub("", normalized)
    signals: list[str] = []
    level = RiskLevel.LOW
    immediate_danger = False

    for rule in HIGH_RISK_RULES:
        if rule.pattern.search(scan_text):
            signals.append(rule.name)
            level = RiskLevel.HIGH
            immediate_danger = immediate_danger or rule.immediate_danger

    if level is not RiskLevel.HIGH:
        for rule in CONCERN_RULES:
            if rule.pattern.search(scan_text):
                signals.append(rule.name)
                level = RiskLevel.CONCERN

    return RiskAssessment(
        level=level,
        signals=signals,
        immediate_danger=immediate_danger,
        source="rules",
    )


def merge_risk(rule_risk: RiskAssessment, semantic_risk: RiskAssessment | None) -> RiskAssessment:
    if semantic_risk is None:
        return rule_risk

    order = {RiskLevel.LOW: 0, RiskLevel.CONCERN: 1, RiskLevel.HIGH: 2}
    chosen = semantic_risk if order[semantic_risk.level] > order[rule_risk.level] else rule_risk

    return RiskAssessment(
        level=chosen.level,
        signals=list(dict.fromkeys([*rule_risk.signals, *semantic_risk.signals])),
        immediate_danger=rule_risk.immediate_danger or semantic_risk.immediate_danger,
        source="rules+semantic",
    )


def safety_reply(risk: RiskAssessment) -> tuple[str, list[str]]:
    """Return a short safety-first response without pretending to provide rescue."""

    if risk.immediate_danger:
        reply = (
            "我很在意你现在的安全。先不要一个人扛着，也先离开可能伤害到你的东西或地方。"
            "请马上联系身边可信任的成年人，让对方现在陪着你；如果你已经准备伤害自己或无法保证安全，"
            "请立即联系当地紧急救援服务。你现在身边有没有一个可以马上叫来的人？"
        )
        return reply, ["我身边有人", "我现在一个人", "我暂时安全"]

    reply = (
        "你刚才的话让我担心你可能承受了很大的痛苦。我们先不谈怎么减少游戏，先确认你的安全："
        "你现在有没有正在伤害自己，或者已经想好要怎么做？请尽快把这件事告诉一位可信任的成年人，"
        "例如家人、老师或学校心理老师，让现实中的人陪着你。"
    )
    return reply, ["我现在安全", "我有伤害自己的想法", "我可以联系一个成年人"]
