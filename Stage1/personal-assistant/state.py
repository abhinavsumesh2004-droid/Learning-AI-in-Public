from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


STATUSES = {
    "intake",
    "classified",
    "gathered",
    "drafted",
    "awaiting_approval",
    "revising",
    "completed",
    "rejected",
}


TRANSITIONS = {
    "intake": {"classified"},
    "classified": {"gathered", "drafted"},
    "gathered": {"drafted"},
    "revising": {"drafted"},
    "drafted": {"awaiting_approval"},
    "awaiting_approval": {"completed", "rejected", "revising"},
    "completed": set(),
    "rejected": set(),
}


class AssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    request: str
    category: str
    details: str
    draft: str
    feedback: str
    revision_count: int
    status: str


def advance(state: AssistantState, new_status: str) -> str:
    current = state.get("status") or "intake"
    if new_status not in TRANSITIONS.get(current, set()):
        raise ValueError(f"illegal transition: {current} -> {new_status}")
    return new_status
