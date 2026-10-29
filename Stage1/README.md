# Stage 1 — Agent Architecture & State Machines

Small demos of durable agent state and explicit state machines: keeping a
conversation's state in memory, writing it to disk, resuming it after the
process exits, and driving transitions through a table instead of ad-hoc code.

> **Scope:** these are learning sketches to get the concepts clear, not
> production code. Error handling, atomic writes, and complete transition
> coverage are intentionally left for later.

## Files

| File | Purpose |
| --- | --- |
| `states_serialize.py` | Day 1: load state, append input, save state |
| `day2-state_machines.py` | Day 2: transition table, events, resume |
| `day3-langraph.py` | Day 3: LangGraph graph, router, retry cycle, checkpointer |
| `day-langgraph-tracing.py` | Day 3: inspect checkpoints from SQLite |
| `state.json` | Checkpoints, keyed by user id |
| `sessions.json` | Registry of known sessions (status, metadata) |
| `checkpoints.sqlite` | LangGraph checkpoint store (generated at runtime) |

## State shape

```json
{
  "u-001": {
    "user_id": "u-001",
    "query": "what can you do with the given info",
    "current_pos": "2",
    "inputs": ["my name is abhinav", "I am learning AI now"],
    "anlaysis": ""
  }
}
```

## Core loop

```
load (deserialize) -> mutate one user's record -> dump (serialize) the whole collection
```

The file is the source of truth for existence; the dict is the source of truth
during a run.

## Day 1 — States and serialization

- **State vs. serialization.** State is the in-memory dict. Serialization is
  turning it into bytes on disk; deserialization is reading it back. Without the
  file, state dies with the process.
- **Checkpointing.** `state.json` exists so a run interrupted by a crash or OOM
  can be resumed instead of restarted.
- **Mutate, don't rebuild.** Writing a fresh `{user_id: record}` each run deletes
  every other user's checkpoint. Load the existing collection first, then change
  only the current entry.
- **In-memory changes are not persisted.** Updating `sessions` in memory without
  a `json.dump` leaves that change on disk untouched.
- **`json.dump()` returns `None`.** It writes to a file object; it does not
  return the data.
- **Writes are destructive first.** `open(path, "w")` truncates immediately. A
  crash mid-dump can leave an empty or half-written file, destroying the very
  checkpoint it was meant to protect.
- **Atomic writes.** Write to `state.json.tmp`, `flush()` + `os.fsync()`, then
  `os.replace(tmp, path)`. Readers then see either the old file or the new one,
  never a partial one.
- **Resume policy is separate from persistence.** Storing state and deciding
  which state to load (last paused, explicit id, etc.) are different concerns.
- **One source of truth.** If both the registry and the checkpoint file can
  answer "does this user exist?", they can disagree.

## Day 2 — State machines

A state machine is: a set of named **states**, a set of **events**, and a
**transition table** `(state, event) -> next_state`. Nothing else writes the
state.

- **Events, not menu numbers.** The menu maps key presses to events
  (`receive_query`, `received_input`, `user_pause`); the table decides where
  they lead.
- **Illegal transitions are rejected.** A missing `(state, event)` pair is a
  guard. Rejection must actually stop or re-drive the flow — re-prompting and
  then continuing anyway is not a guard.
- **Persist the state name.** The checkpoint stores `current_pos` so a new
  process can resume; an unknown value on load is corruption, not something to
  guess.
- **Resume is a transition, not a reset.** Don't rewrite the saved state to
  `start` just to reuse a transition. That makes the state lie about the data
  ("state laundering").
- **Cycles are edges.** "Give more input" is `processing_input -> awaiting_input`
  in the table — not two direct assignments inside a `while True`.
- **No loose edges, no unreachable states.** Every resumable state needs a
  resume path, every declared state must be reachable from the initial state,
  and terminal states must be reachable too.
- **DAG vs. cyclic.** This machine is cyclic: input → process → input again. A
  DAG cannot express that.

The macro loop (`while True`) still drives the machine directly in
`day2-state_machines.py`; inverting it so the loop only dispatches on the
current state is the next exercise (and what LangGraph formalizes).

## Day 3 — LangGraph

The day 2 ideas, but the framework owns the loop: a graph of nodes over a typed
state, with conditional edges as the transition table and a checkpointer as the
serializer.

- **Graph = state schema + nodes + edges.** `AgentState` (a `TypedDict`) is the
  channel set; each node returns a *partial* update, not the whole state.
- **Reducers decide merging.** `messages: Annotated[list, add_messages]`
  appends. Fields without a reducer (`category`, `retry_count`, `query`) are
  overwritten by whatever a node returns.
- **Conditional edges are the table.** `cat_router` maps state to one of
  `{"casual", "research", "retry"}`; the path map names the destination node.
- **Cycles are edges.** `check -> classify` is a real retry cycle, bounded by
  `retry_count` (or `recursion_limit`).
- **Checkpointers.** `InMemorySaver` dies with the process; `SqliteSaver` writes
  to `checkpoints.sqlite`, keyed by `thread_id`, and survives restarts.
- **Pass only new input after the first run.** Passing `retry_count: 0` again
  overwrites the checkpointed value — channels without reducers don't "resume",
  they get replaced.
- **`get_state` returns a snapshot.** Use `.values`, `.next`, `.config`; the
  `.config` is the replay handle. `get_state_history` walks every step.
- **Checkpoints store state, not prompts.** A prompt is derived from state +
  code (or logged separately for observability). To see what a node received,
  inspect the snapshot whose `next` is that node.
- **`messages[-1]` is positional guessing.** After `classify` appends its
  "Classification: ..." message, `llm` reading `[-1]` answers the label instead
  of the query. Pin the query in its own state field.
- **Tracing from another process.** `SqliteSaver.list(config)` yields
  `CheckpointTuple`s; the next node is visible in the `branch:to:<node>`
  channels of `checkpoint["channel_values"]`.

Still open: `interrupt()` for human-in-the-loop pause/resume, streaming
(`stream_mode="updates"`), and time travel via `update_state` / replaying an old
`checkpoint_id`.

## Run

```
python states_serialize.py
python day2-state_machines.py
python day3-langraph.py
python day-langgraph-tracing.py
```

Day 3 needs `GROQ_API_KEY` in `.env` and the dependencies in `.venv`
(`langgraph`, `langchain-core`, `groq`, `python-dotenv`). The graph currently
uses `openai/gpt-oss-120b`; change `MODEL` for another Groq model.

Enter a user id, a query, then inputs. Press `1` to pause (checkpoint and exit)
or `2` to continue.
