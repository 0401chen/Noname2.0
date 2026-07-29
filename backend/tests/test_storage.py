from noname.schemas import ChatMessage
from noname.storage import SQLiteSessionStore


def test_sqlite_session_store_persists_state(tmp_path) -> None:
    database = tmp_path / "sessions.sqlite3"
    first_store = SQLiteSessionStore(database)
    state = first_store.get_or_create("persist-demo", "15-16")
    state.messages.append(ChatMessage(role="user", content="我最近总是玩到很晚"))
    first_store.save(state)
    first_store.close()

    second_store = SQLiteSessionStore(database)
    restored = second_store.get_or_create("persist-demo")

    assert restored.age_group == "15-16"
    assert restored.messages[-1].content == "我最近总是玩到很晚"
    assert second_store.clear("persist-demo") is True
    assert second_store.clear("persist-demo") is False
    second_store.close()
