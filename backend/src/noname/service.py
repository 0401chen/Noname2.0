from __future__ import annotations

from datetime import datetime, timezone

from .llm import GeneratedReply, LLMClient
from .mi import heuristic_analysis
from .quality import review_reply
from .rag import KnowledgeStore
from .safety import assess_rule_risk, merge_risk, safety_reply
from .schemas import (
    ActionPlan,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationAnalysis,
    ConversationStage,
    ReviewerTrace,
    RiskLevel,
    SessionState,
)


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str, age_group: str | None = None) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(
                session_id=session_id,
                age_group=age_group,
            )
        elif age_group:
            self._sessions[session_id].age_group = age_group
        return self._sessions[session_id]

    def clear(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None


class ConversationService:
    def __init__(
        self,
        *,
        llm: LLMClient,
        knowledge: KnowledgeStore,
        sessions: InMemorySessionStore | None = None,
    ) -> None:
        self.llm = llm
        self.knowledge = knowledge
        self.sessions = sessions or InMemorySessionStore()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        state = self.sessions.get_or_create(request.session_id, request.age_group)
        rule_risk = assess_rule_risk(request.message)
        fallback_analysis = heuristic_analysis(state, request.message, rule_risk)

        semantic_analysis = None
        if rule_risk.level is not RiskLevel.HIGH:
            semantic_analysis = await self.llm.analyze(
                state,
                request.message,
                fallback_analysis,
            )

        analysis = semantic_analysis or fallback_analysis
        analysis.risk = merge_risk(rule_risk, semantic_analysis.risk if semantic_analysis else None)
        if analysis.risk.level is RiskLevel.HIGH:
            analysis.stage = ConversationStage.SAFETY
            analysis.next_goal = "确认当前安全并连接现实支持"
            analysis.rag_required = False
            analysis.rag_queries = []

        knowledge_hits = []
        if analysis.rag_required or analysis.risk.level is RiskLevel.HIGH:
            query = " ".join(
                [
                    request.message,
                    analysis.focus_topic or "",
                    *analysis.rag_queries,
                ]
            )
            knowledge_hits = self.knowledge.search(
                query,
                risk_level=analysis.risk.level,
            )

        fallback_used = False
        if analysis.risk.level is RiskLevel.HIGH:
            reply, quick_replies = safety_reply(analysis.risk)
        else:
            generated = await self.llm.generate_reply(
                state,
                request.message,
                analysis,
                knowledge_hits,
            )
            if generated is None:
                generated = self._fallback_reply(analysis, knowledge_hits)
                fallback_used = True
            reply = generated.reply
            quick_replies = generated.quick_replies

        quality_flags = review_reply(reply, analysis)
        if any(
            flag in quality_flags
            for flag in (
                "diagnosis_or_label",
                "coercive_language",
                "dependency_language",
                "false_rescue_claim",
                "high_risk_without_safety_focus",
            )
        ):
            generated = self._fallback_reply(analysis, knowledge_hits)
            reply = generated.reply
            quick_replies = generated.quick_replies
            fallback_used = True
            quality_flags = [*quality_flags, "unsafe_generation_replaced"]

        action_plan = self._maybe_create_action_plan(state, request.message, analysis)
        if action_plan is not None:
            state.action_plan = action_plan

        state.messages.append(ChatMessage(role="user", content=request.message))
        state.messages.append(ChatMessage(role="assistant", content=reply))
        state.analysis = analysis
        state.updated_at = datetime.now(timezone.utc)

        trace = None
        if request.reviewer_mode:
            trace = ReviewerTrace(
                stage=analysis.stage,
                risk=analysis.risk,
                focus_topic=analysis.focus_topic,
                emotions=analysis.emotions,
                psychological_needs=analysis.psychological_needs,
                change_talk=analysis.change_talk,
                sustain_talk=analysis.sustain_talk,
                motivation=analysis.motivation,
                mi_strategies=analysis.mi_strategies,
                rag_used=bool(knowledge_hits),
                knowledge_hits=knowledge_hits,
                quality_flags=quality_flags,
                fallback_used=fallback_used,
            )

        return ChatResponse(
            session_id=state.session_id,
            reply=reply,
            quick_replies=quick_replies,
            action_plan=state.action_plan,
            trace=trace,
        )

    def _fallback_reply(
        self,
        analysis: ConversationAnalysis,
        knowledge_hits: list,
    ) -> GeneratedReply:
        if analysis.risk.level is RiskLevel.HIGH:
            reply, quick_replies = safety_reply(analysis.risk)
            return GeneratedReply(reply=reply, quick_replies=quick_replies)

        if analysis.risk.level is RiskLevel.CONCERN:
            return GeneratedReply(
                reply=(
                    "听起来这已经不只是玩多久的问题，它正在让你承受不少压力。我们可以继续从一个小地方聊起，"
                    "同时也建议你把最近的状态告诉一位可信任的成年人。现在最影响你的是睡眠、上学，还是情绪？"
                ),
                quick_replies=["睡眠", "上学", "情绪"],
            )

        stage = analysis.stage
        focus = analysis.focus_topic
        needs = {item.name for item in analysis.psychological_needs}

        if stage is ConversationStage.ENGAGE:
            return GeneratedReply(
                reply=(
                    "听起来你不希望别人一看到你玩游戏，就直接认定你有问题。"
                    "对你来说，游戏现在更重要的是放松、和朋友在一起，还是获得成就感？"
                ),
                quick_replies=["主要是放松", "和朋友一起", "有成就感", "说不清"],
            )

        if stage is ConversationStage.FOCUS:
            focus_text = {
                "sleep": "晚上停不下来和第二天没精神",
                "stopping": "明明想停却又开下一局",
                "school": "学习压力和游戏之间的循环",
                "family": "游戏引发的家庭冲突",
                "emotion": "游戏前后的情绪变化",
                "social": "队友关系和下线边界",
            }.get(focus, "游戏带来的好处和你不喜欢的影响")
            return GeneratedReply(
                reply=(
                    f"听起来现在最值得先弄清的是{focus_text}。我们不用一次解决所有事情，"
                    "你最想先让哪一点发生一点变化？"
                ),
                quick_replies=["睡得早点", "更容易停下", "少和父母吵", "先继续聊聊"],
            )

        if stage is ConversationStage.EVOKE:
            social_value = "又不失去和队友的联系" if needs & {"belonging", "connection"} else "又保留游戏带来的放松"
            return GeneratedReply(
                reply=(
                    f"一方面，游戏确实给了你需要的东西；另一方面，你也不喜欢它现在带来的一些影响。"
                    f"在{social_value}的情况下，你最愿意先改善哪一小点？"
                ),
                quick_replies=["第二天别那么困", "少拖一点作业", "更容易停下来", "暂时不想改"],
            )

        if stage is ConversationStage.PLAN:
            suggested = None
            for hit in knowledge_hits:
                if hit.suggested_actions:
                    suggested = hit.suggested_actions[0]
                    break
            suggested = suggested or "把目标缩小到只试三天，并且每次只提前十五到二十分钟"
            return GeneratedReply(
                reply=(
                    f"你已经开始考虑怎么做了。经过你同意，我们可以先把它当成一个小实验：{suggested}。"
                    "这个难度对你来说是刚好，还是还需要再小一点？"
                ),
                quick_replies=["可以试三天", "还要再小一点", "我担心队友", "先不做计划"],
            )

        return GeneratedReply(
            reply=(
                "你愿意回来看看发生了什么，本身就是一次有效的复盘。我们不只看有没有完成："
                "哪一次最接近做到，当时有什么条件帮了你？"
            ),
            quick_replies=["有一次做到了", "完全没做到", "目标太难", "遇到临时组队"],
        )

    def _maybe_create_action_plan(
        self,
        state: SessionState,
        message: str,
        analysis: ConversationAnalysis,
    ) -> ActionPlan | None:
        accepted = any(token in message for token in ("可以试", "我试试", "提前20分钟", "提前二十分钟", "试三天"))
        if not accepted or analysis.stage not in {ConversationStage.PLAN, ConversationStage.EVOKE}:
            return None

        confidence = analysis.motivation.confidence or 6
        reason = {
            "sleep": "希望第二天上课不那么困",
            "school": "希望更容易开始学习任务",
            "family": "希望减少因为游戏发生的争吵",
            "stopping": "希望重新获得按计划停下来的选择权",
        }.get(analysis.focus_topic, "希望减少游戏对生活的影响")

        return ActionPlan(
            title="我的三天小实验",
            behavior="在平常结束时间前二十分钟提醒自己和队友这是最后一局",
            duration="连续尝试三天",
            reason=reason,
            confidence=confidence,
            obstacle="队友临时邀请再开一局",
            coping_plan="最后一局开始前提前说明今天的下线时间；失败时只记录原因",
        )
