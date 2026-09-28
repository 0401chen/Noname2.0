from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

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
    KnowledgeHit,
    ReviewerTrace,
    RiskLevel,
    SessionState,
)
from .storage import MemorySessionStore, SessionStore
from .turn_context import engage_fallback_reply

CRITICAL_QUALITY_FLAGS = {
    "diagnosis_or_label",
    "coercive_language",
    "dependency_language",
    "false_rescue_claim",
    "high_risk_without_safety_focus",
    "deception_or_evasion",
    "internal_trace_leak",
    "too_long",
    "too_many_questions",
}


class ConversationService:
    def __init__(
        self,
        *,
        llm: LLMClient,
        knowledge: KnowledgeStore,
        sessions: SessionStore | None = None,
        max_messages: int = 40,
    ) -> None:
        self.llm = llm
        self.knowledge = knowledge
        self.sessions = sessions or MemorySessionStore()
        self.max_messages = max(8, max_messages)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started_at = perf_counter()
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
        if semantic_analysis is not None:
            if analysis.focus_topic is None:
                analysis.focus_topic = fallback_analysis.focus_topic
            if not analysis.psychological_needs:
                analysis.psychological_needs = fallback_analysis.psychological_needs
            if not analysis.emotions:
                analysis.emotions = fallback_analysis.emotions
            if fallback_analysis.motivation.importance is not None:
                analysis.motivation.importance = fallback_analysis.motivation.importance
                analysis.stage = fallback_analysis.stage
                analysis.mi_strategies = fallback_analysis.mi_strategies
                analysis.next_goal = fallback_analysis.next_goal

        analysis.risk = merge_risk(rule_risk, semantic_analysis.risk if semantic_analysis else None)
        if analysis.risk.level is RiskLevel.HIGH:
            analysis.stage = ConversationStage.SAFETY
            analysis.next_goal = "确认当前安全并连接现实支持"
            analysis.rag_required = False
            analysis.rag_queries = []

        knowledge_hits: list[KnowledgeHit] = []
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
                generated = self._fallback_reply(
                    state,
                    request.message,
                    analysis,
                    knowledge_hits,
                )
                fallback_used = True
            reply = generated.reply
            quick_replies = generated.quick_replies

        quality_flags = review_reply(reply, analysis)
        if CRITICAL_QUALITY_FLAGS.intersection(quality_flags):
            generated = self._fallback_reply(
                state,
                request.message,
                analysis,
                knowledge_hits,
            )
            reply = generated.reply
            quick_replies = generated.quick_replies
            fallback_used = True
            quality_flags = [*quality_flags, "unsafe_generation_replaced"]

        action_plan = self._maybe_create_action_plan(state, request.message, analysis)
        if action_plan is not None:
            state.action_plan = action_plan
        elif state.action_plan is not None:
            self._update_action_plan_progress(state.action_plan, request.message)

        state.messages.append(ChatMessage(role="user", content=request.message))
        state.messages.append(ChatMessage(role="assistant", content=reply))
        if len(state.messages) > self.max_messages:
            state.messages = state.messages[-self.max_messages :]
        state.analysis = analysis
        state.updated_at = datetime.now(timezone.utc)
        self.sessions.save(state)

        processing_ms = round((perf_counter() - started_at) * 1000, 2)
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
                retrieval_method=self.knowledge.method if knowledge_hits else "none",
                knowledge_hits=knowledge_hits,
                quality_flags=quality_flags,
                fallback_used=fallback_used,
                processing_ms=processing_ms,
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
        state: SessionState,
        message: str,
        analysis: ConversationAnalysis,
        knowledge_hits: list[KnowledgeHit],
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

        importance = analysis.motivation.importance
        if importance is not None:
            if importance == 0:
                return GeneratedReply(
                    reply=(
                        "你给了0分，说明现在并不想把精力放在改变游戏上，这个选择可以被尊重。"
                        "我们先不谈计划，只把游戏对你最重要的部分弄清楚。"
                    ),
                    quick_replies=["主要是放松", "队友很重要", "现实太累", "先不聊改变"],
                )
            if importance <= 3:
                return GeneratedReply(
                    reply=(
                        f"你给了{importance}分，听起来改变这件事目前并不太吸引你，我不会催你往前走。"
                        "即使只有这一点分数，它更像是来自想少困一点、少些争吵，还是别的原因？"
                    ),
                    quick_replies=["少困一点", "少些争吵", "更容易停下", "其实不想改"],
                )
            if importance >= 8:
                return GeneratedReply(
                    reply=(
                        f"你给了{importance}分，说明这件事对你已经相当重要。"
                        "在不一下子戒掉游戏的前提下，你觉得哪个最小变化最值得先试？"
                    ),
                    quick_replies=["提前20分钟", "少开一局", "先做五分钟作业", "先想想困难"],
                )
            return GeneratedReply(
                reply=(
                    f"你给了{importance}分，说明你既看到了改变的理由，也还有一些顾虑。"
                    "是什么让它已经不止更低的分数？"
                ),
                quick_replies=["第二天太困", "总和父母吵", "作业被拖延", "想重新能停下"],
            )

        stage = analysis.stage
        focus = analysis.focus_topic
        needs = {item.name for item in analysis.psychological_needs}

        if stage is ConversationStage.ENGAGE:
            previous_assistant = next(
                (
                    item.content
                    for item in reversed(state.messages)
                    if item.role == "assistant"
                ),
                None,
            )
            return engage_fallback_reply(message, previous_assistant)

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
            social_value = (
                "又不失去和队友的联系"
                if needs & {"belonging", "connection"}
                else "又保留游戏带来的放松"
            )
            return GeneratedReply(
                reply=(
                    "一方面，游戏确实给了你需要的东西；另一方面，你也不喜欢它现在带来的一些影响。"
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
        plan_intent = any(
            token in message
            for token in (
                "可以试",
                "我试试",
                "想试",
                "我想先",
                "今晚先",
                "今天晚上先",
                "明天开始",
                "提前20分钟",
                "提前二十分钟",
                "提早结束",
                "提前结束",
                "设置闹钟",
                "设闹钟",
                "设置提醒",
                "试三天",
                "制定一个任务",
                "制定任务",
                "制定一个行动",
                "制定行动",
                "行动计划",
                "制定计划",
                "安排一个行动",
                "安排时间",
                "做个计划",
                "定个计划",
            )
        )
        if not plan_intent:
            return None

        recent_user_text = " ".join(
            [
                item.content
                for item in state.messages[-10:]
                if item.role == "user"
            ]
            + [message]
        )
        focus = analysis.focus_topic or state.analysis.focus_topic if state.analysis else analysis.focus_topic
        focus = focus or "general"

        if any(token in recent_user_text for token in ("闹钟", "提醒")) and focus in {"sleep", "stopping"}:
            return ActionPlan(
                title="早点下线小实验",
                behavior="今晚设置一个结束游戏的闹钟；闹钟响后结束当前对局，不再开启新一局",
                duration="先尝试今晚，再观察第二天状态",
                reason="希望更早结束游戏，让第二天上课更有精神",
                confidence=analysis.motivation.confidence or 6,
                obstacle="闹钟响时正好还想继续玩或再开一局",
                coping_plan="把闹钟当作最后一局提醒；没按计划停下也只记录原因，下一次再调整",
            )

        if any(token in message for token in ("今晚先不玩", "今天晚上先不玩", "今晚不玩")):
            return ActionPlan(
                title="今晚的小实验",
                behavior="今晚先暂停游戏，观察第二天的精神状态",
                duration="今晚到明天上课前",
                reason="看看减少今晚的游戏是否能让第二天更有精神",
                confidence=analysis.motivation.confidence or 6,
                obstacle="晚上到了平常游戏时间又想打开游戏",
                coping_plan="先把今晚当成一次观察实验，不要求以后都这样做",
            )

        if any(token in recent_user_text for token in ("提早结束", "提前结束")) and focus == "sleep":
            return ActionPlan(
                title="早点结束小实验",
                behavior="今晚比平常更早结束游戏，并观察第二天的精神状态",
                duration="先尝试今晚，再决定是否继续",
                reason="希望第二天上课更有精神",
                confidence=analysis.motivation.confidence or 6,
                obstacle="到时间后还想继续玩一局",
                coping_plan="提前确定结束点；如果没做到，只记录是什么让自己继续玩了",
            )

        plans = {
            "sleep": {
                "title": "睡眠小实验",
                "behavior": "今晚比平常更早结束游戏，并观察第二天的精神状态",
                "duration": "先尝试今晚；觉得有用再决定是否继续",
                "reason": "希望第二天上课更有精神",
                "obstacle": "到了平常结束时间还想再开一局",
                "coping": "提前决定最后一局的时间；没做到也只记录发生了什么",
            },
            "stopping": {
                "title": "下线小实验",
                "behavior": "开始最后一局前确定结束点，到点后不再进入新对局",
                "duration": "先尝试一次，再根据结果调整",
                "reason": "希望重新获得按计划停下来的选择权",
                "obstacle": "结束后又想再开一局",
                "coping": "提醒响起后先离开座位两分钟，再决定下一步",
            },
            "school": {
                "title": "学习启动小实验",
                "behavior": "开始游戏前先用五分钟启动一个最小学习任务",
                "duration": "先尝试三次",
                "reason": "希望更容易开始学习任务，减少游戏后的压力",
                "obstacle": "任务看起来太大，不知道从哪里开始",
                "coping": "只写标题、读一道题或整理一页资料，五分钟后允许重新选择",
            },
            "family": {
                "title": "沟通小实验",
                "behavior": "找一个冲突较少的时段，只表达一个感受和一个具体请求",
                "duration": "先尝试一次",
                "reason": "希望减少因为游戏发生的争吵",
                "obstacle": "一开口就变成互相指责",
                "coping": "只说自己的感受和请求，不争论谁对谁错",
            },
            "emotion": {
                "title": "情绪观察小实验",
                "behavior": "打开游戏前花九十秒记下当前情绪和最想从游戏里得到什么",
                "duration": "连续记录三次",
                "reason": "希望看清游戏和情绪之间的关系",
                "obstacle": "情绪上来时只想立刻进入游戏",
                "coping": "只选一个情绪词即可，不要求马上解决它",
            },
            "social": {
                "title": "下线边界小实验",
                "behavior": "最后一局开始前把今天的下线时间告诉队友",
                "duration": "先尝试一次",
                "reason": "希望保留队友关系，同时建立自己的下线边界",
                "obstacle": "担心队友失望或临时缺人",
                "coping": "提前说明不是退出团队，而是今天到点下线",
            },
            "general": {
                "title": "时间安排小实验",
                "behavior": "先选一个最小、明确的游戏时间调整，并记录实际效果",
                "duration": "先尝试一天，再决定下一步",
                "reason": "希望找到更适合自己的游戏与生活安排",
                "obstacle": "计划太大或临时想改变",
                "coping": "把目标缩小到今天能做到的一步，失败只作为调整信息",
            },
        }
        selected = plans[focus]
        return ActionPlan(
            title=selected["title"],
            behavior=selected["behavior"],
            duration=selected["duration"],
            reason=selected["reason"],
            confidence=analysis.motivation.confidence or 6,
            obstacle=selected["obstacle"],
            coping_plan=selected["coping"],
        )

    @staticmethod
    def _update_action_plan_progress(plan: ActionPlan, message: str) -> None:
        success = any(
            token in message
            for token in (
                "做到了",
                "完成了",
                "成功了",
                "坚持了",
                "确实有用",
                "精神很好",
                "有精神",
                "效果很好",
                "效果不错",
                "感觉好多了",
            )
        )
        difficulty = any(
            token in message
            for token in ("没做到", "没有做到", "失败了", "目标太难", "忘了", "还是没停下来")
        )

        if success:
            plan.attempts += 1
            plan.successes += 1
            plan.last_review = "这次尝试已经记录：你观察到了积极变化，可以据此决定下一步怎么调整"
        elif difficulty:
            plan.attempts += 1
            plan.last_review = "这次尝试没有按计划完成；先记录原因，不作责备，再决定是否把目标缩小"

        if any(token in message for token in ("三天都做到了", "连续三天完成", "这个计划完成了")):
            plan.status = "completed"
        elif any(token in message for token in ("先暂停", "暂时不做")):
            plan.status = "paused"
