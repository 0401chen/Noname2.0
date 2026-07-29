from noname.rag import KnowledgeStore
from noname.schemas import ChatRequest, ConversationStage, RiskLevel
from noname.service import ConversationService


class DisabledLLM:
    enabled = False

    async def analyze(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def generate_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


async def test_service_runs_without_api_key_and_returns_trace() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    response = await service.chat(
        ChatRequest(
            session_id="offline-demo",
            message="队友都在等我，但我希望能早点停，第二天不要那么困",
            reviewer_mode=True,
        )
    )

    assert response.reply
    assert response.trace is not None
    assert response.trace.fallback_used is True
    assert response.trace.focus_topic == "sleep"


async def test_service_creates_small_action_plan_after_user_accepts() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    await service.chat(
        ChatRequest(
            session_id="plan-demo",
            message="我每天玩到两点，第二天很困，但队友晚上都在",
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id="plan-demo",
            message="可以试三天提前20分钟",
            reviewer_mode=True,
        )
    )

    assert response.action_plan is not None
    assert response.action_plan.confidence == 6
    assert "二十分钟" in response.action_plan.behavior
    assert response.trace is not None
    assert response.trace.stage is ConversationStage.PLAN


async def test_school_focus_creates_a_learning_start_action() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    await service.chat(
        ChatRequest(
            session_id="school-plan",
            message="我一想到作业就去打游戏，最后更自责",
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id="school-plan",
            message="我试试先做五分钟再决定要不要玩",
        )
    )

    assert response.action_plan is not None
    assert "五分钟" in response.action_plan.behavior
    assert "学习" in response.action_plan.reason


async def test_review_updates_action_plan_progress_without_shaming() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    await service.chat(
        ChatRequest(session_id="review-demo", message="我每天玩到两点，第二天很困")
    )
    await service.chat(
        ChatRequest(session_id="review-demo", message="可以试三天提前20分钟")
    )
    response = await service.chat(
        ChatRequest(
            session_id="review-demo",
            message="有一次做到了，另外两次没有",
            reviewer_mode=True,
        )
    )

    assert response.action_plan is not None
    assert response.action_plan.attempts == 1
    assert response.action_plan.successes == 1
    assert response.action_plan.last_review is not None
    assert response.trace is not None
    assert response.trace.stage is ConversationStage.REVIEW


async def test_high_risk_bypasses_normal_game_advice() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())

    response = await service.chat(
        ChatRequest(
            session_id="safety-demo",
            message="我现在无法保证自己的安全",
            reviewer_mode=True,
        )
    )

    assert response.trace is not None
    assert response.trace.risk.level is RiskLevel.HIGH
    assert response.trace.stage is ConversationStage.SAFETY
    assert "安全" in response.reply
    assert "提前" not in response.reply
