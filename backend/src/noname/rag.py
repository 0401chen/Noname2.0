from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .schemas import KnowledgeHit, RiskLevel


HAN_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+")
STOP_CHARACTERS = set("的了是在和与也就都而及或很把被让给有没我你他她它这那吗呢吧啊呀")
SYNONYMS = {
    "游戏成瘾": "游戏障碍 游戏失控",
    "网瘾": "游戏障碍 游戏失控",
    "开黑": "队友 朋友 一起玩",
    "肝游戏": "熬夜 游戏时间",
}


def normalize(text: str) -> str:
    normalized = text.lower()
    for source, target in SYNONYMS.items():
        normalized = normalized.replace(source, f"{source} {target}")
    return normalized


def tokenize(text: str) -> list[str]:
    """Create dependency-free Chinese lexical tokens for BM25.

    Single characters retain short signals such as“困”, while bigrams and
    trigrams preserve phrases such as“睡眠”“队友”“停不下来”.
    """

    normalized = normalize(text)
    tokens = WORD_PATTERN.findall(normalized)
    for run in HAN_RUN_PATTERN.findall(normalized):
        tokens.extend(character for character in run if character not in STOP_CHARACTERS)
        for size in (2, 3):
            tokens.extend(run[index : index + size] for index in range(len(run) - size + 1))
    return tokens


def semantic_ngrams(text: str) -> Counter[str]:
    normalized = re.sub(r"\s+", "", normalize(text))
    grams: list[str] = []
    for size in (2, 3, 4):
        grams.extend(normalized[index : index + size] for index in range(len(normalized) - size + 1))
    grams.extend(WORD_PATTERN.findall(normalized))
    return Counter(grams)


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = left.keys() & right.keys()
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


class KnowledgeStore:
    """Transparent hybrid retriever for a small, reviewed knowledge base.

    It combines BM25 lexical relevance with a local Chinese character n-gram
    vector score. The second score is not a neural embedding, but it provides a
    deterministic semantic-like fallback when the configured API has no
    embeddings endpoint. Every component remains visible in reviewer mode.
    """

    method = "bm25+char-ngram"

    def __init__(self, path: Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[3] / "knowledge" / "reviewed" / "core.json"
        self.path = path or default_path
        self.entries = self._load_entries()
        self._documents = [self._searchable_text(entry) for entry in self.entries]
        self._token_counts = [Counter(tokenize(document)) for document in self._documents]
        self._semantic_counts = [semantic_ngrams(document) for document in self._documents]
        self._document_lengths = [sum(counter.values()) for counter in self._token_counts]
        self._average_length = (
            sum(self._document_lengths) / len(self._document_lengths)
            if self._document_lengths
            else 0.0
        )
        self._document_frequency = Counter(
            token for counter in self._token_counts for token in counter.keys()
        )

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("knowledge file must contain a JSON array")
        return data

    @staticmethod
    def _searchable_text(entry: dict[str, Any]) -> str:
        return " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("summary", "")),
                " ".join(entry.get("keywords", [])),
                " ".join(entry.get("suggested_actions", [])),
            ]
        )

    def _bm25(self, query_tokens: Counter[str], document_index: int) -> float:
        if not self.entries or not self._average_length:
            return 0.0

        k1 = 1.5
        b = 0.75
        token_counts = self._token_counts[document_index]
        document_length = self._document_lengths[document_index]
        score = 0.0
        total_documents = len(self.entries)

        for token, query_frequency in query_tokens.items():
            term_frequency = token_counts.get(token, 0)
            if term_frequency == 0:
                continue
            document_frequency = self._document_frequency[token]
            inverse_frequency = math.log(
                1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = term_frequency + k1 * (
                1 - b + b * document_length / self._average_length
            )
            score += inverse_frequency * (term_frequency * (k1 + 1) / denominator) * min(
                query_frequency,
                2,
            )
        return score

    def search(
        self,
        query: str,
        *,
        limit: int = 4,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> list[KnowledgeHit]:
        if not self.entries or not query.strip():
            return []

        query_tokens = Counter(tokenize(query))
        query_semantics = semantic_ngrams(query)
        scored: list[tuple[float, int, float, float, list[str]]] = []

        for index, entry in enumerate(self.entries):
            if risk_level is RiskLevel.HIGH and entry.get("category") != "safety":
                continue

            bm25_score = self._bm25(query_tokens, index)
            semantic_score = cosine_similarity(query_semantics, self._semantic_counts[index])
            keyword_bonus = sum(
                0.8 for keyword in entry.get("keywords", []) if keyword and keyword in query
            )
            category_bonus = 0.8 if str(entry.get("category", "")) in query else 0.0
            combined_score = bm25_score + semantic_score * 4.0 + keyword_bonus + category_bonus

            matched_terms = sorted(
                query_tokens.keys() & self._token_counts[index].keys(),
                key=lambda token: (len(token), query_tokens[token]),
                reverse=True,
            )[:8]
            if combined_score > 0.05:
                scored.append(
                    (combined_score, index, bm25_score, semantic_score, matched_terms)
                )

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[KnowledgeHit] = []
        for score, index, bm25_score, semantic_score, matched_terms in scored[:limit]:
            entry = self.entries[index]
            results.append(
                KnowledgeHit(
                    id=entry["id"],
                    title=entry["title"],
                    category=entry["category"],
                    summary=entry["summary"],
                    suggested_actions=entry.get("suggested_actions", []),
                    score=round(score, 4),
                    bm25_score=round(bm25_score, 4),
                    semantic_score=round(semantic_score, 4),
                    matched_terms=matched_terms,
                    source_name=entry.get("source_name"),
                    source_url=entry.get("source_url"),
                )
            )
        return results
