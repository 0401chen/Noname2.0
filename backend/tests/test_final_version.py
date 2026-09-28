from noname.rag import KnowledgeStore
from noname.schemas import ChatRequest
from noname.service import ConversationService


class DisabledLLM:
    enabled = False

    async def analyze(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def generate_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


async def test_user_owned_sleep_experiment_is_created_and_reviewed() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-sleep-experiment"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我最近经常玩游戏到凌晨，第二天上课很困",
            reviewer_mode=True,
        )
    )

    planned = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我想今天晚上先不玩，看看第二天精神怎么样",
            reviewer_mode=True,
        )
    )

    assert planned.action_plan is not None
    assert planned.action_plan.title == "今晚的小实验"
    assert "暂停游戏" in planned.action_plan.behavior
    assert "第二天" in planned.action_plan.reason
    assert planned.action_plan.attempts == 0

    reviewed = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="确实，第二天我的精神很好，上课也有精神",
            reviewer_mode=True,
        )
    )

    assert reviewed.action_plan is not None
    assert reviewed.action_plan.attempts == 1
    assert reviewed.action_plan.successes == 1
    assert reviewed.action_plan.last_review is not None
    assert "积极变化" in reviewed.action_plan.last_review


async def test_time_planning_intent_creates_small_experiment() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-time-plan"

    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我想制定一个任务来帮助我安排时间",
            reviewer_mode=True,
        )
    )

    assert response.action_plan is not None
    assert response.action_plan.title == "时间安排小实验"
    assert "时间" in response.action_plan.behavior
    assert response.action_plan.status == "active"
