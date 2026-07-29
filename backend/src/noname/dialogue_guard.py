from __future__ import annotations

import re

from .llm import GeneratedReply
from .schemas import ConversationAnalysis, ConversationStage

CORRECTION_PATTERN = re.compile(
    r"(我没说|我没有说|我只是说|不是这个意思|你理解错了|你误会了|你想多了|别给我贴标签|不要替我猜)"
)
NEUTRAL_PREFERENCE_PATTERN = re.compile(
    r"^(?:我)?(?:很|挺|特别|比较)?(?:喜欢|爱玩|常玩|经常玩|平时玩|觉得.{0,8}好玩).{0,24}$"
)
IMPACT_PATTERN = re.compile(
    r"(停不下来|控制不住|熬夜|困|作业|学习|上课|父母|爸妈|吵架|焦虑|压力|难受|孤独|低落|绝望|没意义|想改变|少玩|戒掉)"
)
COMPETITIVE_PATTERN = re.compile(
    r"(王者荣耀|上分|段位|击杀|虐杀|压制|对面|团战|操作|翻盘|赢下|排位|竞技)"
)
SOCIAL_PATTERN = re.compile(r"(队友|朋友|开黑|一起玩|组队|战队)")


def is_user_correction(text: str) -> bool:
    return bool(CORRECTION_PATTERN.search(text))


def is_neutral_preference(text: str) -> bool:
    cleaned = re.sub(r"[。！!？?，,\s]+", "", text)
    return bool(NEUTRAL_PREFERENCE_PATTERN.fullmatch(cleaned)) and not IMPACT_PATTERN.search(text)


def correction_reply() -> GeneratedReply:
    return GeneratedReply(
        reply=(
            "你说得对，是我刚才推断多了。你只是表达了自己喜欢这款游戏，我不该替你加上别的意思。"
            "我们重新来：你最享受的是操作和对抗、上分的成就感、和朋友一起玩，还是其他部分？"
        ),
        quick_replies=["操作和对抗", "上分成就感", "和朋友开黑", "还有别的"],
    )


def neutral_preference_reply(text: str) -> GeneratedReply:
    game = "这款游戏"
    for candidate in ("王者荣耀", "英雄联盟", "和平精英", "原神", "第五人格", "蛋仔派对"):
        if candidate in text:
            game = candidate
            break
    return GeneratedReply(
        reply=(
            f"听起来你挺喜欢{game}。最吸引你的是操作和对抗、上分或完成目标的成就感、"
            "和朋友一起玩，还是其他部分？"
        ),
        quick_replies=["操作和对抗", "上分有成就感", "和朋友一起玩", "还有别的"],
    )


def align_quick_replies(
    message: str,
    analysis: ConversationAnalysis,
    replies: list[str],
) -> list[str]:
    if is_user_correction(message):
        return correction_reply().quick_replies
    if COMPETITIVE_PATTERN.search(message):
        return ["操作成功最爽", "喜欢压制对手", "上分有成就感", "赢下团战最开心"]
    if SOCIAL_PATTERN.search(message) and analysis.stage in {
        ConversationStage.ENGAGE,
        ConversationStage.FOCUS,
    }:
        return ["一起玩更有意思", "队友让我有归属感", "有时也会有矛盾", "我更喜欢单排"]
    return replies[:4]
