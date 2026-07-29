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
