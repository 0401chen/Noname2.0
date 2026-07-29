from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .schemas import ConversationAnalysis, ConversationStage, MIStrategy, RiskLevel

_STAGE_VALUES = {item.value for item in ConversationStage}
_STRATEGY_VALUES = {item.value for item in MIStrategy}
_RISK_VALUES = {item.value for item in RiskLevel}
_FOCUS_VALUES = {"sleep", "stopping", "school", "family", "emotion", "social"}


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if not isinstance(value, Iterable) or isinstance(value, (bytes, dict)):
        return []

    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
        elif isinstance(item, dict):
            cleaned = _text(
                _first(item, "text", "content", "quote", "reason", "description", "name")
            )
        else:
            cleaned = None
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _boolean(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "需要", "是"}:
            return True
        if normalized in {"false", "no", "0", "不需要", "否"}:
            return False
    return default


def _score(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        return None
    return max(0, min(10, numeric))


def _confidence(value: Any, default: float = 0.6) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if 1 < numeric <= 100:
        numeric /= 100
    return max(0.0, min(1.0, numeric))


def _needs(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value is None:
        return fallback
    items = value if isinstance(value, list) else [value]
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            name = item.strip()
            confidence = 0.6
        elif isinstance(item, dict):
            name = _text(_first(item, "name", "need", "type", "label")) or ""
            confidence = _confidence(_first(item, "confidence", "score", "probability"))
        else:
            continue
        if name and not any(existing["name"] == name for existing in normalized):
            normalized.append({"name": name, "confidence": confidence})
    return normalized[:3] or fallback


def _motivation(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    raw = _first(payload, "motivation", "motivation_state", "readiness")
    raw_dict = raw if isinstance(raw, dict) else {}
    importance = _score(
        _first(
            raw_dict,
            "importance",
            "readiness",
            "willingness",
            "change_importance",
        )
    )
    if importance is None:
        importance = _score(
            _first(payload, "importance", "readiness_score", "willingness", "change_readiness")
        )
    confidence = _score(_first(raw_dict, "confidence", "self_efficacy", "action_confidence"))
    if confidence is None:
        confidence = _score(
            _first(payload, "confidence", "confidence_score", "self_efficacy")
        )
    return {
        "importance": fallback.get("importance") if importance is None else importance,
        "confidence": fallback.get("confidence") if confidence is None else confidence,
    }


def _risk(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    raw = _first(payload, "risk", "risk_assessment", "safety")
    raw_dict = raw if isinstance(raw, dict) else {}
    level = _text(_first(raw_dict, "level", "risk_level")) or _text(
        _first(payload, "risk_level", "safety_level")
    )
    normalized_level = level.upper() if level else fallback.get("level", "LOW")
    if normalized_level not in _RISK_VALUES:
        normalized_level = fallback.get("level", "LOW")

    signals = _string_list(_first(raw_dict, "signals", "risk_signals", "indicators"))
    if not signals:
        signals = _string_list(_first(payload, "risk_signals", "safety_signals"))
    if not signals:
        signals = list(fallback.get("signals", []))

    immediate = _boolean(
        _first(raw_dict, "immediate_danger", "urgent", "imminent"),
        bool(fallback.get("immediate_danger", False)),
    )
    return {
        "level": normalized_level,
        "signals": signals,
        "immediate_danger": immediate,
        "source": "llm",
    }


def normalize_analysis_payload(
    payload: dict[str, Any],
    fallback: ConversationAnalysis,
) -> ConversationAnalysis:
    """Adapt provider-specific JSON into the project's stable analysis schema.

    Providers may follow the semantic intent while returning aliases such as
    ``current_emotions`` or ``retrieval_needed``. Missing optional fields inherit
    deterministic heuristic values, so a harmless schema variation does not disable
    the whole semantic-analysis layer.
    """

    base = fallback.model_dump(mode="json")

    summary = _text(
        _first(payload, "summary", "analysis_summary", "conversation_summary", "current_summary")
    ) or base["summary"]

    stage = _text(_first(payload, "stage", "mi_stage", "conversation_stage"))
    normalized_stage = stage.upper() if stage else base["stage"]
    if normalized_stage not in _STAGE_VALUES:
        normalized_stage = base["stage"]

    focus = _text(_first(payload, "focus_topic", "focus", "topic", "primary_focus"))
    normalized_focus = focus.lower() if focus else base.get("focus_topic")
    if normalized_focus not in _FOCUS_VALUES:
        normalized_focus = base.get("focus_topic")

    emotions = _string_list(
        _first(payload, "emotions", "current_emotions", "current_emotion", "emotion")
    ) or list(base.get("emotions", []))

    needs = _needs(
        _first(payload, "psychological_needs", "needs", "underlying_needs", "current_needs"),
        list(base.get("psychological_needs", [])),
    )

    change_talk = _string_list(
        _first(payload, "change_talk", "change_language", "change_statements")
    ) or list(base.get("change_talk", []))
    sustain_talk = _string_list(
        _first(
            payload,
            "sustain_talk",
            "maintenance_language",
            "sustain_language",
            "status_quo_talk",
        )
    ) or list(base.get("sustain_talk", []))

    raw_strategies = _string_list(
        _first(payload, "mi_strategies", "strategies", "mi_strategy", "recommended_strategies")
    )
    strategies = [item.upper() for item in raw_strategies if item.upper() in _STRATEGY_VALUES]
    if not strategies:
        strategies = list(base.get("mi_strategies", []))

    rag_required = _boolean(
        _first(
            payload,
            "rag_required",
            "retrieval_needed",
            "needs_retrieval",
            "knowledge_retrieval_needed",
            "use_rag",
        ),
        bool(base.get("rag_required", False)),
    )
    rag_queries = _string_list(
        _first(payload, "rag_queries", "retrieval_queries", "search_queries", "knowledge_queries")
    )
    if rag_required and not rag_queries:
        rag_queries = list(base.get("rag_queries", []))

    next_goal = _text(
        _first(payload, "next_goal", "next_step", "conversation_goal", "response_goal")
    ) or base["next_goal"]

    candidate = {
        "summary": summary,
        "stage": normalized_stage,
        "focus_topic": normalized_focus,
        "emotions": emotions,
        "psychological_needs": needs,
        "change_talk": change_talk,
        "sustain_talk": sustain_talk,
        "motivation": _motivation(payload, dict(base.get("motivation", {}))),
        "risk": _risk(payload, dict(base.get("risk", {}))),
        "mi_strategies": strategies[:2],
        "rag_required": rag_required,
        "rag_queries": rag_queries,
        "next_goal": next_goal,
    }
    return ConversationAnalysis.model_validate(candidate)
