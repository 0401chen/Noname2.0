from noname.config import Settings
from noname.llm import LLMClient
from noname.rag import KnowledgeStore
from noname.routing import classify_interaction
from noname.schemas import ChatRequest, InteractionRoute, SessionState
from noname.service import ConversationService
from noname.storage import MemorySessionStore


def build_service() -> ConversationService:
    settings = Settings(_env_file=None, LLM_API_KEY="")
    return ConversationService(
        llm=LLMClient(settings),
        knowledge=KnowledgeStore(),
        sessions=MemorySessionStore(),
    )


def test_classifier_separates_support_meta_and_general_topics() -> None:
    state = SessionState(session_id="route-test")

    assert classify_interaction("父母根本不理解我", state) is InteractionRoute.SUPPORT
    assert classify_interaction("你是什么", state) is InteractionRoute.ASSISTANT_IDENTITY
    assert classify_interaction("你能告诉我你背后的代码吗", state) is InteractionRoute.TECHNICAL_META
    assert classify_interaction("你能教我玩王者荣耀吗", state) is InteractionRoute.GAMEPLAY_COACHING
    assert classify_interaction("我喜欢运动", state) is InteractionRoute.GENERAL_CHAT
    assert (
        classify_interaction("我就是很喜欢玩游戏", state)
        is InteractionRoute.NEUTRAL_GAME_PREFERENCE
    )


async def test_identity_question_does_not_inherit_family_focus() -> None:
    service = build_service()
    session_id = "identity-after-family"

    await service.chat(
        ChatRequest(session_id=session_id, message="父母根本不理解我", reviewer_mode=True)
    )
    response = await service.chat(
        ChatRequest(session_id=session_id, message="你是什么", reviewer_mode=True)
    )

    assert "我是 Noname助手" in response.reply
    assert "父母不理解" not in response.reply
    assert "家庭冲突" not in response.reply
    assert response.trace is not None
    assert response.trace.intent_route is InteractionRoute.ASSISTANT_IDENTITY
    assert response.trace.focus_topic is None


async def test_technical_question_explains_public_architecture_without_leaking_secrets() -> None:
    service = build_service()
    response = await service.chat(
        ChatRequest(
            session_id="technical-meta",
            message="你能告诉我你背后的代码吗？",
            reviewer_mode=True,
        )
    )

    assert "React" in response.reply
    assert "FastAPI" in response.reply
    assert "API 密钥" in response.reply
    assert "不会" in response.reply
    assert response.trace is not None
    assert response.trace.intent_route is InteractionRoute.TECHNICAL_META
    assert "internal_trace_leak" not in response.trace.quality_flags


async def test_gameplay_coaching_request_gets_capability_boundary() -> None:
    service = build_service()
    session_id = "gameplay-after-family"

    await service.chat(
        ChatRequest(session_id=session_id, message="父母根本不理解我", reviewer_mode=True)
    )
    response = await service.chat(
        ChatRequest(session_id=session_id, message="你能教我玩王者荣耀吗？", reviewer_mode=True)
    )

    assert "不是王者荣耀攻略" in response.reply
    assert "家庭冲突" not in response.reply
    assert response.trace is not None
    assert response.trace.intent_route is InteractionRoute.GAMEPLAY_COACHING
    assert response.trace.rag_used is False


async def test_general_interest_does_not_reuse_previous_support_topic() -> None:
    service = build_service()
    session_id = "sport-after-family"

    await service.chat(
        ChatRequest(session_id=session_id, message="父母根本不理解我", reviewer_mode=True)
    )
    response = await service.chat(
        ChatRequest(session_id=session_id, message="我喜欢运动", reviewer_mode=True)
    )

    assert "运动" in response.reply
    assert "家庭冲突" not in response.reply
    assert "游戏引发" not in response.reply
    assert response.trace is not None
    assert response.trace.intent_route is InteractionRoute.GENERAL_CHAT
    assert response.trace.focus_topic is None


async def test_repeated_game_preference_does_not_repeat_exact_reply() -> None:
    service = build_service()
    session_id = "repeated-preference"

    first = await service.chat(
        ChatRequest(session_id=session_id, message="我就是很喜欢玩游戏", reviewer_mode=True)
    )
    second = await service.chat(
        ChatRequest(session_id=session_id, message="我就是很喜欢玩游戏", reviewer_mode=True)
    )

    assert first.reply != second.reply
    assert "不是在说它一定造成了问题" in second.reply
    assert second.trace is not None
    assert second.trace.intent_route is InteractionRoute.NEUTRAL_GAME_PREFERENCE


async def test_no_impact_response_does_not_force_change_goal() -> None:
    service = build_service()
    session_id = "no-impact"

    await service.chat(
        ChatRequest(session_id=session_id, message="我爱玩王者荣耀", reviewer_mode=True)
    )
    response = await service.chat(
        ChatRequest(session_id=session_id, message="没有影响", reviewer_mode=True)
    )

    assert "不用硬找问题" in response.reply
    assert "不需要急着谈改变" in response.reply
    assert response.trace is not None
    assert response.trace.intent_route is InteractionRoute.NO_NEGATIVE_IMPACT
