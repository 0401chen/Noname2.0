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
    "belonging": ("队友", "朋友", "开黑", "一起玩", "群里", "没人陪", "战队", "同学"),
    "achievement": ("上分", "段位", "赢", "厉害", "擅长", "成就", "排名", "翻盘"),
    "autonomy": ("别管我", "凭什么", "控制我", "自己决定", "不理解我", "没收"),
    "relaxation": ("放松", "累", "压力", "烦", "缓一缓", "解压"),
    "escape": ("不想面对", "逃避", "忘掉", "作业", "学习也没用", "现实", "躲一会"),
    "connection": ("孤独", "一个人", "被需要", "有人理我", "有人聊天", "没人理我"),
}

FOCUS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sleep": (
        "熬夜",
        "睡觉",
        "睡眠",
        "睡不着",
        "没睡",
        "只睡",
        "晚睡",
        "凌晨",
        "困",
        "起不来",
        "两点",
        "三点",
    ),
    "stopping": (
        "停不下来",
        "最后一局",
        "再来一把",
        "控制不住",
        "下不了线",
        "翻盘",
        "继续玩",
    ),
    "school": (
        "作业",
        "学习",
        "上课",
        "上学",
        "缺课",
        "考试",
        "成绩",
        "拖延",
    ),
    "family": ("父母", "爸妈", "妈妈", "爸爸", "家里人", "没收", "吵架"),
    "emotion": ("焦虑", "难受", "烦躁", "低落", "孤独", "压力", "绝望", "没意义"),
    "social": ("队友", "朋友", "战队", "开黑", "社交", "被孤立"),
}

CHANGE_PATTERNS = (
    re.compile(r"(想|希望|最好|要是能).{0,12}(少玩|早点|停下|改变|不困|不吵架)"),
    re.compile(r"(不想再|受够了|其实也不想)"),
)

SUSTAIN_PATTERNS = (
    re.compile(r"(没问题|没什么|不用改|不可能|做不到|管不着)"),
    re.compile(r"(不能少|必须玩|队友需要|只有游戏)"),
)

RULER_PATTERN = re.compile(r"(?:重要|想改变|把握|信心|愿意).{0,8}(10|[0-9])\s*分")
BARE_RULER_PATTERN = re.compile(r"^\s*(10|[0-9])\s*(?:分)?\s*$")
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


def _bare_ruler_score(state: SessionState, text: str) -> int | None:
    match = BARE_RULER_PATTERN.fullmatch(text)
    if match is None or not state.messages:
        return None
    return int(match.group(1))


def _choose_stage(
    state: SessionState,
    focus_topic: str | None,
    change_talk: list[str],
    text: str,
    bare_score: int | None,
) -> ConversationStage:
    if state.action_plan is not None:
        return ConversationStage.REVIEW
    if PLAN_PATTERN.search(text):
        return ConversationStage.PLAN
    if bare_score is not None:
        return ConversationStage.EVOKE
    if change_talk:
        return ConversationStage.EVOKE
    if focus_topic or len(state.messages) >= 2:
        return ConversationStage.FOCUS
    return ConversationStage.ENGAGE


def _choose_strategies(
    stage: ConversationStage,
    change_talk: list[str],
    sustain_talk: list[str],
    bare_score: int | None,
) -> list[MIStrategy]:
    if stage is ConversationStage.REVIEW:
        return [MIStrategy.AFFIRMATION, MIStrategy.REVIEW_AND_ADJUST]
    if stage is ConversationStage.PLAN:
        return [MIStrategy.ASK_PERMISSION, MIStrategy.ACTION_PLANNING]
    if bare_score is not None:
        if bare_score <= 3:
            return [MIStrategy.AUTONOMY_SUPPORT, MIStrategy.READINESS_RULER]
        if bare_score >= 8:
            return [MIStrategy.AFFIRMATION, MIStrategy.ELICIT_CHANGE_TALK]
        return [MIStrategy.READINESS_RULER, MIStrategy.ELICIT_CHANGE_TALK]
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

    previous = state.analysis
    focus_topic = _first_matching_topic(text) or (previous.focus_topic if previous else None)
    current_needs = _needs(text)
    psychological_needs = current_needs or (previous.psychological_needs if previous else [])
    current_emotions = [
        word
        for word in ("烦躁", "焦虑", "低落", "孤独", "压力", "绝望")
        if word in text
    ]
    emotions = current_emotions or (previous.emotions if previous and len(text.strip()) <= 3 else [])

    change_talk = _extract(CHANGE_PATTERNS, text)
    sustain_talk = _extract(SUSTAIN_PATTERNS, text)
    bare_score = _bare_ruler_score(state, text)
    stage = _choose_stage(state, focus_topic, change_talk, text, bare_score)
    strategies = _choose_strategies(stage, change_talk, sustain_talk, bare_score)

    ruler_match = RULER_PATTERN.search(text)
    explicit_score = int(ruler_match.group(1)) if ruler_match else None
    confidence = explicit_score if ruler_match and "信心" in text else None
    importance = explicit_score if ruler_match and "信心" not in text else bare_score

    rag_required = bool(
        stage in {ConversationStage.PLAN, ConversationStage.REVIEW}
        or re.search(r"(怎么办|怎么做|方法|建议|睡眠|焦虑|压力)", text)
    )

    summary = (
        f"用户给出了 {bare_score}/10 的改变意愿评分"
        if bare_score is not None
        else f"用户正在讨论{focus_topic or '游戏与生活的关系'}"
    )

    return ConversationAnalysis(
        summary=summary,
        stage=stage,
        focus_topic=focus_topic,
        emotions=emotions,
        psychological_needs=psychological_needs,
        change_talk=change_talk,
        sustain_talk=sustain_talk,
        motivation=MotivationState(importance=importance, confidence=confidence),
        risk=risk,
        mi_strategies=strategies,
        rag_required=rag_required,
        rag_queries=[item for item in (focus_topic, "微行动") if item] if rag_required else [],
        next_goal=(
            "理解评分背后的理由，不推动用户过快进入计划"
            if bare_score is not None and bare_score <= 3
            else {
                ConversationStage.ENGAGE: "理解游戏对用户的价值",
                ConversationStage.FOCUS: "与用户共同选定一个优先问题",
                ConversationStage.EVOKE: "引出用户自己的改变理由",
                ConversationStage.PLAN: "形成足够小且由用户选择的行动实验",
                ConversationStage.REVIEW: "复盘有效条件并调整实验",
            }.get(stage, "继续理解用户")
        ),
    )
