from httpx import ASGITransport, AsyncClient

from noname.main import app


async def test_health_endpoint_reports_runtime_mode() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["llm_enabled"], bool)
    assert payload["model"]
    assert payload["storage"] in {"sqlite", "memory"}
    assert payload["knowledge_entries"] > 0


async def test_evaluation_summary_endpoint_is_always_available() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/evaluation/summary")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["ready"], bool)
    assert payload["note"]


async def test_chat_endpoint_has_offline_fallback() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "session_id": "api-offline-demo",
                "message": "我最近总是玩到两点，第二天上课很困",
                "reviewer_mode": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"]
    assert payload["trace"] is not None
    assert payload["trace"]["focus_topic"] == "sleep"


async def test_demo_scenarios_are_fictional_and_cover_safety() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/demo/scenarios")

    assert response.status_code == 200
    payload = response.json()
    assert "虚构" in payload["notice"]
    assert len(payload["scenarios"]) >= 5
    assert any(item["high_risk"] for item in payload["scenarios"])
    assert all(item["messages"] for item in payload["scenarios"])


async def test_diagnostics_never_exposes_api_key() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "0.4.0"
    assert payload["storage"] in {"memory", "sqlite"}
    assert payload["session_retention_hours"] >= 1
    assert "api_key" not in response.text.lower()
    assert "LLM_API_KEY" not in response.text
