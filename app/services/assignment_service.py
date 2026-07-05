from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.database.models import Conversation, User


ACTIVE_CONVERSATION_STATUSES = [
    "active",
    "open",
    "pending_human",
    "escalated",
]

HUMAN_ACTIONS = {
    "human_handoff",
    "escalation",
    "escalate",
}


def count_active_conversations(db: Session, agent_email: str) -> int:
    """How many not-finished conversations are currently assigned to this agent."""
    if not agent_email:
        return 0

    return (
        db.query(Conversation)
        .filter(
            Conversation.assigned_agent == agent_email,
            Conversation.status.in_(ACTIVE_CONVERSATION_STATUSES),
        )
        .count()
    )


def agent_to_assignment_dict(db: Session, agent: User | None) -> dict | None:
    if agent is None:
        return None

    return {
        "id": agent.id,
        "name": agent.name,
        "email": agent.email,
        "role": agent.role,
        "is_available": bool(getattr(agent, "is_available", True)),
        "active_conversations": count_active_conversations(db, agent.email),
        "max_active_conversations": getattr(agent, "max_active_conversations", 5),
        "last_assigned_at": agent.last_assigned_at.isoformat() if getattr(agent, "last_assigned_at", None) else None,
    }


def get_available_agent(db: Session) -> User | None:
    """
    Pick the best available agent.

    Rules:
    1) user.role must be agent
    2) user must be active and available
    3) choose the lowest active workload
    4) tie-break by older last_assigned_at, then id
    """
    agents = (
        db.query(User)
        .filter(
            User.role == "agent",
            User.is_active == True,  # noqa: E712
            User.is_available == True,  # noqa: E712
        )
        .all()
    )

    candidates: list[tuple[int, datetime, int, User]] = []

    for agent in agents:
        active_count = count_active_conversations(db, agent.email)
        max_active = getattr(agent, "max_active_conversations", 5) or 5

        # Skip agents who reached their allowed active queue size.
        if active_count >= max_active:
            continue

        # Oldest/null last assignment should win when workload is equal.
        last_assigned = getattr(agent, "last_assigned_at", None) or datetime.min
        candidates.append((active_count, last_assigned, agent.id, agent))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][3]


def should_auto_assign(
    action: str | None = None,
    needs_human: bool = False,
    urgency: str | None = None,
    sentiment: str | None = None,
    category: str | None = None,
) -> bool:
    """Central rule for deciding whether a conversation must go to a human."""
    action = (action or "").strip()
    urgency = (urgency or "").strip()
    sentiment = (sentiment or "").strip()
    category = (category or "").strip()

    return (
        bool(needs_human)
        or action in HUMAN_ACTIONS
        or urgency in ["urgent", "critical"]
        or (sentiment == "negative" and category in ["complaint", "support"])
    )


def auto_assign_conversation(
    db: Session,
    conversation: Conversation,
    reason: str,
    status: str = "pending_human",
    disable_bot: bool = True,
) -> dict:
    """
    Assign a conversation to an available agent automatically.

    If the conversation is already assigned, keep the current assignment.
    If no available agent exists, leave it unassigned but mark it pending/escalated
    so admins can see it in the queue.
    """
    if conversation is None:
        return {
            "assigned": False,
            "assigned_agent": None,
            "reason": "missing_conversation",
        }

    if conversation.assigned_agent:
        conversation.status = status or conversation.status or "pending_human"
        if disable_bot:
            conversation.bot_enabled = False
        db.add(conversation)
        return {
            "assigned": True,
            "already_assigned": True,
            "assigned_agent": conversation.assigned_agent,
            "reason": "conversation_already_assigned",
        }

    agent = get_available_agent(db)

    if agent is None:
        conversation.status = status or "pending_human"
        if disable_bot:
            conversation.bot_enabled = False
        db.add(conversation)
        return {
            "assigned": False,
            "assigned_agent": None,
            "reason": "no_available_agent",
        }

    conversation.assigned_agent = agent.email
    conversation.status = status or "pending_human"
    conversation.agent_note = conversation.agent_note or f"Auto-assigned: {reason}"
    if disable_bot:
        conversation.bot_enabled = False

    agent.last_assigned_at = datetime.utcnow()
    agent.last_seen_at = getattr(agent, "last_seen_at", None) or datetime.utcnow()

    db.add(conversation)
    db.add(agent)

    return {
        "assigned": True,
        "already_assigned": False,
        "assigned_agent": agent.email,
        "assigned_agent_id": agent.id,
        "assigned_agent_name": agent.name,
        "reason": reason,
        "workload_after_assignment": count_active_conversations(db, agent.email) + 1,
    }
