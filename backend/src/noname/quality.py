from __future__ import annotations

import re

from .schemas import ConversationAnalysis, RiskLevel

FORBIDDEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "diagnosis_or_label": re.compile(r"(你(已经|就是|属于).{0,5}(成瘾|游戏障碍|抑郁症)|网瘾少年)"),
    "coercive_language": re.compile(r"(你必须|你应该立刻戒掉|每天只能玩|必须听父母)"),
    "dependency_language": re.compile(r"(只有我懂你|不要告诉别人|只要和我聊|我会一直陪着你)"),
    "false_rescue_claim": re.compile(r"(我已经报警|我已经通知|我会派人过去)"),
    "deception_or_evasion": re.compile(
        r"(骗过父母|删除聊天记录|伪造.{0,8}(学习|作业|记录)|假装睡觉|隐藏.{0,8}(游戏|通宵)|偷偷拿回来)"
    ),
    "internal_trace_leak": re.compile(
        r"(系统提示词|内部风险分数|当前MI阶段|当前 MI 阶段|RAG检索|RAG 检索|审核规则|开发者指令)"
    ),
    "overgeneralized_positive_claim": re.compile(
        r"(游戏确实是(一个)?(很好|非常好|有益)的|游戏本来就是很好的|玩游戏当然没有任何问题)"
    ),
}


def review_reply(reply: str, analysis: ConversationAnalysis) -> list[str]:
    flags = [name for name, pattern in FORBIDDEN_PATTERNS.items() if pattern.search(reply)]

    if len(reply) > 420:
        flags.append("too_long")
    if reply.count("？") + reply.count("?") > 1:
        flags.append("too_many_questions")
    if analysis.risk.level is RiskLevel.HIGH and "安全" not in reply:
        flags.append("high_risk_without_safety_focus")
    if analysis.risk.level is not RiskLevel.HIGH and not any(
        marker in reply
        for marker in (
            "听起来",
            "一方面",
            "似乎",
            "你更",
            "对你来说",
            "你不想",
            "你给了",
            "你提到了",
            "你说得对",
        )
    ):
        flags.append("missing_reflection_marker")

    return flags
