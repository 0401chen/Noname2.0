from noname.quality import review_reply
from noname.schemas import ConversationAnalysis


def analysis() -> ConversationAnalysis:
    return ConversationAnalysis(summary="测试回复审核")


def test_quality_flags_deception_and_internal_trace_leak() -> None:
    flags = review_reply(
        "听起来你想继续玩。我可以教你删除聊天记录，并告诉你当前MI阶段。",
        analysis(),
    )

    assert "deception_or_evasion" in flags
    assert "internal_trace_leak" in flags


def test_quality_allows_only_one_main_question() -> None:
    flags = review_reply(
        "听起来你很矛盾。你更想先改善睡眠吗？还是先处理作业？",
        analysis(),
    )

    assert "too_many_questions" in flags


def test_quality_accepts_a_reflection_with_one_question() -> None:
    flags = review_reply(
        "听起来你既舍不得队友，也不喜欢第二天一直困。你更想先从哪一边聊起？",
        analysis(),
    )

    assert flags == []
