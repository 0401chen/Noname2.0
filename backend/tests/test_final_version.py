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


async def test_alarm_path_updates_experiment_card_from_real_demo_conversation() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-alarm-path"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我最近经常玩游戏到凌晨",
            reviewer_mode=True,
        )
    )
    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="感觉很兴奋，但是第二天很困",
            reviewer_mode=True,
        )
    )

    earlier = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="可以提早结束",
            reviewer_mode=True,
        )
    )
    assert earlier.action_plan is not None
    assert earlier.action_plan.title == "早点结束小实验"

    alarm = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="可以设置闹钟",
            reviewer_mode=True,
        )
    )
    assert alarm.action_plan is not None
    assert alarm.action_plan.title == "早点下线小实验"
    assert "闹钟" in alarm.action_plan.behavior

    explicit = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我可以制定一个行动吗？",
            reviewer_mode=True,
        )
    )
    assert explicit.action_plan is not None
    assert explicit.action_plan.title == "早点下线小实验"
    assert "闹钟" in explicit.action_plan.behavior


async def test_high_risk_mode_persists_when_user_refuses_to_tell_someone() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-persistent-safety"

    first = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我想割腕",
            reviewer_mode=True,
        )
    )
    second = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我不想告诉别人",
            reviewer_mode=True,
        )
    )

    assert first.trace is not None
    assert second.trace is not None
    assert first.trace.stage.value == "SAFETY"
    assert first.trace.risk.level.value == "HIGH"
    assert second.trace.stage.value == "SAFETY"
    assert second.trace.risk.level.value == "HIGH"
    assert "safety_session_active" in second.trace.risk.signals
    assert "不想告诉别人" in second.reply
    assert "安全" in second.reply


async def test_high_risk_mode_blocks_normal_action_plan_creation() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-safety-block-plan"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我想割腕",
            reviewer_mode=True,
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我想制定一个行动计划",
            reviewer_mode=True,
        )
    )

    assert response.trace is not None
    assert response.trace.stage.value == "SAFETY"
    assert response.trace.risk.level.value == "HIGH"
    assert response.action_plan is None


async def test_high_risk_mode_exits_only_after_explicit_safety_confirmation() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-safety-resolution"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我想割腕",
            reviewer_mode=True,
        )
    )
    still_active = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我现在暂时安全",
            reviewer_mode=True,
        )
    )
    resolved = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我现在安全，没有伤害自己的想法，家人在我身边陪我",
            reviewer_mode=True,
        )
    )

    assert still_active.trace is not None
    assert still_active.trace.stage.value == "SAFETY"
    assert still_active.trace.risk.level.value == "HIGH"

    assert resolved.trace is not None
    assert resolved.trace.stage.value != "SAFETY"
    assert resolved.trace.risk.level.value != "HIGH"
    assert "安全情况" in resolved.reply
    assert "游戏" not in resolved.reply
