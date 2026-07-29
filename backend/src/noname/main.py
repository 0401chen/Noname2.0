from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .llm import LLMClient
from .rag import KnowledgeStore
from .schemas import ChatRequest, ChatResponse, HealthResponse
from .service import ConversationService
from .storage import MemorySessionStore, SQLiteSessionStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

settings = get_settings()
knowledge = KnowledgeStore()
sessions = (
    SQLiteSessionStore(settings.session_database_path)
    if settings.use_sqlite_sessions
    else MemorySessionStore()
)
service = ConversationService(
    llm=LLMClient(settings),
    knowledge=knowledge,
    sessions=sessions,
    max_messages=settings.session_max_messages,
)

app = FastAPI(
    title="重启键 Re:Play API",
    version="0.2.0",
    description="面向青少年的游戏行为心理支持比赛原型。仅用于支持和演示，不进行医学诊断。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "重启键 Re:Play",
        "tagline": "不是逼你离开游戏，而是帮你重新拿回选择权。",
        "docs": "/docs",
    }


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_enabled=service.llm.enabled,
        model=settings.llm_model,
        storage=service.sessions.kind,
        knowledge_entries=len(knowledge.entries),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await service.chat(request)
    except Exception as exc:
        logging.exception("Unhandled chat error")
        raise HTTPException(
            status_code=500,
            detail="会话处理暂时失败，请稍后重试。",
        ) from exc


@app.delete("/api/sessions/{session_id}")
async def clear_session(session_id: str) -> dict[str, bool]:
    return {"cleared": service.sessions.clear(session_id)}
