from noname.llm import GeneratedReply
from noname.quality import review_reply
from noname.rag import KnowledgeStore
from noname.schemas import ChatRequest, ConversationAnalysis, RiskAssessment, RiskLevel
from noname.service import ConversationService


class DisabledLLM:
    enabled = False
    last_analysis_mode = "disabled"

    async def analyze(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def generate_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


async def test_neutral_game_preference_does_not_invent_a_problem() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    response = await service.chat(
        ChatRequest(
            session_id="neutral-preference",
            message="我爱玩王者荣耀",
            reviewer_mode=True,
        )
    )

    assert "王者荣耀" in response.reply
    assert "认定你有问题" not in response.reply
    assert response.trace is not None
    assert response.trace.focus_topic is None
    assert response.trace.psychological_needs == []
    assert response.quick_replies == ["操作成功最爽", "喜欢压制对手", "上分有成就感", "赢下团战最开心"]


async def test_user_correction_rolls_back_previous_social_hypothesis() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    await service.chat(
        ChatRequest(
            session_id="correction-demo",
            message="我喜欢和队友一起开黑",
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id="correction-demo",
            message="我没说不希望别人看到我玩游戏就认定我有问题",
            reviewer_mode=True,
        )
    )

    assert response.reply.startswith("你说得对")
    assert response.trace is not None
    assert response.trace.focus_topic is None
    assert response.trace.psychological_needs == []
    assert response.quick_replies == ["操作和对抗", "上分成就感", "和朋友开黑", "还有别的"]


async def test_competitive_enjoyment_is_confirmed_as_achievement_not_real_world_violence() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    response = await service.chat(
        ChatRequest(
            session_id="competitive-demo",
            message="我享受虐杀对面的快感",
            reviewer_mode=True,
        )
    )

    assert response.trace is not None
    achievement = next(
        need for need in response.trace.psychological_needs if need.name == "achievement"
    )
    assert achievement.confidence >= 0.8
    assert response.trace.risk.level is RiskLevel.LOW
    assert response.quick_replies[0] == "操作成功最爽"


def test_unconditional_positive_gaming_claim_is_rejected() -> None:
    analysis = ConversationAnalysis(
        summary="用户正在探索游戏偏好",
        risk=RiskAssessment(level=RiskLevel.LOW),
    )
    reply = GeneratedReply(
        reply="听起来你很喜欢它。游戏确实是一个很好的放松和社交方式。",
        quick_replies=["继续聊聊"],
    )

    assert "overgeneralized_positive_claim" in review_reply(reply.reply, analysis)
