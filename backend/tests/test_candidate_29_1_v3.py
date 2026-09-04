from noname.rag import KnowledgeStore
from noname.schemas import ChatRequest, ConversationStage
from noname.service import ConversationService


class DisabledLLM:
    enabled = False

    async def analyze(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def generate_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


async def test_engage_fallback_advances_from_explicit_ranked_win_preference() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "candidate-29-1-v3-ranked-win"

    await service.chat(
        ChatRequest(session_id=session_id, message="我爱玩王者荣耀")
    )
    await service.chat(
        ChatRequest(session_id=session_id, message="我就是很喜欢玩游戏")
    )
    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我主要就是喜欢排位上分，赢了很爽",
            reviewer_mode=True,
        )
    )

    assert response.trace is not None
    assert response.trace.stage is ConversationStage.ENGAGE
    assert response.trace.fallback_used is True
    assert "排位" in response.reply
    assert "上分" in response.reply
    assert "赢" in response.reply
    assert "最吸引你的是什么" not in response.reply
    assert "特别的意义" not in response.reply


async def test_engage_fallback_uses_game_name_on_first_turn() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    response = await service.chat(
        ChatRequest(
            session_id="candidate-29-1-v3-game-name",
            message="我爱玩王者荣耀",
            reviewer_mode=True,
        )
    )

    assert response.trace is not None
    assert response.trace.stage is ConversationStage.ENGAGE
    assert "王者荣耀" in response.reply
    assert "认定你有问题" not in response.reply
    assert "不替你假设" not in response.reply
