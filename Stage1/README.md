# Stage 1 — Agent Architecture & State Machines

This stage is a practical exploration of how agent workflows manage state, move
between steps, pause, and resume. The work starts with plain Python dictionaries
and JSON, moves to a state machine built by hand, and then revisits the same
ideas using LangGraph.

The aim is to understand the ideas behind the framework by building small
experiments, observing their behaviour, and recording what still needs work.
These scripts are learning exercises, not production implementations.

## What I am trying to learn

- How to represent the state of a multi-step workflow.
- How to persist state so a process can continue after it stops.
- How to make allowed and disallowed transitions explicit.
- How to model branching, retries, and cycles.
- How graph frameworks handle execution, checkpointing, and human approval.
- How to inspect a workflow when its behaviour is not what I expected.
- Where a framework helps, and which design decisions still belong to the
  developer.

I use AI coding agents as implementation partners in some experiments. Their
output is still something to inspect: I want to understand the structure, test
the behaviour, identify gaps, and document both useful results and mistakes.

## Stage tasks

The topics below are the tasks I am working through in this stage. Some have
been explored in code; others remain to be revisited or completed.

- Represent workflow state and distinguish in-memory state from serialized data.
- Load and save JSON state, preserving multiple sessions.
- Understand persistence risks and how atomic writes can help.
- Define state-machine states and events.
- Build a transition table and reject illegal transitions.
- Model cycles, terminal states, and state reachability.
- Compare DAGs with cyclic workflows.
- Define typed state in LangGraph.
- Build graph nodes, edges, and conditional routing.
- Understand partial state updates and reducers.
- Implement bounded retry cycles.
- Use a SQLite checkpointer with session/thread identifiers.
- Inspect saved state and checkpoint history.
- Pause workflows with `interrupt()` and resume with `Command(resume=...)`.
- Understand what happens when an interrupted node is re-executed.
- Stream graph execution and inspect node updates.
- Trace execution using checkpoint IDs and state snapshots.
- Explore `update_state` and replay from an earlier checkpoint.
- Compare the workflow model with Temporal.io.
- Combine classification, branching, interrupts, checkpointing, approval, and
  recovery in an integrated CLI project.

## Why build it by hand first

Using LangGraph without the underlying model can make a graph, checkpointer, or
pause/resume mechanism feel like magic. Building similar behaviour with
\`json.dump\` and a transition table first makes each framework feature answer a
problem encountered in a smaller implementation.

| Hand-built (days 1–2) | LangGraph (day 3) |
| --- | --- |
| \`state\` dict | \`TypedDict\` state schema |
| \`json.load\` / \`json.dump\` | checkpointer (\`SqliteSaver\`) |
| \`state.json\` keyed by user id | \`thread_id\` |
| \`if/elif\` on \`current_pos\` | conditional edges + path map |
| transition table \`(state, event) -> next\` | nodes + edges + routers |
| \`while True\` loop | graph runtime |
| hand-built pause/resume | \`interrupt()\` + \`Command(resume=...)\` |
| inspect JSON file | \`get_state\` / \`get_state_history\` |

The framework reduces some of the plumbing, but the decisions about state,
transitions, persistence, and recovery still need to be made.

## Files

| File | Purpose |
| --- | --- |
| \`states_serialize.py\` | Day 1: load state, append input, save state |
| \`day2-state_machines.py\` | Day 2: transition table, events, resume |
| \`day3-langraph.py\` | Day 3: LangGraph graph, router, retry cycle, checkpointer, interrupt |
| \`day-langgraph-tracing.py\` | Day 3: inspect checkpoints from SQLite |
| \`personal-assistant/\` | Practice project combining the earlier concepts |
| \`state.json\` | Runtime state keyed by user id |
| \`sessions.json\` | Registry of known sessions |
| \`checkpoints.sqlite\` | LangGraph checkpoint store generated at runtime |

## Day 1 — States and serialization

The first exercises use a dictionary as the in-memory state and a JSON file as
the persisted representation.

- **State vs. serialization.** State is the in-memory dictionary.
  Serialization turns it into a representation that can be stored; deserialization
  reads it back. Without persistence, state disappears when the process ends.
- **Checkpointing.** The purpose of saving state is to make it possible to
  continue a run rather than always starting from scratch.
- **Mutate, don't rebuild.** Writing a fresh \`{user_id: record}\` each run can
  delete every other user's checkpoint. Load the existing collection and update
  only the current entry.
- **In-memory changes are not persisted.** Updating a dictionary without writing
  it back leaves the on-disk version unchanged.
- **\`json.dump()\` returns \`None\`.** It writes to a file object; it does not
  return the serialized data.
- **Writes can be destructive.** Opening a file in \`"w"\` mode truncates it.
  A crash during a write can leave an incomplete checkpoint.
- **Atomic writes.** A safer pattern is to write to a temporary file, flush and
  sync it, then replace the original with \`os.replace()\`.
- **Resume policy is separate from persistence.** Saving state and deciding
  which saved state to resume are different concerns.
- **One source of truth.** If both a registry and a checkpoint file answer
  whether a session exists, they can disagree.

## Day 2 — State machines

A state machine consists of named **states**, **events**, and a transition
function or table that determines the next state. The transition rules should
be the authority for movement through the workflow.

- **Events, not menu numbers.** The menu translates user input into events;
  the transition table decides where those events lead.
- **Illegal transitions should be rejected.** A missing state/event pair should
  prevent the workflow from silently continuing.
- **Persist the state name.** A saved state that is unknown when loaded should
  be treated as invalid rather than guessed.
- **Resume is a transition, not a reset.** Rewriting a saved state to \`start\`
  just to reuse a transition can make the recorded state inconsistent with the
  data it represents.
- **Cycles are edges.** Asking for more input can be represented as a transition
  back to an input state, rather than scattered assignments inside a loop.
- **Check reachability.** Resumable states need a path forward; declared states
  should be reachable; terminal states should be attainable.
- **DAG vs. cyclic graph.** A DAG has no cycles. A workflow that can return to
  an earlier state needs a cyclic graph.

The hand-built script still uses a loop to drive the machine. The LangGraph
exercise explores how a graph runtime can take over that responsibility.

## Day 3 — LangGraph

The LangGraph exercise revisits the state-machine ideas using a typed state, a
graph of nodes, conditional routing, and a checkpointer.

### Mental model

- **Graph = state schema + nodes + edges.** The \`AgentState\` TypedDict lists
  the state channels. Nodes receive state and return partial updates.
- **Reducers decide merging.** A field such as
  \`messages: Annotated[list, add_messages]\` appends messages. Fields without a
  reducer are generally overwritten by updates.
- **Conditional edges are routing rules.** A router examines the state and
  selects a destination node.
- **Cycles are edges.** A retry can route back to an earlier node, with a
  counter or recursion limit used to bound the loop.
- **Nodes can use \`Command(goto=...)\`.** This is another way to combine a state
  update with a routing decision.

### Checkpointing

- **In-memory vs. durable storage.** An in-memory saver does not survive process
  termination. The SQLite checkpointer stores checkpoints in
  \`checkpoints.sqlite\`, associated with a \`thread_id\`.
- **Pass only new input after the first run.** Supplying an old value again can
  overwrite a checkpointed channel when no reducer is configured.
- **Inspect snapshots.** \`get_state\` returns a snapshot with values, next
  nodes, and configuration. \`get_state_history\` exposes earlier snapshots.
- **Checkpoints store state, not necessarily prompts.** Prompts are often
  constructed from state and code, or logged separately.
- **Avoid positional assumptions.** Reading \`messages[-1]\` can select a
  classification message rather than the original user query. Keeping the query
  in its own state field makes its purpose explicit.

### Human-in-the-loop

- \`interrupt(payload)\` pauses the graph and returns an interrupt to the caller.
- \`Command(resume=value)\` supplies the value used to resume the interrupt.
- The interrupted node starts executing again from its beginning on resume.
  Side effects before the interrupt therefore need care.
- A checkpointer and the same \`thread_id\` are required to resume the run.

### Tracing from another process

\`SqliteSaver.list(config)\` can be used to inspect checkpoint tuples. The
tracing script prints the step, next node, last message, and checkpoint ID for
each snapshot, allowing inspection without rebuilding the graph.

## Practice project — Personal Assistant

The \`personal-assistant/\` directory combines several of the stage concepts in a
small CLI workflow: classify a request, gather details when needed, draft a
response, and pause for human approval or rejection.

The initial implementation was developed with help from an AI coding agent.
I used the project as an opportunity to inspect the generated structure, run
manual scenarios, note unexpected behaviour, and make targeted changes. The
project README records the flow, smoke tests, observations, and current
limitations. It is a learning case study, not a claim that the assistant is
production-ready.

Some issues observed during testing:

- Rejection originally ended the run. The flow was changed to return to drafting
  with the rejection reason, with a limit of two revisions.
- Drafts sometimes invented details when the request contained little context.
  Grounding instructions and a lower temperature reduced this behaviour but
  did not eliminate it.
- The session registry was not updated at every pause. It is now updated after
  each graph invocation.

The tests were manual CLI smoke tests, not an automated test suite. The full
test table and remaining limitations are in
[\`personal-assistant/README.md\`](personal-assistant/README.md).

## Run the experiments

Run these from the \`Stage1\` directory:

\`\`\`bash
python states_serialize.py
python day2-state_machines.py
python day3-langraph.py
python day-langgraph-tracing.py
\`\`\`

Day 3 requires \`GROQ_API_KEY\` in \`.env\` and the dependencies in the virtual
environment (\`langgraph\`, \`langchain-core\`, \`groq\`, and \`python-dotenv\`).
The graph currently uses \`openai/gpt-oss-120b\`; change \`MODEL\` if using another
Groq model.

For days 1–2, enter a user ID, a query, and then inputs. Press \`1\` to pause
(checkpoint and exit) or \`2\` to continue.

## Notes on scope

The examples focus on understanding state and workflow behaviour. They do not
yet cover every production concern, such as comprehensive automated testing,
concurrent session updates, robust recovery from partial file writes in every
path, or operational monitoring. Those are areas to revisit rather than
assumptions this stage is intended to settle.
