from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import RiskAssessment, RiskLevel, SafetyConversationState


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
        re.compile(
            r"(被打|打我|揍我|殴打我|家暴|虐待|性侵|强迫我|威胁我|威胁不让|不让我出门)"
        ),
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

SAFETY_RESOLUTION_PATTERN = re.compile(
    r"("
    r"(我现在|我目前|我暂时).{0,4}安全.{0,12}(没有|不会|不打算).{0,8}(伤害自己|自杀|割腕)"
    r"|"
    r"(没有|不会|不打算).{0,8}(伤害自己|自杀|割腕).{0,12}(有人陪|身边有人|已经联系|已经告诉)"
    r"|"
    r"(已经联系|已经告诉).{0,10}(家人|父母|老师|成年人|朋友|辅导员).{0,10}(陪|过来|知道|在身边)"
    r"|"
    r"(家人|父母|老师|成年人|朋友|辅导员).{0,8}(在陪我|在我身边|已经来了)"
    r")"
)

SAFETY_REFUSAL_PATTERN = re.compile(
    r"(不想|不愿意|不敢|不能).{0,8}(告诉|联系|求助|找).{0,8}"
    r"(别人|家人|父母|老师|成年人|任何人)"
)

SAFETY_ALONE_PATTERN = re.compile(r"(我现在)?(一个人|没人陪|独自|独处)")
SAFETY_TEMP_SAFE_PATTERN = re.compile(r"(我现在|我目前|我暂时).{0,4}安全")


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



def safety_resolution_confirmed(text: str) -> bool:
    """Return True only for an explicit, concrete de-escalation statement."""

    normalized = " ".join(text.strip().split())
    return bool(SAFETY_RESOLUTION_PATTERN.search(normalized))


def carry_forward_safety_risk(previous: RiskAssessment) -> RiskAssessment:
    """Keep a previously detected HIGH-risk session in safety mode.

    A new turn should not fall back to ordinary conversation merely because the
    user did not repeat the original self-harm or violence wording.
    """

    return RiskAssessment(
        level=RiskLevel.HIGH,
        signals=list(dict.fromkeys([*previous.signals, "safety_session_active"])),
        immediate_danger=previous.immediate_danger,
        source="session",
    )


def safety_followup_reply(
    text: str,
    risk: RiskAssessment,
    *,
    continuing: bool,
) -> tuple[str, list[str]]:
    """Safety reply that remains useful across multiple turns instead of repeating."""

    normalized = " ".join(text.strip().split())

    if continuing and SAFETY_REFUSAL_PATTERN.search(normalized):
        reply = (
            "我听到你现在不想告诉别人。你不需要一次把所有事情解释清楚，但因为你刚才提到过想伤害自己，"
            "我不能把这当成普通聊天。先把可能伤害到你的东西放远，尽量去有其他人的地方。"
            "你可以只对一个可信任的人说一句“我现在状态不太安全，希望你能陪我一下”。"
            "你现在是一个人吗？"
        )
        return reply, ["我现在一个人", "身边有人", "我暂时安全"]

    if continuing and SAFETY_ALONE_PATTERN.search(normalized):
        reply = (
            "谢谢你告诉我你现在是一个人。先把安全放在第一位：请离开可能伤害到你的东西或地方，"
            "尽量去有其他人的公共空间，并马上联系一位可信任的成年人来陪你。"
            "如果你已经准备伤害自己或觉得自己可能马上行动，请立即联系当地紧急救援服务。"
        )
        return reply, ["我可以去找人", "我已经联系了人", "我暂时安全"]

    if continuing and SAFETY_TEMP_SAFE_PATTERN.search(normalized):
        reply = (
            "谢谢你告诉我你现在暂时安全。我们再确认一步：现在还有没有伤害自己的想法，"
            "或者已经准备好要怎么做？如果还有，就继续让现实中的人陪着你，并把可能伤害到你的东西放远。"
        )
        return reply, ["没有伤害自己的想法", "还有这样的想法", "身边有人陪我"]

    return safety_reply(risk)


def safety_resolution_reply() -> tuple[str, list[str]]:
    """Deterministic transition after the user clearly reports current safety."""

    reply = (
        "谢谢你把现在的安全情况说清楚。既然你明确说目前没有伤害自己的打算，"
        "并且已经有人陪着或已经连接到现实中的支持，我们可以先把安全状态放稳。"
        "如果危险感再次变强，请马上重新告诉身边的人或联系当地紧急救援。"
    )
    return reply, ["先休息一下", "继续聊刚才的事", "我想换个话题"]



def initialize_safety_state(
    current: SafetyConversationState,
    text: str,
    risk: RiskAssessment,
) -> SafetyConversationState:
    """Seed persistent safety state from hard rules without lowering uncertainty."""

    state = current.model_copy(deep=True)
    state.active = True
    normalized = " ".join(text.strip().split())

    if "self_harm_intent" in risk.signals:
        state.self_harm_thought = True
    if "immediate_plan" in risk.signals:
        state.immediate_plan = True
    if "cannot_stay_safe" in risk.signals:
        state.current_safety = False

    if SAFETY_ALONE_PATTERN.search(normalized):
        state.alone = True
        state.trusted_person_present = False
    if re.search(r"(身边有人|有人陪|家人在|父母在|朋友在|老师在)", normalized):
        state.alone = False
        state.trusted_person_present = True

    state.last_interpretation = "规则层进入安全优先状态"
    return state


def apply_safety_fallback_context(
    state: SafetyConversationState,
    text: str,
    previous_assistant: str | None,
) -> SafetyConversationState:
    """Deterministic backup for short contextual answers when the LLM is unavailable."""

    updated = state.model_copy(deep=True)
    normalized = " ".join(text.strip().split())
    previous = previous_assistant or ""

    if SAFETY_REFUSAL_PATTERN.search(normalized):
        updated.user_refuses_support = True

    if SAFETY_ALONE_PATTERN.search(normalized):
        updated.alone = True
        updated.trusted_person_present = False

    if re.search(r"(身边有人|有人陪|家人在|父母在|朋友在|老师在)", normalized):
        updated.alone = False
        updated.trusted_person_present = True

    if re.search(r"(已经联系|已经告诉).{0,10}(家人|父母|老师|成年人|朋友|辅导员)", normalized):
        updated.support_contacted = True

    if re.search(r"(刀|药|绳|危险的东西).{0,8}(放远|拿走|收起来|交给)", normalized):
        updated.means_removed = True

    affirmative = normalized in {"有", "有的", "嗯", "是", "有人", "在", "有啊"}
    negative = normalized in {"没有", "没", "不是", "不会", "不"}

    if affirmative:
        if any(marker in previous for marker in ("身边有没有", "可以马上叫来的人", "有人陪", "身边有人")):
            updated.alone = False
            updated.trusted_person_present = True
        elif any(marker in previous for marker in ("伤害自己的想法", "想伤害自己")):
            updated.self_harm_thought = True
        elif any(marker in previous for marker in ("已经想好要怎么做", "准备好要怎么做", "计划")):
            updated.immediate_plan = True

    if negative:
        if any(marker in previous for marker in ("伤害自己的想法", "想伤害自己")):
            updated.self_harm_thought = False
        if any(marker in previous for marker in ("正在伤害自己", "已经想好要怎么做", "准备好要怎么做")):
            updated.currently_injuring = False
            updated.immediate_plan = False
        if any(marker in previous for marker in ("一个人吗", "现在是一个人")):
            updated.alone = False

    if SAFETY_TEMP_SAFE_PATTERN.search(normalized):
        updated.current_safety = True

    if re.search(r"(没有|不会|不打算).{0,8}(伤害自己|自杀|割腕)", normalized):
        updated.self_harm_thought = False
        updated.immediate_plan = False
        updated.currently_injuring = False

    updated.last_interpretation = normalized[:120] or updated.last_interpretation
    return updated


def merge_safety_state(
    base: SafetyConversationState,
    updates: dict[str, object] | None,
) -> SafetyConversationState:
    """Merge only explicit non-null LLM fields into the persistent state."""

    if not updates:
        return base

    merged = base.model_copy(deep=True)
    for field in (
        "self_harm_thought",
        "immediate_plan",
        "currently_injuring",
        "current_safety",
        "alone",
        "trusted_person_present",
        "support_contacted",
        "means_removed",
        "user_refuses_support",
    ):
        value = updates.get(field)
        if isinstance(value, bool):
            setattr(merged, field, value)

    interpretation = updates.get("interpretation")
    if isinstance(interpretation, str) and interpretation.strip():
        merged.last_interpretation = interpretation.strip()[:240]

    merged.active = True
    return merged


def safety_can_resolve(state: SafetyConversationState) -> bool:
    """Programmatic exit gate; the LLM cannot independently end safety mode."""

    no_immediate_harm = (
        state.self_harm_thought is False
        and state.immediate_plan is False
        and state.currently_injuring is False
    )
    connected_support = (
        state.trusted_person_present is True
        or state.support_contacted is True
    )
    return bool(no_immediate_harm and connected_support)


def contextual_safety_fallback_reply(
    state: SafetyConversationState,
    risk: RiskAssessment,
) -> tuple[str, list[str]]:
    """Choose the next safety step from what has already been confirmed."""

    if risk.immediate_danger or state.current_safety is False:
        return safety_reply(
            RiskAssessment(
                level=RiskLevel.HIGH,
                signals=risk.signals,
                immediate_danger=True,
                source=risk.source,
            )
        )

    if state.trusted_person_present is True:
        if state.currently_injuring is None or state.immediate_plan is None:
            return (
                "好，身边现在有人这一点很重要。先尽量和对方待在一起，也把可能伤害到你的东西放远。"
                "我们再确认一件事：你现在有没有正在伤害自己，或者已经准备马上去做？",
                ["没有", "有这样的情况", "我不确定"],
            )
        if state.self_harm_thought is not False:
            return (
                "谢谢你继续告诉我这些。既然身边有人，先不要独处，也继续让对方陪着你。"
                "你现在还有伤害自己的想法吗？",
                ["没有了", "还有", "我不确定"],
            )

    if state.alone is True:
        return (
            "你现在是一个人，所以先把现实中的陪伴接上会更重要。请去有其他人的地方，"
            "并联系一位可信任的成年人来陪你；如果你觉得自己可能马上行动，请联系当地紧急救援服务。",
            ["我可以去找人", "我已经联系了人", "我暂时安全"],
        )

    if state.user_refuses_support is True:
        return (
            "我知道你现在不想把这些事告诉别人。你不用一次解释很多，可以只告诉一个可信任的人："
            "“我现在状态不太安全，希望你陪我一下。”在这之前，先尽量不要独处，也把可能伤害到你的东西放远。",
            ["我身边有人", "我现在一个人", "我暂时安全"],
        )

    return safety_reply(risk)
