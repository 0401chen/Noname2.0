from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .schemas import KnowledgeHit, RiskLevel


TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{1,4}|[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    normalized = text.lower().replace("游戏成瘾", "游戏障碍 游戏失控")
    return TOKEN_PATTERN.findall(normalized)


class KnowledgeStore:
    """Small, transparent lexical retriever for the first milestone.

    The interface is intentionally compatible with a future hybrid BM25/vector
    implementation. Keeping the first version dependency-light makes the demo
    runnable even when embedding services are unavailable.
    """

    def __init__(self, path: Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[3] / "knowledge" / "reviewed" / "core.json"
        self.path = path or default_path
        self.entries = self._load_entries()

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("knowledge file must contain a JSON array")
        return data

    def search(
        self,
        query: str,
        *,
        limit: int = 4,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> list[KnowledgeHit]:
        if not self.entries:
            return []

        query_tokens = Counter(tokenize(query))
        scored: list[tuple[float, dict[str, Any]]] = []

        for entry in self.entries:
            if risk_level is RiskLevel.HIGH and entry.get("category") != "safety":
                continue

            searchable = " ".join(
                [
                    str(entry.get("title", "")),
                    str(entry.get("summary", "")),
                    " ".join(entry.get("keywords", [])),
                    " ".join(entry.get("suggested_actions", [])),
                ]
            )
            document_tokens = Counter(tokenize(searchable))
            overlap = sum(
                min(query_tokens[token], document_tokens[token]) for token in query_tokens
            )
            keyword_bonus = sum(
                1.5 for keyword in entry.get("keywords", []) if keyword and keyword in query
            )
            category_bonus = 2.0 if entry.get("category") in query else 0.0
            score = float(overlap + keyword_bonus + category_bonus)

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeHit(
                id=entry["id"],
                title=entry["title"],
                category=entry["category"],
                summary=entry["summary"],
                suggested_actions=entry.get("suggested_actions", []),
                score=score,
                source_name=entry.get("source_name"),
                source_url=entry.get("source_url"),
            )
            for score, entry in scored[:limit]
        ]
