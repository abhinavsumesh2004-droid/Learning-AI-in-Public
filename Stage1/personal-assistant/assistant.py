import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from registry import Registry
from state import AssistantState, advance

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent
DB_PATH = BASE / "checkpoints.sqlite"
REGISTRY_PATH = BASE / "sessions.json"

load_dotenv()

client = Groq()
MODEL = "openai/gpt-oss-120b"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ask(prompt):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return (response.choices[0].message.content or "").strip()


def ai(text):
    return {"role": "ai", "content": text}


def intake(state: AssistantState):
    return {"status": "intake"}


def classify(state: AssistantState):
    prompt = f"""
    You are a personal assistant. Classify the user's request into exactly one
    of these categories:

    - task: something to plan, do, schedule, book, research or draft
    - chat: casual conversation or a simple question

    Request:
    {state["request"]}

    Return ONLY the category name.
    """
    category = ask(prompt).strip().lower()
    if category not in {"task", "chat"}:
        category = "task"
    return {
        "category": category,
        "status": advance(state, "classified"),
        "messages": [ai(f"Category: {category}")],
    }


def classify_router(state: AssistantState):
    return "gather" if state["category"] == "task" else "draft"


def gather(state: AssistantState):
    answer = interrupt(
        {
            "type": "clarify",
            "question": "Any extra details for this task? (leave blank to skip)",
            "request": state["request"],
        }
    )
    return {
        "details": (answer or "").strip(),
        "status": advance(state, "gathered"),
    }


def draft(state: AssistantState):
    prompt = f"""
    You are a helpful personal assistant. Write a concise, practical draft
    response for the user.

    Request: {state["request"]}
    Category: {state["category"]}
    Extra details: {state["details"] or "(none)"}

    The draft will be reviewed by the user before it is used.
    """
    text = ask(prompt)
    return {
        "draft": text,
        "status": advance(state, "drafted"),
        "messages": [ai(text)],
    }


def await_approval(state: AssistantState):
    return {"status": advance(state, "awaiting_approval")}


def approve(state: AssistantState):
    decision = interrupt(
        {
            "type": "approval",
            "draft": state["draft"],
            "instruction": "Type approve or reject",
        }
    )
    decision = str(decision or "").strip().lower()
    if decision.startswith("a"):
        return {"status": advance(state, "completed")}
    return {"status": advance(state, "rejected")}


def build_graph(checkpointer):
    graph = StateGraph(AssistantState)

    graph.add_node("intake", intake)
    graph.add_node("classify", classify)
    graph.add_node("gather", gather)
    graph.add_node("draft", draft)
    graph.add_node("await_approval", await_approval)
    graph.add_node("approve", approve)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "classify")
    graph.add_conditional_edges(
        "classify",
        classify_router,
        {"gather": "gather", "draft": "draft"},
    )
    graph.add_edge("gather", "draft")
    graph.add_edge("draft", "await_approval")
    graph.add_edge("await_approval", "approve")
    graph.add_edge("approve", END)

    return graph.compile(checkpointer=checkpointer)


def format_interrupt(value):
    if value.get("type") == "approval":
        print("\n--- draft ---")
        print(value["draft"])
        print("-------------")
        return input(f"{value.get('instruction', 'approve or reject')}: ")
    print(f"\n{value.get('question', value)}")
    return input("> ")


def run(graph, registry, session_id, payload):
    config = {"configurable": {"thread_id": session_id}}
    result = graph.invoke(payload, config)

    while True:
        registry.upsert(
            session_id,
            status=result.get("status", "unknown"),
            updated_at=now(),
        )
        if "__interrupt__" not in result:
            return result

        try:
            answer = format_interrupt(result["__interrupt__"][0].value)
        except (EOFError, KeyboardInterrupt):
            print(f"\npaused. resume with: assistant.py resume {session_id}")
            return None

        result = graph.invoke(Command(resume=answer), config)


def cmd_new(args):
    request = " ".join(args).strip()
    if not request:
        print("usage: assistant.py new <request>")
        return

    session_id = str(uuid.uuid4())
    registry = Registry(REGISTRY_PATH)
    registry.upsert(
        session_id,
        title=request[:60],
        status="intake",
        created_at=now(),
        updated_at=now(),
    )

    print(f"session: {session_id}")
    graph = build_graph(connect())
    result = run(
        graph,
        registry,
        session_id,
        {
            "messages": [{"role": "user", "content": request}],
            "request": request,
            "category": "",
            "details": "",
            "draft": "",
            "status": "intake",
        },
    )
    if result:
        print_final(result)


def cmd_resume(args):
    if not args:
        print("usage: assistant.py resume <session_id>")
        return

    session_id = args[0]
    registry = Registry(REGISTRY_PATH)
    if session_id not in registry.sessions():
        print(f"unknown session: {session_id}")
        return

    graph = build_graph(connect())
    result = run(graph, registry, session_id, None)
    if result:
        print_final(result)


def cmd_list(_args):
    registry = Registry(REGISTRY_PATH)
    sessions = registry.sessions()
    if not sessions:
        print("no sessions")
        return

    for session_id, entry in sessions.items():
        print(
            f"{session_id}  {entry.get('status', '?'):<18} "
            f"{entry.get('title', '')}"
        )


def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)


def print_final(result):
    print("\nstatus:", result.get("status"))
    print("category:", result.get("category"))
    if result.get("draft"):
        print("draft:", result["draft"])


COMMANDS = {
    "new": cmd_new,
    "resume": cmd_resume,
    "list": cmd_list,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage:")
        print("  assistant.py new <request>")
        print("  assistant.py resume <session_id>")
        print("  assistant.py list")
        return

    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
