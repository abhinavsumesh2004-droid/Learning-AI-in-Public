# Personal Assistant — Stage 1 practice project

A small CLI personal assistant built to practice the Stage 1 concepts: explicit
state, serialization, a transition table, branching, durable checkpoints, and
human-in-the-loop pause/resume.

It is a learning project, not production software. The goal was to connect the
ideas from the earlier scripts into one working flow and see where they break.

## Flow

- `classify` asks the LLM for `task` or `chat`.
- `gather` pauses with `interrupt()` to ask for extra details (task only).
- `draft` asks the LLM to write the response, grounded in the request and
  details; on a revision it also receives the rejection feedback.
- `approve` pauses with `interrupt()`:
  - `approve` → `completed`
  - `reject <reason>` → back to `draft` with the reason as feedback
  - after `MAX_REVISIONS` (2) rejections → `rejected`

Statuses and legal transitions live in `state.py`; any transition not listed
there raises `ValueError`.

## Files

| File | Purpose |
| --- | --- |
| `assistant.py` | Graph, LLM calls, CLI (`new`, `resume`, `list`) |
| `state.py` | `AssistantState` schema, statuses, transition table |
| `registry.py` | `sessions.json` index (temp file + replace) |
| `sessions.json` | Session registry: title, status, timestamps |
| `checkpoints.sqlite` | LangGraph checkpoints, keyed by `thread_id` (runtime) |

## How it maps to Stage 1

| Stage 1 concept | Here |
| --- | --- |
| State dict | `AssistantState` (`request`, `category`, `details`, `draft`, `feedback`, `revision_count`, `status`) |
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

## Manual smoke tests

These were run by hand from the CLI. There is no automated test suite yet.

| # | Scenario | Steps | Observed |
| --- | --- | --- | --- |
| 1 | Task happy path | `new "plan my week"`, enter details, `approve` | classified as `task`, asked for details, drafted, approved, status `completed` |
| 2 | Chat path | `new "what can you do?"`, `approve` | classified as `chat`, skipped `gather`, drafted, approved |
| 3 | Reject then approve | `new`, details, `reject: make it shorter`, `approve` | second draft produced, status `completed`, `revision_count` = 1 |
| 4 | Revision cap | `new`, details, three `reject` decisions | two redrafts, then status `rejected` |
| 5 | Crash at approval | `new`, details, close terminal / `Ctrl+C` at approval | process exited, `list` showed `awaiting_approval` |
| 6 | Resume after crash | `resume <session_id>`, `approve` | same approval prompt re-raised, then `completed` |
| 7 | Resume a finished session | `resume <completed_id>` | returned the final state; no nodes re-ran |
| 8 | List sessions | `list` | printed id, status, and title for each session |

## Issues found during testing

- **Rejection had no destination.** The first version sent `reject` straight to
  `END`, which made the approval gate decorative: it could only kill the run.
  Changed to a bounded revise loop with feedback.
- **Drafts hallucinated details.** With only a one-line request, the model
  invented times, names, and placeholder contact fields. Added grounding rules
  ("use only the request and details, ask for missing facts") and lowered
  `temperature` to 0.2. This reduced the problem but did not remove it.
- **Registry status went stale on pause.** Status was only written after the run
  finished, so a crashed or paused session stayed `intake`. Now the registry is
  updated after every graph invocation.
- **CRLF line endings made the working tree look modified.** An editor/checkout
  converted files to CRLF, so Git reported every file as changed even though the
  content was the same. Resolved by restoring the committed files.

## Known limitations / next steps

- Hallucination is reduced, not solved. A stricter approach would use structured
  output and refuse to draft until required fields are present.
- Classification output is coerced to `task` when the model returns something
  unexpected; a schema would be more reliable.
- No concurrency control: two processes resuming the same session will race.
- `sessions.json` is a convenience index; the checkpoint store is the source of
  truth for state.
- Time travel (`update_state`, replaying an old `checkpoint_id`) was not added.
- No automated tests; the table above is manual.
