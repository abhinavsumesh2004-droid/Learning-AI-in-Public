# Stage 1 — States and Serialization

A small demo of durable agent state: keeping a conversation's state in memory,
writing it to disk, and resuming it after the process exits.

## Files

| File | Purpose |
| --- | --- |
| `states_serialize.py` | Demo loop: load state, append input, save state |
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

## What was learned

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

## Run

```
python states_serialize.py
```

Enter a user id, a query, then inputs. Press `1` to pause (checkpoint and exit)
or `2` to continue.
