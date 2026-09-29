import json
import logging

from httpx import ASGITransport, AsyncClient

import noname.main as main_module
from noname.llm import GeneratedReply, SafetyTurnUnderstanding
from noname.rag import KnowledgeStore
from noname.schemas import ChatRequest
from noname.service import ConversationService


class DisabledLLM:
    enabled = False

    async def analyze(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def generate_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def analyze_safety_turn(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    async def generate_safety_reply(self, *args, **kwargs):  # noqa: ANN002, ANN003
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
    assert "不想" in second.reply
    assert "告诉" in second.reply
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



class ContextSafetyLLM(DisabledLLM):
    def __init__(self) -> None:
        self.safety_history_lengths: list[int] = []

    async def analyze_safety_turn(self, state, message, safety_state):  # noqa: ANN001
        self.safety_history_lengths.append(len(state.messages))
        if message.strip() == "有":
            return SafetyTurnUnderstanding(
                trusted_person_present=True,
                alone=False,
                interpretation="用户在回答上一轮关于身边是否有人陪伴的问题",
            )
        return None

    async def generate_safety_reply(self, state, message, safety_state, risk):  # noqa: ANN001
        if safety_state.trusted_person_present is True:
            return GeneratedReply(
                reply=(
                    "好，安全上先和身边这个人待在一起。你刚才的“有”我理解为身边现在有人陪着，"
                    "所以不用再重复确认这一点。接下来只需要确认你现在有没有正在伤害自己或准备马上行动。"
                ),
                quick_replies=["没有", "有这样的情况", "我不确定"],
            )
        return None


async def test_safety_llm_reads_previous_turn_for_short_answer() -> None:
    llm = ContextSafetyLLM()
    service = ConversationService(llm=llm, knowledge=KnowledgeStore())
    session_id = "final-version-safety-short-context"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我现在就想割腕",
            reviewer_mode=True,
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="有",
            reviewer_mode=True,
        )
    )

    state = service.sessions.get_or_create(session_id)
    assert len(llm.safety_history_lengths) == 2
    assert llm.safety_history_lengths[0] == 0
    assert llm.safety_history_lengths[1] >= 2
    assert state.safety_state.active is True
    assert state.safety_state.trusted_person_present is True
    assert state.safety_state.alone is False
    assert response.trace is not None
    assert response.trace.stage.value == "SAFETY"
    assert "不用再重复确认" in response.reply


async def test_offline_safety_fallback_understands_short_no_from_previous_question() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-safety-short-no"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我想割腕",
            reviewer_mode=True,
        )
    )
    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我身边有人",
            reviewer_mode=True,
        )
    )
    third = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="没有",
            reviewer_mode=True,
        )
    )

    state = service.sessions.get_or_create(session_id)
    assert third.trace is not None
    assert third.trace.stage.value == "SAFETY"
    assert state.safety_state.trusted_person_present is True
    assert state.safety_state.currently_injuring is False
    assert state.safety_state.immediate_plan is False
    assert "伤害自己的想法" in third.reply



class SummaryLLM(DisabledLLM):
    def __init__(self) -> None:
        self.summary_calls = 0
        self.last_summary_message_count = 0

    async def summarize_history(self, existing_summary, messages_to_summarize):  # noqa: ANN001
        self.summary_calls += 1
        self.last_summary_message_count = len(messages_to_summarize)
        return (
            "用户长期提到游戏是日常兴趣；当前没有需要长期保存的额外心理推断。"
            "后续应继续以用户明确表达为准。"
        )


async def test_long_conversation_compacts_into_rolling_summary() -> None:
    llm = SummaryLLM()
    service = ConversationService(llm=llm, knowledge=KnowledgeStore())
    session_id = "final-version-long-memory"

    for index in range(14):
        await service.chat(
            ChatRequest(
                session_id=session_id,
                message=f"这是第{index + 1}轮，我今天玩了一会儿游戏",
                reviewer_mode=True,
            )
        )

    state = service.sessions.get_or_create(session_id)
    assert llm.summary_calls >= 1
    assert llm.last_summary_message_count > 0
    assert state.conversation_summary
    assert state.summary_compactions >= 1
    assert len(state.messages) <= 16


async def test_backend_logs_turn_state_without_logging_user_text(caplog) -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    caplog.set_level(logging.INFO, logger="noname.service")

    await service.chat(
        ChatRequest(
            session_id="final-version-log-state",
            message="这是一句不应该直接出现在状态日志里的测试文本",
            reviewer_mode=True,
        )
    )

    messages = [record.getMessage() for record in caplog.records]
    turn_lines = [message for message in messages if "TURN_STATE" in message]
    assert turn_lines
    assert any("stage=" in message and "risk=" in message and "strategies=" in message for message in turn_lines)
    assert all("这是一句不应该直接出现在状态日志里的测试文本" not in message for message in turn_lines)



class StreamDemoService:
    async def chat(self, request):  # noqa: ANN001
        from noname.schemas import ChatResponse

        return ChatResponse(
            session_id=request.session_id,
            reply="这是一条经过审核后再流式展示的测试回复。",
            quick_replies=["继续聊", "重新开始"],
            action_plan=None,
            trace=None,
        )


async def test_stream_endpoint_emits_ordered_ndjson_events(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "service", StreamDemoService())

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat/stream",
            json={
                "session_id": "final-version-stream",
                "message": "测试流式输出",
                "reviewer_mode": True,
            },
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [event["type"] for event in events]

    assert event_types[0] == "start"
    assert "meta" in event_types
    assert "delta" in event_types
    assert event_types[-1] == "done"

    streamed_reply = "".join(
        event["text"] for event in events if event["type"] == "delta"
    )
    assert streamed_reply == events[-1]["data"]["reply"]



async def test_repeated_game_value_exploration_bridges_back_to_original_sleep_concern() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-primary-focus-bridge"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="最近总是玩到很晚",
            reviewer_mode=True,
        )
    )
    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我就是喜欢玩",
            reviewer_mode=True,
        )
    )
    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="王者荣耀",
            reviewer_mode=True,
        )
    )
    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="朋友一起玩",
            reviewer_mode=True,
        )
    )
    bridged = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="我喜欢团队合作",
            reviewer_mode=True,
        )
    )

    state = service.sessions.get_or_create(session_id)
    assert state.primary_focus_topic == "sleep"
    assert state.primary_focus_excerpt == "最近总是玩到很晚"
    assert state.last_anchor_bridge_user_turn == state.user_turn_count
    assert bridged.trace is not None
    assert bridged.trace.stage.value == "FOCUS"
    assert bridged.trace.focus_topic == "sleep"
    assert "朋友" in bridged.reply
    assert "最开始" in bridged.reply
    assert "最近总是玩到很晚" in bridged.reply
    assert "特别的意义" not in bridged.reply
    assert "最满足" not in bridged.reply



async def test_natural_time_reduction_phrase_creates_action_plan() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-natural-time-reduction"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="最近总是玩到很晚",
            reviewer_mode=True,
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="每天少玩半个小时可以吗",
            reviewer_mode=True,
        )
    )

    assert response.action_plan is not None
    assert response.action_plan.title == "减少游戏时间小实验"
    assert "少玩半个小时" in response.action_plan.behavior
    assert "三天" in response.action_plan.duration


async def test_round_break_phrase_updates_action_plan_with_user_strategy() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-round-break-plan"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="最近总是玩到很晚",
            reviewer_mode=True,
        )
    )
    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="每天少玩半个小时可以吗",
            reviewer_mode=True,
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="玩一局后休息几分钟，再考虑还继续玩",
            reviewer_mode=True,
        )
    )

    assert response.action_plan is not None
    assert response.action_plan.title == "游戏节奏小实验"
    assert "少玩半个小时" in response.action_plan.behavior
    assert "每局结束后先休息几分钟" in response.action_plan.behavior


async def test_asking_for_methods_alone_does_not_create_action_plan() -> None:
    service = ConversationService(llm=DisabledLLM(), knowledge=KnowledgeStore())
    session_id = "final-version-method-question-no-plan"

    await service.chat(
        ChatRequest(
            session_id=session_id,
            message="最近总是玩到很晚",
            reviewer_mode=True,
        )
    )
    response = await service.chat(
        ChatRequest(
            session_id=session_id,
            message="有没有具体一点的方法",
            reviewer_mode=True,
        )
    )

    assert response.action_plan is None
