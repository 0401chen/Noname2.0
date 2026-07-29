from noname.rag import KnowledgeStore
from noname.schemas import RiskLevel


def test_hybrid_retrieval_prioritizes_sleep_and_social_context() -> None:
    store = KnowledgeStore()
    hits = store.search("队友总叫我再来一局，玩到凌晨两点第二天很困")

    assert hits
    assert hits[0].category in {"sleep", "social"}
    assert any(hit.category == "sleep" for hit in hits)
    assert any(hit.category == "social" for hit in hits)
    assert all(hit.score >= hit.bm25_score for hit in hits)
    assert all(0 <= hit.semantic_score <= 1 for hit in hits)


def test_high_risk_retrieval_only_returns_safety_material() -> None:
    store = KnowledgeStore()
    hits = store.search("我现在很危险想伤害自己", risk_level=RiskLevel.HIGH)

    assert hits
    assert all(hit.category == "safety" for hit in hits)
