from __future__ import annotations

import re
from difflib import SequenceMatcher

from .dialogue_guard import is_neutral_preference, is_user_correction, neutral_preference_reply
from .llm import GeneratedReply
from .schemas import (
    ConversationAnalysis,
    ConversationStage,
    InteractionRoute,
    MIStrategy,
    RiskAssessment,
    SessionState,
)

IDENTITY_PATTERN = re.compile(
    r"(你是谁|你是什么(?:东西)?|你是干什么的|介绍一下你|你能做什么|你有什么用|你是机器人吗)"
)
TECHNICAL_META_PATTERN = re.compile(
    r"(背后的代码|源代码|代码怎么写|系统提示词|提示词|prompt|内部运作|怎么实现|用了什么模型|用的什么模型|API.?Key|密钥|开发者指令)"
    ,
    re.IGNORECASE,
)
GAMEPLAY_COACHING_PATTERN = re.compile(
    r"(教我.{0,10}(玩|打).{0,16}(王者荣耀|王者|游戏)|"
    r"(王者荣耀|王者).{0,12}(怎么玩|攻略|出装|铭文|连招|上分技巧)|"
    r"怎么.{0,12}(出装|配铭文|连招|上分|练英雄))"
)
NO_NEGATIVE_IMPACT_PATTERN = re.compile(
    r"^\s*(没有影响|没影响|没有什么影响|没什么影响|不影响|没有负面影响|没造成影响)\s*[。.!！]?$"
)
SUPPORT_PATTERN = re.compile(
    r"(游戏|手游|网游|王者|上分|段位|队友|开黑|熬夜|睡|困|停不下来|控制不住|"
    r"作业|学习|上课|成绩|拖延|父母|爸妈|家庭|吵架|不理解|焦虑|压力|难受|"
    r"孤独|低落|情绪|绝望|没意义|欺负|霸凌|朋友|同学|没人懂|少玩|改变|自责|"
    r"烦躁|生气|害怕|紧张|失眠|手机|网络|被骂|骂我|打我|活着|自杀|自伤)"
)
CONTEXTUAL_SHORT_PATTERN = re.compile(
    r"^\s*(是|不是|有|没有|不知道|不确定|还好|一点|很多|因为|就是|可能|嗯|对|"
    r"不对|继续|不想说|先不说|他们|他|她|这样|那样|为什么|怎么办).{0,12}\s*$"
)
SPORT_PATTERN = re.compile(r"(运动|跑步|篮球|足球|羽毛球|乒乓球|游泳|健身|骑车|跳绳)")
MUSIC_PATTERN = re.compile(r"(音乐|唱歌|听歌|乐器|吉他|钢琴)" )
READING_PATTERN = re.compile(r"(看书|阅读|小说|漫画)" )
ART_PATTERN = re.compile(r"(画画|绘画|摄影|手工)" )
REALTIME_PATTERN = re.compile(r"(今天|现在|实时).{0,8}(天气|新闻|比赛|价格|汇率|几点)" )


def classify_interaction(text: str, state: SessionState) -> InteractionRoute:
    if is_user_correction(text):
        return InteractionRoute.USER_CORRECTION
    if IDENTITY_PATTERN.search(text):
        return InteractionRoute.ASSISTANT_IDENTITY
    if TECHNICAL_META_PATTERN.search(text):
        return InteractionRoute.TECHNICAL_META
    if GAMEPLAY_COACHING_PATTERN.search(text):
        return InteractionRoute.GAMEPLAY_COACHING
    if NO_NEGATIVE_IMPACT_PATTERN.fullmatch(text):
        return InteractionRoute.NO_NEGATIVE_IMPACT
    if is_neutral_preference(text):
        return InteractionRoute.NEUTRAL_GAME_PREFERENCE
    if SUPPORT_PATTERN.search(text):
        return InteractionRoute.SUPPORT
    if state.messages and CONTEXTUAL_SHORT_PATTERN.fullmatch(text):
        return InteractionRoute.SUPPORT
    return InteractionRoute.GENERAL_CHAT


def route_analysis(route: InteractionRoute, risk: RiskAssessment) -> ConversationAnalysis:
    summaries = {
        InteractionRoute.NEUTRAL_GAME_PREFERENCE: "用户表达游戏偏好，尚未说明负面影响",
        InteractionRoute.NO_NEGATIVE_IMPACT: "用户明确表示目前没有感到负面影响",
        InteractionRoute.USER_CORRECTION: "用户纠正了系统之前的推断",
        InteractionRoute.ASSISTANT_IDENTITY: "用户询问助手身份与能力边界",
        InteractionRoute.TECHNICAL_META: "用户询问系统技术实现或内部信息",
        InteractionRoute.GAMEPLAY_COACHING: "用户请求具体游戏攻略或操作教学",
        InteractionRoute.GENERAL_CHAT: "用户切换到一般话题",
        InteractionRoute.SUPPORT: "用户进入游戏与生活心理支持主流程",
    }
    strategies = (
        [MIStrategy.SIMPLE_REFLECTION, MIStrategy.OPEN_QUESTION]
        if route in {
            InteractionRoute.NEUTRAL_GAME_PREFERENCE,
            InteractionRoute.NO_NEGATIVE_IMPACT,
            InteractionRoute.GENERAL_CHAT,
        }
        else []
    )
    return ConversationAnalysis(
        summary=summaries[route],
        stage=ConversationStage.ENGAGE,
        risk=risk,
        mi_strategies=strategies,
        next_goal="直接回应用户当前消息，不继承无关的旧主题",
    )


def should_replace_saved_analysis(route: InteractionRoute) -> bool:
    return route in {
        InteractionRoute.NEUTRAL_GAME_PREFERENCE,
        InteractionRoute.NO_NEGATIVE_IMPACT,
        InteractionRoute.USER_CORRECTION,
    }


def _previous_user_messages(state: SessionState) -> list[str]:
    return [item.content for item in state.messages if item.role == "user"]


def neutral_preference_route_reply(text: str, state: SessionState) -> GeneratedReply:
    repeated = any(_similar(previous, text) >= 0.82 for previous in _previous_user_messages(state)[-4:])
    return neutral_preference_reply(text, repeated=repeated)


def no_negative_impact_reply() -> GeneratedReply:
    return GeneratedReply(
        reply=(
            "明白，你目前没有感觉游戏给生活带来负面影响，那就不用硬找问题，也不需要急着谈改变。"
            "我们可以继续聊你喜欢的游戏体验，也可以换个你感兴趣的话题。"
        ),
        quick_replies=["聊聊喜欢的玩法", "我也喜欢运动", "换个话题", "先随便聊聊"],
    )


def identity_reply() -> GeneratedReply:
    return GeneratedReply(
        reply=(
            "我是 Noname助手，一个面向青少年的游戏与生活平衡心理支持原型。"
            "我可以陪你聊游戏、情绪、学习、家庭和队友关系，但我不是医生、现实救援人员，也不是全能问答或游戏代练工具。"
        ),
        quick_replies=["你能帮我什么", "隐私怎么处理", "聊聊游戏", "换个话题"],
    )


def technical_meta_reply() -> GeneratedReply:
    return GeneratedReply(
        reply=(
            "可以介绍公开的整体架构：前端使用 React，后端使用 FastAPI，核心由动机式访谈、"
            "本地 RAG、语言模型和安全规则组成。出于安全考虑，我不会在对话中展示系统提示词、API 密钥或内部安全配置。"
        ),
        quick_replies=["介绍MI流程", "介绍RAG", "介绍安全机制", "继续聊天"],
    )


def gameplay_coaching_reply() -> GeneratedReply:
    return GeneratedReply(
        reply=(
            "我不是王者荣耀攻略或实时操作教练，不能可靠地提供随版本变化的英雄、出装和铭文教学。"
            "我更擅长陪你聊上分压力、队友关系、游戏时间，或把你想练习的目标拆成一个小计划。"
        ),
        quick_replies=["聊上分压力", "聊队友关系", "做练习计划", "我只是想随便聊"],
    )


def general_chat_fallback(text: str) -> GeneratedReply:
    if SPORT_PATTERN.search(text):
        return GeneratedReply(
            reply="运动也是你喜欢的事。你更喜欢球类、跑步、游泳、健身，还是其他运动？",
            quick_replies=["球类运动", "跑步", "游泳", "还有别的"],
        )
    if MUSIC_PATTERN.search(text):
        return GeneratedReply(
            reply="音乐也很适合聊。你更喜欢听歌、唱歌，还是自己弹奏乐器？",
            quick_replies=["听歌", "唱歌", "弹乐器", "都喜欢"],
        )
    if READING_PATTERN.search(text):
        return GeneratedReply(
            reply="阅读也是一种很个人的兴趣。你最近更喜欢小说、漫画，还是其他类型？",
            quick_replies=["小说", "漫画", "科普", "随便看看"],
        )
    if ART_PATTERN.search(text):
        return GeneratedReply(
            reply="这个话题可以聊。你更享受创作的过程，还是完成作品后的感觉？",
            quick_replies=["创作过程", "完成作品", "只是放松", "还说不清"],
        )
    if REALTIME_PATTERN.search(text):
        return GeneratedReply(
            reply=(
                "我在这个比赛原型里没有可靠的实时信息查询能力，所以不应该猜测当前天气、新闻、价格或赛程。"
                "你可以换一个不依赖实时数据的话题，我会直接回应。"
            ),
            quick_replies=["聊兴趣", "聊学习", "聊游戏", "聊心情"],
        )
    return GeneratedReply(
        reply=(
            "可以，我们先回应你刚提到的这个话题，不必强行拉回游戏或家庭问题。"
            "你最希望我回答哪一部分？"
        ),
        quick_replies=["直接回答问题", "先听我说", "聊兴趣", "换个话题"],
    )


def direct_route_reply(
    route: InteractionRoute,
    text: str,
    state: SessionState,
) -> GeneratedReply:
    if route is InteractionRoute.NEUTRAL_GAME_PREFERENCE:
        return neutral_preference_route_reply(text, state)
    if route is InteractionRoute.NO_NEGATIVE_IMPACT:
        return no_negative_impact_reply()
    if route is InteractionRoute.USER_CORRECTION:
        from .dialogue_guard import correction_reply

        return correction_reply()
    if route is InteractionRoute.ASSISTANT_IDENTITY:
        return identity_reply()
    if route is InteractionRoute.TECHNICAL_META:
        return technical_meta_reply()
    if route is InteractionRoute.GAMEPLAY_COACHING:
        return gameplay_coaching_reply()
    return general_chat_fallback(text)


def is_repetitive_reply(state: SessionState, reply: str) -> bool:
    previous = next(
        (item.content for item in reversed(state.messages) if item.role == "assistant"),
        None,
    )
    return previous is not None and _similar(previous, reply) >= 0.9


def repair_repetitive_reply(
    route: InteractionRoute,
    text: str,
    analysis: ConversationAnalysis,
) -> GeneratedReply:
    if route is not InteractionRoute.SUPPORT:
        return general_chat_fallback(text)
    focus = {
        "sleep": "睡眠",
        "stopping": "停不下来",
        "school": "学习",
        "family": "家庭关系",
        "emotion": "情绪",
        "social": "队友关系",
    }.get(analysis.focus_topic or "", "这件事")
    return GeneratedReply(
        reply=(
            f"我不想重复刚才的说法。你这次强调的是{focus}本身。"
            "你希望我先听你把情况说完整，还是和你一起想一个具体办法？"
        ),
        quick_replies=["先听我说", "一起想办法", "换个角度", "先不聊这个"],
    )


def _similar(left: str, right: str) -> float:
    normalize = lambda value: re.sub(r"[\s，。！？、；：,.!?;:]", "", value).lower()
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()
