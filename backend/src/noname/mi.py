from __future__ import annotations

import re

from .dialogue_guard import is_neutral_preference, is_user_correction
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
    "achievement": (
        "上分",
        "段位",
        "赢",
        "厉害",
        "擅长",
        "成就",
        "排名",
        "翻盘",
        "击杀",
        "虐杀",
        "压制",
        "操作",
        "团战",
        "对面",
    ),
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
    "school": ("作业", "学习", "上课", "上学", "缺课", "考试", "成绩", "拖延"),
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


def _need_confidence(name: str, text: str, hits: int) -> float:
    direct_patterns = {
        "belonging": r"(喜欢|享受|重要|离不开).{0,8}(队友|朋友|开黑|一起玩)|和.{0,6}(队友|朋友).{0,6}(一起|玩)",
        "achievement": r"(喜欢|享受|最爽|满足|有成就感).{0,10}(上分|赢|击杀|虐杀|压制|操作|团战|段位|翻盘)|(上分|赢|击杀|虐杀|压制|操作|团战|段位|翻盘).{0,10}(喜欢|享受|最爽|满足|成就感)",
        "autonomy": r"(我想|我希望|对我重要).{0,8}(自己决定|自主)|讨厌.{0,8}(控制|没收)",
        "relaxation": r"(让我|为了|主要是|就是为了).{0,6}(放松|解压|缓一缓)",
        "escape": r"(为了|只能|主要是).{0,8}(逃避|不想面对|忘掉|躲一会)",
        "connection": r"(让我|因为).{0,8}(不孤独|有人理|被需要|有人聊天)",
    }
    if re.search(direct_patterns[name], text):
        return min(0.84 + max(0, hits - 1) * 0.04, 0.96)
    return min(0.55 + hits * 0.08, 0.76)


def _needs(text: str) -> list[PsychologicalNeed]:
    found: list[PsychologicalNeed] = []
    for name, keywords in NEED_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits:
            found.append(
                PsychologicalNeed(
                    name=name,
                    confidence=_need_confidence(name, text, hits),
                )
            )
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
    *,
    correction: bool,
    neutral_first_turn: bool,
) -> ConversationStage:
    if correction or neutral_first_turn:
        return ConversationStage.ENGAGE
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
    *,
    correction: bool,
) -> list[MIStrategy]:
    if correction:
        return [MIStrategy.SIMPLE_REFLECTION, MIStrategy.OPEN_QUESTION]
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

    correction = is_user_correction(text)
    neutral_first_turn = is_neutral_preference(text) and not state.messages
    previous = None if correction or neutral_first_turn else state.analysis

    focus_topic = None if correction or neutral_first_turn else _first_matching_topic(text)
    if focus_topic is None and previous is not None:
        focus_topic = previous.focus_topic

    current_needs = [] if correction or neutral_first_turn else _needs(text)
    psychological_needs = current_needs or (previous.psychological_needs if previous else [])

    current_emotions = [
        word
        for word in ("烦躁", "焦虑", "低落", "孤独", "压力", "绝望")
        if word in text
    ]
    emotions = (
        []
        if correction or neutral_first_turn
        else current_emotions
        or (previous.emotions if previous and len(text.strip()) <= 3 else [])
    )

    change_talk = [] if correction else _extract(CHANGE_PATTERNS, text)
    sustain_talk = [] if correction else _extract(SUSTAIN_PATTERNS, text)
    bare_score = None if correction else _bare_ruler_score(state, text)
    stage = _choose_stage(
        state,
        focus_topic,
        change_talk,
        text,
        bare_score,
        correction=correction,
        neutral_first_turn=neutral_first_turn,
    )
    strategies = _choose_strategies(
        stage,
        change_talk,
        sustain_talk,
        bare_score,
        correction=correction,
    )

    ruler_match = RULER_PATTERN.search(text)
    explicit_score = int(ruler_match.group(1)) if ruler_match else None
    confidence = explicit_score if ruler_match and "信心" in text else None
    importance = explicit_score if ruler_match and "信心" not in text else bare_score

    rag_required = bool(
        not correction
        and not neutral_first_turn
        and (
            stage in {ConversationStage.PLAN, ConversationStage.REVIEW}
            or re.search(r"(怎么办|怎么做|方法|建议|睡眠|焦虑|压力)", text)
        )
    )

    if correction:
        summary = "用户明确纠正了系统上一轮的推断，旧假设应被撤回"
    elif neutral_first_turn:
        summary = "用户只表达了游戏偏好，尚未提到困扰、影响或心理需要"
    elif bare_score is not None:
        summary = f"用户给出了 {bare_score}/10 的改变意愿评分"
    else:
        summary = f"用户正在讨论{focus_topic or '游戏与生活的关系'}"

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
            "承认推断过度、撤回旧假设并重新理解用户原意"
            if correction
            else "只探索用户明确表达的游戏偏好，不推断问题或心理需要"
            if neutral_first_turn
            else "理解评分背后的理由，不推动用户过快进入计划"
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
