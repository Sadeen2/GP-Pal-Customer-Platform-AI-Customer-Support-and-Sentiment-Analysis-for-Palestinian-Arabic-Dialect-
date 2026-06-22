import time

SESSIONS = {}
SESSION_TTL_SECONDS = 15 * 60  # 15 minutes


def get_session(session_id: str) -> dict:
    if not session_id:
        session_id = "default"

    session = SESSIONS.get(session_id)

    if not session:
        session = {
            "topic": None,
            "pending_slot": None,
            "data": {},
            "updated_at": time.time()
        }
        SESSIONS[session_id] = session

    # Clear old session
    if time.time() - session.get("updated_at", 0) > SESSION_TTL_SECONDS:
        session = {
            "topic": None,
            "pending_slot": None,
            "data": {},
            "updated_at": time.time()
        }
        SESSIONS[session_id] = session

    return session


def set_pending(session_id: str, topic: str, pending_slot: str, data: dict | None = None):
    session = get_session(session_id)

    session["topic"] = topic
    session["pending_slot"] = pending_slot

    if data:
        session["data"].update(data)

    session["updated_at"] = time.time()
    SESSIONS[session_id] = session


def update_session_data(session_id: str, data: dict):
    session = get_session(session_id)
    session["data"].update(data)
    session["updated_at"] = time.time()
    SESSIONS[session_id] = session


def clear_session(session_id: str):
    SESSIONS[session_id] = {
        "topic": None,
        "pending_slot": None,
        "data": {},
        "updated_at": time.time()
    }