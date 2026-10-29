import sqlite3
import sys

from langgraph.checkpoint.sqlite import SqliteSaver

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)

thread_id = input("Enter thread_id: ").strip()
config = {"configurable": {"thread_id": thread_id}}


def next_nodes(checkpoint):
    return tuple(
        key.split("branch:to:")[1]
        for key in checkpoint["channel_values"]
        if key.startswith("branch:to:")
    )


for snap in memory.list(config):
    values = snap.checkpoint.get("channel_values", {})
    messages = values.get("messages", [])
    last = messages[-1].content if messages else None

    print(
        f"step={snap.metadata.get('step')} "
        f"next={next_nodes(snap.checkpoint)} "
        f"category={values.get('category')!r} "
        f"retry_count={values.get('retry_count')!r}"
    )
    print(f"  last_message={last!r}")
    print(f"  checkpoint_id={snap.config['configurable'].get('checkpoint_id')}")
