from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .config import Settings
from .schemas import ConversationAnalysis, KnowledgeHit, SessionState

logger = logging.getLogger(__name__)


class GeneratedReply(BaseModel):
    reply: str = Field(min_length=1, max_length=1200)
    quick_replies: list[str] = Field(default_factory=list, max_length=4)


ANALYSIS_SYSTEM_PROMPT = """
你是 Re:Play 的会话分析器，面向 12—18 岁青少年。你的任务不是诊断疾病，而是为后续回复生成结构化会话状态。

必须遵守：
1. 不把游戏时长直接等同于游戏障碍。
2. 区分游戏带来的价值、现实影响、改变语言和维持现状语言。
3. MI 阶段只能是 ENGAGE、FOCUS、EVOKE、PLAN、REVIEW、SAFETY。
4. MI 策略只能从给定枚举中选择，最多两个主要策略。
5. 规则层给出的风险等级只能保持或提高，不能降低。
6. 只输出一个 JSON 对象，不输出 Markdown 或解释。

分析重点：用户当前情绪、游戏背后的心理需要、关注问题、改变意愿、下一轮目标、是否需要知识检索。
""".strip()

REPLY_SYSTEM_PROMPT = """
你是“重启键 Re:Play”，一个面向青少年的游戏行为心理支持助手。

表达原则：
- 不说教、不贴标签、不诊断，不站在父母一方训斥用户。
- 先准确反映用户的感受或矛盾，再提出最多一个主要问题。
- 决定权属于用户；提供建议前尽量征得许可。
- 不要求突然戒断，行动建议应足够小、可观察、可以失败后调整。
- 不制造 AI 依赖，不说“只有我懂你”，不承诺保密或现实救援。
- 回复一般为 60—180 个中文字，避免长篇科普。
- 只输出 JSON：reply 与 quick_replies；quick_replies 为 2—4 个简短选项。
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("model output is not a JSON object")
    return value


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_error: str | None = None
        self.client = (
            AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout_seconds,
                max_retries=1,
            )
            if settings.llm_enabled
            else None
        )

    @property
    def enabled(self) -> bool:
        return self.client is not None

    async def analyze(
        self,
        state: SessionState,
        message: str,
        rule_analysis: ConversationAnalysis,
    ) -> ConversationAnalysis | None:
        if self.client is None:
            return None

        history = [item.model_dump(mode="json") for item in state.messages[-8:]]
        payload = {
            "history": history,
            "user_message": message,
            "rule_and_heuristic_result": rule_analysis.model_dump(mode="json"),
            "allowed_mi_strategies": [
                "OPEN_QUESTION",
                "SIMPLE_REFLECTION",
                "COMPLEX_REFLECTION",
                "AFFIRMATION",
                "SUMMARY",
                "DOUBLE_SIDED_REFLECTION",
                "AUTONOMY_SUPPORT",
                "ELICIT_CHANGE_TALK",
                "READINESS_RULER",
                "CONFIDENCE_RULER",
                "ASK_PERMISSION",
                "ACTION_PLANNING",
                "REVIEW_AND_ADJUST",
            ],
        }

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            result = ConversationAnalysis.model_validate(_extract_json(content))
            self.last_error = None
            return result
        except Exception as exc:  # network, provider and validation errors degrade safely
            self.last_error = f"analysis: {type(exc).__name__}: {exc}"
            logger.warning("LLM analysis failed: %s", self.last_error)
            return None

    async def generate_reply(
        self,
        state: SessionState,
        message: str,
        analysis: ConversationAnalysis,
        knowledge_hits: list[KnowledgeHit],
    ) -> GeneratedReply | None:
        if self.client is None:
            return None

        history: list[dict[str, str]] = [
            {"role": item.role, "content": item.content} for item in state.messages[-8:]
        ]
        payload = {
            "current_user_message": message,
            "analysis": analysis.model_dump(mode="json"),
            "knowledge": [hit.model_dump(mode="json") for hit in knowledge_hits],
            "requirements": {
                "use_planned_mi_strategy": True,
                "ask_at_most_one_main_question": True,
                "do_not_claim_diagnosis": True,
                "do_not_expose_internal_scores": True,
            },
        }

        messages: list[dict[str, str]] = [
            {"role": "system", "content": REPLY_SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                temperature=0.55,
                response_format={"type": "json_object"},
                messages=messages,
            )
            content = response.choices[0].message.content or "{}"
            result = GeneratedReply.model_validate(_extract_json(content))
            self.last_error = None
            return result
        except Exception as exc:
            self.last_error = f"reply: {type(exc).__name__}: {exc}"
            logger.warning("LLM reply failed: %s", self.last_error)
            return None
