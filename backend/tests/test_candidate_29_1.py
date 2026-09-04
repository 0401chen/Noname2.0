from noname.rag import KnowledgeStore
from noname.schemas import ChatRequest, ConversationStage
from noname.service import ConversationService


class SpyLLM:
    enabled = True

    def __init__(self) -> None:
        self.analyze_calls = 0
        self.generate_calls = 0

    async def analyze(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.analyze_calls += 1
        return None

    async def generate_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.generate_calls += 1
        return None


async def test_neutral_first_turn_game_preference_does_not_infer_a_problem() -> None:
    llm = SpyLLM()
    service = ConversationService(llm=llm, knowledge=KnowledgeStore())

    response = await service.chat(
        ChatRequest(
            session_id="candidate-29-1-neutral",
            message="我爱玩王者荣耀",
            reviewer_mode=True,
        )
    )

    assert llm.analyze_calls == 0
    assert llm.generate_calls == 0
    assert "不假设" in response.reply
    assert "别人一看到" not in response.reply
    assert "认定你有问题" not in response.reply
    assert response.trace is not None
    assert response.trace.stage is ConversationStage.ENGAGE
    assert response.trace.focus_topic is None
    assert response.trace.psychological_needs == []


async def test_game_preference_with_real_impact_keeps_original_full_pipeline() -> None:
    llm = SpyLLM()
    service = ConversationService(llm=llm, knowledge=KnowledgeStore())

    response = await service.chat(
        ChatRequest(
            session_id="candidate-29-1-impact",
            message="我喜欢玩王者荣耀，但最近总玩到凌晨两点，第二天上课很困",
            reviewer_mode=True,
        )
    )

    assert llm.analyze_calls == 1
    assert llm.generate_calls == 1
    assert response.trace is not None
    assert response.trace.focus_topic == "sleep"
