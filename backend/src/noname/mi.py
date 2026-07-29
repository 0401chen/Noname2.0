from __future__ import annotations

import re

from .schemas import (
    ConversationAnalysis,
    ConversationStage,
    MIStrategy,
    MotivationState,
    PsychologicalNeed,
    RiskAssessment,
    RiskLevel,
    SessionState,
)


NEED_KEYWORDS: dict[str, tuple[str, ...]] = {
    "belonging": ("队友", "朋友", "开黑", "一起玩", "群里", "没人陪"),
    "achievement": ("上分", "段位", "赢", "厉害", "擅长", "成就", "排名"),
    "autonomy": ("别管我", "凭什么", "控制我", "自己决定", "不理解我"),
    "relaxation": ("放松", "累", "压力", "烦", "缓一缓", "解压"),
    "escape": ("不想面对", "逃避", "忘掉", "作业", "学习也没用", "现实"),
    "connection": ("孤独", "一个人", "被需要", "有人理我", "有人聊天"),
}

FOCUS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sleep": ("熬夜", "睡觉", "凌晨", "困", "起不来", "两点", "三点"),
    "stopping": ("停不下来", "最后一局", "再来一把", "控制不住", "下不了线"),
    "school": ("作业", "学习", "上课", "考试", "成绩", "拖延"),
    "family": ("父母", "爸妈", "妈妈", "爸爸", "没收", "吵架"),
    "emotion": ("焦虑", "难受", "烦躁", "低落", "孤独", "压力"),
    "social": ("队友", "朋友", "开黑", "社交", "被孤立"),
}

CHANGE_PATTERNS = (
    re.compile(r"(想|希望|最好|要是能).{0,12}(少玩|早点|停下|改变|不困|不吵架)"),
    re.compile(r"(不想再|受够了|其实也不想)"),
)

SUSTAIN_PATTERNS = (
    re.compile(r"(没问题|没什么|不用改|不可能|做不到|管不着)"),
    re.compile(r"(不能少|必须玩|队友需要|只有游戏)"),
)

RULER_PATTERN = re.compile(r"(?:重要|想改变|把握|信心).{0,8}([0-9]|10)\s*分")
PLAN_PATTERN = re.compile(
    r"(计划|试试|我试试|可以试|愿意试|试三天|怎么做|可以做什么|提前.{0,5}分钟)"
)


def _first_matching_topic(text: str) -> str | None:
    scores = {
        topic: sum(1 for keyword in keywords if keyword in text)
        for topic, keywords in FOCUS_KEYWORDS.items()
    }
    topic, score = max(scores.items(), key=lambda item: item[1])
    return topic if score else None


def _needs(text: str) -> list[PsychologicalNeed]:
    found: list[PsychologicalNeed] = []
    for name, keywords in NEED_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits:
            found.append(PsychologicalNeed(name=name, confidence=min(0.55 + hits * 0.12, 0.91)))
    return sorted(found, key=lambda item: item.confidence, reverse=True)[:3]


def _extract(patterns: tuple[re.Pattern[str], ...], text: str) -> list[str]:
    return [text] if any(pattern.search(text) for pattern in patterns) else []


def _choose_stage(
    state: SessionState,
    focus_topic: str | None,
    change_talk: list[str],
    text: str,
) -> ConversationStage:
    if state.action_plan is not None:
        return ConversationStage.REVIEW
    if PLAN_PATTERN.search(text):
        return ConversationStage.PLAN
    if change_talk:
        return ConversationStage.EVOKE
    if focus_topic or len(state.messages) >= 2:
        return ConversationStage.FOCUS
    return ConversationStage.ENGAGE


def _choose_strategies(
    stage: ConversationStage,
    change_talk: list[str],
    sustain_talk: list[str],
) -> list[MIStrategy]:
    if stage is ConversationStage.REVIEW:
        return [MIStrategy.AFFIRMATION, MIStrategy.REVIEW_AND_ADJUST]
    if stage is ConversationStage.PLAN:
        return [MIStrategy.ASK_PERMISSION, MIStrategy.ACTION_PLANNING]
    if change_talk and sustain_talk:
        return [MIStrategy.DOUBLE_SIDED_REFLECTION, MIStrategy.ELICIT_CHANGE_TALK]
    if change_talk:
        return [MIStrategy.COMPLEX_REFLECTION, MIStrategy.ELICIT_CHANGE_TALK]
    if sustain_talk:
        return [MIStrategy.AUTONOMY_SUPPORT, MIStrategy.COMPLEX_REFLECTION]
    if stage is ConversationStage.FOCUS:
        return [MIStrategy.SUMMARY, MIStrategy.OPEN_QUESTION]
    return [MIStrategy.SIMPLE_REFLECTION, MIStrategy.OPEN_QUESTION]


def heuristic_analysis(
    state: SessionState,
    text: str,
    risk: RiskAssessment,
) -> ConversationAnalysis:
    """Deterministic fallback used when an LLM is unavailable or returns invalid JSON."""

    if risk.level is RiskLevel.HIGH:
        return ConversationAnalysis(
            summary="检测到需要优先处理的安全风险",
            stage=ConversationStage.SAFETY,
            risk=risk,
            mi_strategies=[],
            next_goal="确认当前安全并连接现实支持",
        )

    focus_topic = _first_matching_topic(text) or (
        state.analysis.focus_topic if state.analysis else None
    )
    change_talk = _extract(CHANGE_PATTERNS, text)
    sustain_talk = _extract(SUSTAIN_PATTERNS, text)
    stage = _choose_stage(state, focus_topic, change_talk, text)
    strategies = _choose_strategies(stage, change_talk, sustain_talk)

    ruler_match = RULER_PATTERN.search(text)
    confidence = int(ruler_match.group(1)) if ruler_match and "信心" in text else None
    importance = int(ruler_match.group(1)) if ruler_match and "信心" not in text else None

    rag_required = bool(
        stage in {ConversationStage.PLAN, ConversationStage.REVIEW}
        or re.search(r"(怎么办|怎么做|方法|建议|睡眠|焦虑|压力)", text)
    )

    return ConversationAnalysis(
        summary=f"用户正在讨论{focus_topic or '游戏与生活的关系'}",
        stage=stage,
        focus_topic=focus_topic,
        emotions=[word for word in ("烦躁", "焦虑", "低落", "孤独", "压力") if word in text],
        psychological_needs=_needs(text),
        change_talk=change_talk,
        sustain_talk=sustain_talk,
        motivation=MotivationState(importance=importance, confidence=confidence),
        risk=risk,
        mi_strategies=strategies,
        rag_required=rag_required,
        rag_queries=[item for item in (focus_topic, "微行动") if item] if rag_required else [],
        next_goal={
            ConversationStage.ENGAGE: "理解游戏对用户的价值",
            ConversationStage.FOCUS: "与用户共同选定一个优先问题",
            ConversationStage.EVOKE: "引出用户自己的改变理由",
            ConversationStage.PLAN: "形成足够小且由用户选择的行动实验",
            ConversationStage.REVIEW: "复盘有效条件并调整实验",
        }.get(stage, "继续理解用户"),
    )
