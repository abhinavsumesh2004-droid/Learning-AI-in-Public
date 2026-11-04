# Personal Assistant — Stage 1 project

A small CLI personal assistant that brings the Stage 1 concepts together:
explicit state, serialization, a transition table, branching, a cycle-free
multi-step flow, durable checkpoints, and human-in-the-loop pause/resume.

## Flow

```
START -> intake -> classify ──task──> gather ──> draft -> await_approval -> approve
                       └──────chat──────────────────┘                         │
                                                          approve ───────────> END
                                                          reject  ──> draft (revise)
```

- `classify` asks the LLM for `task` or `chat`.
- `gather` pauses with `interrupt()` to ask for extra details (task only).
- `draft` asks the LLM to write the response/plan, grounded in the request and
  details; on a revision it also receives the rejection feedback.
- `approve` pauses with `interrupt()`:
  - `approve` → `completed`
  - `reject <reason>` → back to `draft` with the reason as feedback
  - after `MAX_REVISIONS` (2) rejections → `rejected`

Statuses and legal transitions live in `state.py`:

```
intake -> classified -> gathered -> drafted -> awaiting_approval -> completed
                     \-> drafted                    │  \-> revising -> drafted
                                                    └-> rejected (revision cap)
```

Any other transition raises `ValueError`.

## Files

| File | Purpose |
| --- | --- |
| `assistant.py` | Graph, LLM calls, CLI (`new`, `resume`, `list`) |
| `state.py` | `AssistantState` schema, statuses, transition table |
| `registry.py` | `sessions.json` index (atomic write via temp + replace) |
| `sessions.json` | Session registry: title, status, timestamps |
| `checkpoints.sqlite` | LangGraph checkpoints, keyed by `thread_id` |

## What each Stage 1 lesson shows up as

| Stage 1 concept | Here |
| --- | --- |
| State dict | `AssistantState` (`request`, `category`, `details`, `draft`, `status`) |
| Serialization | `SqliteSaver` checkpoints instead of `json.dump` |
| Checkpoint per session | `thread_id` = `session_id` |
| Transition rules | `TRANSITIONS` + `advance()` |
| Branching | `classify_router` |
| Pause/resume | `interrupt()` + `Command(resume=...)` |
| Session registry | `sessions.json` via `registry.py` |
| Crash safety | resuming after a killed process continues at the pending interrupt |

## Run

Use the Stage 1 virtualenv (one level up):

```
cd Stage1/personal-assistant

..\.venv\Scripts\python.exe assistant.py new "plan my week"
..\.venv\Scripts\python.exe assistant.py list
..\.venv\Scripts\python.exe assistant.py resume <session_id>
```

On Linux/macOS the interpreter is `../.venv/bin/python`.

Requires `GROQ_API_KEY` in `Stage1/.env`. Model is set by `MODEL` in
`assistant.py` (`openai/gpt-oss-120b`).

## Try the crash path

1. `new "book a dentist appointment"` and enter details.
2. At the approval prompt, press `Ctrl+C` (or close the terminal).
3. `list` shows `awaiting_approval`.
4. `resume <session_id>` re-raises the same approval prompt and finishes.

## Design notes / limits

- Interrupts require a checkpointer; the same `thread_id` must be used to resume.
- On resume, the interrupted node re-executes from the top, so keep side effects
  after `interrupt()`.
- Rejection is not terminal until the revision cap is hit; the rejection reason
  is fed into the next `draft` call.
- Drafts are generated at `temperature=0.2` with instructions to use only the
  request + details and to ask for missing facts instead of inventing them. This
  reduces but does not eliminate hallucination.
- Classification output is coerced to `task` when the model returns anything
  unexpected; a stricter schema would be better.
- No concurrency control: two processes resuming the same session will race.
- `sessions.json` is a convenience index; the checkpoint store is the source of
  truth for state.
