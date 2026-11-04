# Personal Assistant — Stage 1 practice project

This small CLI assistant brings several Stage 1 concepts together: explicit
state, branching, a transition table, durable checkpoints, and human-in-the-loop
pause/resume.

The initial implementation was created with assistance from an AI coding agent.
I am treating it as a practical learning case study: understand the generated
workflow, inspect how its parts fit together, try realistic scenarios, record
unexpected behaviour, and make changes where the tests reveal a gap.

This is an experiment for learning about workflow design and reliability, not a
production assistant. The notes below distinguish the intended flow from what
was observed during manual testing.

## What this project is intended to explore

- How a request moves through a multi-step workflow.
- How classification determines which path is taken.
- How an interrupt can collect information or request approval.
- How rejection feedback can send a workflow back to an earlier step.
- How checkpoints allow a paused session to resume.
- How a session registry relates to the checkpoint store.
- What can go wrong even when the main happy path works.

## Workflow

- \`classify\` asks the LLM to classify the request as \`task\` or \`chat\`.
- \`gather\` pauses with \`interrupt()\` to ask for extra details when the request
  is classified as a task.
- \`draft\` asks the LLM to write a response using the request and any gathered
  details. On a revision, it also receives the rejection feedback.
- \`approve\` pauses with \`interrupt()\`:
  - \`approve\` → \`completed\`
  - \`reject <reason>\` → return to \`draft\` with the reason as feedback
  - after \`MAX_REVISIONS\` (2) rejections → \`rejected\`

Statuses and legal transitions are defined in \`state.py\`. A transition not
listed there raises \`ValueError\`.

## Files and responsibilities

| File | Purpose |
| --- | --- |
| \`assistant.py\` | Graph, LLM calls, CLI commands (\`new\`, \`resume\`, \`list\`) |
| \`state.py\` | \`AssistantState\` schema, statuses, transition table |
| \`registry.py\` | \`sessions.json\` index, written using a temporary file and replace |
| \`sessions.json\` | Session registry: title, status, timestamps |
| \`checkpoints.sqlite\` | LangGraph checkpoints, keyed by \`thread_id\` (generated at runtime) |

## How it maps to Stage 1

| Stage 1 concept | How it appears here |
| --- | --- |
| State dictionary | \`AssistantState\` (\`request\`, \`category\`, \`details\`, \`draft\`, \`feedback\`, \`revision_count\`, \`status\`) |
| Serialization | SQLite checkpoints instead of \`json.dump\` |
| Checkpoint per session | \`thread_id\` is the \`session_id\` |
| Transition rules | \`TRANSITIONS\` and \`advance()\` |
| Branching | \`classify_router\` |
| Pause/resume | \`interrupt()\` and \`Command(resume=...)\` |
| Session registry | \`sessions.json\` managed by \`registry.py\` |
| Crash recovery | Resume a session from its pending interrupt after the process exits |

## Running the project

Use the Stage 1 virtual environment. From this directory:

\`\`\`powershell
..\.venv\Scripts\python.exe assistant.py new "plan my week"
..\.venv\Scripts\python.exe assistant.py list
..\.venv\Scripts\python.exe assistant.py resume <session_id>
\`\`\`

On Linux/macOS, the interpreter path is \`../.venv/bin/python\`.

The project requires \`GROQ_API_KEY\` in \`Stage1/.env\`. The model is set by
\`MODEL\` in \`assistant.py\` (currently \`openai/gpt-oss-120b\`).

## Manual smoke tests

The following scenarios were run manually through the CLI. They are useful
checks of the main paths, but they are not a substitute for an automated test
suite.

| # | Scenario | Steps | Observed |
| --- | --- | --- | --- |
| 1 | Task happy path | \`new "plan my week"\`, enter details, \`approve\` | Classified as \`task\`, asked for details, drafted, approved, status \`completed\` |
| 2 | Chat path | \`new "what can you do?"\`, \`approve\` | Classified as \`chat\`, skipped \`gather\`, drafted, approved |
| 3 | Reject then approve | \`new\`, details, \`reject: make it shorter\`, \`approve\` | Second draft produced, status \`completed\`, \`revision_count\` = 1 |
| 4 | Revision cap | \`new\`, details, three \`reject\` decisions | Two redrafts, then status \`rejected\` |
| 5 | Crash at approval | \`new\`, details, close terminal / \`Ctrl+C\` at approval | Process exited; \`list\` showed \`awaiting_approval\` |
| 6 | Resume after crash | \`resume <session_id>\`, \`approve\` | Same approval prompt reappeared, then status \`completed\` |
| 7 | Resume a finished session | \`resume <completed_id>\` | Returned the final state; no nodes re-ran |
| 8 | List sessions | \`list\` | Printed ID, status, and title for each session |

## Observations and changes made

These are observations from the scenarios above and the debugging that followed.
They describe the behaviour seen in this implementation; they are not claims
that the underlying problems are fully solved.

### Rejection initially had no useful destination

The first version sent a rejection directly to \`END\`. That meant the approval
step could stop a run but could not guide a revision. The flow was changed to
return to drafting with the rejection reason as feedback, with a maximum of two
revisions.

### Drafts sometimes invented details

With only a short request, the model sometimes supplied details that were not
provided, such as times, names, or placeholder contact information. Grounding
instructions were added and the temperature was lowered to \`0.2\`. This reduced
the behaviour in the tested examples, but did not eliminate it.

### Registry status could become stale

The registry was initially updated only after a run completed. A paused or
interrupted session could therefore still appear to be at \`intake\`. The registry
is now updated after each graph invocation.

### Line-ending changes created noisy Git diffs

An editor or checkout converted files to CRLF, making Git report broad changes
even when the content had not meaningfully changed. The committed versions
were restored to remove that noise.

## Current limitations and questions to revisit

- **Hallucination is reduced, not solved.** Structured output and explicit
  checks for required information may make the drafting step more reliable.
- **Classification fallback is permissive.** Unexpected model output is
  coerced to \`task\`; a validated schema and an explicit fallback path would be
  easier to reason about.
- **No concurrency control.** Two processes resuming the same session could
  race while updating shared session data.
- **Two stores have different roles.** \`sessions.json\` is a convenience index;
  the checkpoint store is the source of truth for workflow state.
- **Time travel is not implemented.** \`update_state\` and replaying an earlier
  \`checkpoint_id\` remain topics to explore.
- **No automated tests yet.** The table above records manual smoke tests. These
  scenarios could later be converted into repeatable automated tests.

## What this experiment has helped me examine

The project provided a concrete place to look at how state, routing, interrupts,
checkpointing, and recovery interact. The manual tests also showed that a
workflow can pass its happy path while still having awkward rejection
behaviour, stale metadata, or unreliable model output.

A useful next step for this learning exercise is to revisit the open questions
above and check whether the current implementation and observations still
support the conclusions recorded here. The purpose of documenting them is to
make the learning process and the limits of the current experiment visible.
