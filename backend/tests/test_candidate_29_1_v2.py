from noname.llm import ANALYSIS_SYSTEM_PROMPT
from noname.rag import KnowledgeStore
from noname.schemas import ChatRequest, ConversationStage
from noname.service import ConversationService


class DisabledLLM:
    enabled = False

    async def analyze(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def generate_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


async def test_repeated_game_preference_stays_in_engage_without_inventing_a_problem() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "candidate-29-1-v2-neutral"

    first = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我爱玩王者荣耀",
            reviewer_mode=True,
        )
    )
    second = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我就是很喜欢玩游戏",
            reviewer_mode=True,
        )
    )

    assert first.trace is not None
    assert second.trace is not None
    assert first.trace.stage is ConversationStage.ENGAGE
    assert second.trace.stage is ConversationStage.ENGAGE
    assert second.trace.focus_topic is None
    assert "王者荣耀" in first.reply
    assert "你不喜欢的影响" not in second.reply
    assert "认定你有问题" not in second.reply
    assert "不替你假设" not in first.reply
    assert "先按你现在说的来" not in first.reply
    assert "家庭" not in first.reply
    assert "孤独" not in first.reply
    assert "成瘾" not in first.reply


async def test_real_sleep_impact_still_enters_focus_after_neutral_game_talk() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "candidate-29-1-v2-impact"

    await service.chat(
        ChatRequest(session_id=session_id, message="我爱玩王者荣耀")
    )
    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="最近总玩到凌晨两点，第二天上课很困",
            reviewer_mode=True,
        )
    )

    assert response.trace is not None
    assert response.trace.stage is ConversationStage.FOCUS
    assert response.trace.focus_topic == "sleep"


def test_analysis_prompt_forbids_unsupported_inference_for_neutral_preference() -> None:
    assert "用户仅表达喜欢游戏" in ANALYSIS_SYSTEM_PROMPT
    assert "不凭空推断" in ANALYSIS_SYSTEM_PROMPT
