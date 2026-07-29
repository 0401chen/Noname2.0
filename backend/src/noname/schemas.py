from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ConversationStage(StrEnum):
    ENGAGE = "ENGAGE"
    FOCUS = "FOCUS"
    EVOKE = "EVOKE"
    PLAN = "PLAN"
    REVIEW = "REVIEW"
    SAFETY = "SAFETY"


class RiskLevel(StrEnum):
    LOW = "LOW"
    CONCERN = "CONCERN"
    HIGH = "HIGH"


class MIStrategy(StrEnum):
    OPEN_QUESTION = "OPEN_QUESTION"
    SIMPLE_REFLECTION = "SIMPLE_REFLECTION"
    COMPLEX_REFLECTION = "COMPLEX_REFLECTION"
    AFFIRMATION = "AFFIRMATION"
    SUMMARY = "SUMMARY"
    DOUBLE_SIDED_REFLECTION = "DOUBLE_SIDED_REFLECTION"
    AUTONOMY_SUPPORT = "AUTONOMY_SUPPORT"
    ELICIT_CHANGE_TALK = "ELICIT_CHANGE_TALK"
    READINESS_RULER = "READINESS_RULER"
    CONFIDENCE_RULER = "CONFIDENCE_RULER"
    ASK_PERMISSION = "ASK_PERMISSION"
    ACTION_PLANNING = "ACTION_PLANNING"
    REVIEW_AND_ADJUST = "REVIEW_AND_ADJUST"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PsychologicalNeed(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)


class RiskAssessment(BaseModel):
    level: RiskLevel = RiskLevel.LOW
    signals: list[str] = Field(default_factory=list)
    immediate_danger: bool = False
    source: str = "rules"


class MotivationState(BaseModel):
    importance: int | None = Field(default=None, ge=0, le=10)
    confidence: int | None = Field(default=None, ge=0, le=10)


class ActionPlan(BaseModel):
    title: str
    behavior: str
    duration: str
    reason: str
    confidence: int = Field(ge=0, le=10)
    obstacle: str | None = None
    coping_plan: str | None = None
    attempts: int = Field(default=0, ge=0)
    successes: int = Field(default=0, ge=0)
    status: Literal["active", "completed", "paused"] = "active"
    last_review: str | None = None


class ConversationAnalysis(BaseModel):
    summary: str
    stage: ConversationStage = ConversationStage.ENGAGE
    focus_topic: str | None = None
    emotions: list[str] = Field(default_factory=list)
    psychological_needs: list[PsychologicalNeed] = Field(default_factory=list)
    change_talk: list[str] = Field(default_factory=list)
    sustain_talk: list[str] = Field(default_factory=list)
    motivation: MotivationState = Field(default_factory=MotivationState)
    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    mi_strategies: list[MIStrategy] = Field(default_factory=list)
    rag_required: bool = False
    rag_queries: list[str] = Field(default_factory=list)
    next_goal: str = "继续理解用户当前最在意的问题"


class KnowledgeHit(BaseModel):
    id: str
    title: str
    category: str
    summary: str
    suggested_actions: list[str] = Field(default_factory=list)
    score: float = Field(ge=0)
    bm25_score: float = Field(default=0, ge=0)
    semantic_score: float = Field(default=0, ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)
    source_name: str | None = None
    source_url: str | None = None


class ReviewerTrace(BaseModel):
    stage: ConversationStage
    risk: RiskAssessment
    focus_topic: str | None = None
    emotions: list[str] = Field(default_factory=list)
    psychological_needs: list[PsychologicalNeed] = Field(default_factory=list)
    change_talk: list[str] = Field(default_factory=list)
    sustain_talk: list[str] = Field(default_factory=list)
    motivation: MotivationState = Field(default_factory=MotivationState)
    mi_strategies: list[MIStrategy] = Field(default_factory=list)
    rag_used: bool = False
    retrieval_method: str = "none"
    knowledge_hits: list[KnowledgeHit] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    processing_ms: float = Field(default=0, ge=0)


class SessionState(BaseModel):
    session_id: str
    age_group: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    analysis: ConversationAnalysis | None = None
    action_plan: ActionPlan | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=3000)
    age_group: str | None = Field(default=None, max_length=20)
    reviewer_mode: bool = False


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    quick_replies: list[str] = Field(default_factory=list)
    action_plan: ActionPlan | None = None
    trace: ReviewerTrace | None = None


class HealthResponse(BaseModel):
    status: str
    llm_enabled: bool
    model: str
    storage: str
    knowledge_entries: int
