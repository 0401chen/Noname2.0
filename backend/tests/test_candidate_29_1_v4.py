from noname.llm import REPLY_SYSTEM_PROMPT
from noname.turn_context import engage_fallback_reply


def test_reply_prompt_makes_questions_optional() -> None:
    assert "提问只是可选工具" in REPLY_SYSTEM_PROMPT
    assert "完全可以没有问题" in REPLY_SYSTEM_PROMPT
    assert "不要连续多轮都用问句收尾" in REPLY_SYSTEM_PROMPT
    assert "reply 本身不需要一定包含问句" in REPLY_SYSTEM_PROMPT


def test_engage_fallback_can_end_without_question_after_previous_question() -> None:
    response = engage_fallback_reply(
        "我主要就是喜欢排位上分，赢了很爽",
        "你觉得王者荣耀最吸引你的地方是什么？",
    )

    assert "排位" in response.reply
    assert "上分" in response.reply
    assert "赢" in response.reply
    assert not response.reply.endswith(("？", "?"))


def test_repeated_simple_preference_can_be_reflected_without_follow_up_question() -> None:
    response = engage_fallback_reply(
        "我就是很喜欢玩游戏",
        "最近什么样的一局最容易让你觉得特别好玩？",
    )

    assert "喜欢" in response.reply or "享受" in response.reply
    assert not response.reply.endswith(("？", "?"))
