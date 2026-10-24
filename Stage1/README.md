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
| `state.json` | Checkpoints, keyed by user id |
| `sessions.json` | Registry of known sessions (status, metadata) |

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

## Run

```
python states_serialize.py
python day2-state_machines.py
```

Enter a user id, a query, then inputs. Press `1` to pause (checkpoint and exit)
or `2` to continue.
