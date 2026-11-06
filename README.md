# AgentFlow

**A lightweight workflow orchestration API for building observable, tool-using AI agents.**

AgentFlow models an agent run as an explicit directed graph. Workflows can transform state, invoke allowlisted tools, evaluate conditions, pause for human approval and resume from persisted state. Every step is recorded as an execution event.

> **Status:** portfolio MVP. This implementation focuses on reliable orchestration primitives. It is not an autonomous, unrestricted agent runtime.

## Core capabilities

- Define workflows as directed graphs with typed nodes and edges.
- Execute deterministic state and tool nodes.
- Route execution through conditional branches.
- Pause at human approval gates and resume later.
- Persist workflow definitions, run state and execution traces.
- Inspect run status, outputs, errors and step history.
- Execute a small allowlisted tool registry (calculator and text utilities).
- API documentation through OpenAPI / Swagger.

## Architecture

```text
Client
  |
  v
FastAPI ---- Workflow API
  |
  +---- Workflow definitions (SQLAlchemy)
  |
  +---- Execution engine
          |
          +-- State node
          +-- Tool registry (allowlisted)
          +-- Conditional router
          +-- Human approval gate
          +-- End node
          |
          v
      Run state + event trace
          |
          v
      SQL database
```

## Stack

- Python 3.12
- FastAPI + Pydantic
- SQLAlchemy 2
- SQLite by default; PostgreSQL supported through `DATABASE_URL`
- pytest + Ruff
- Docker Compose

## Quick start

### Requirements
- Python 3.12+ (or Docker)

### Local

```bash
git clone https://github.com/asunavlr/agent-flow.git
cd agent-flow
python -m venv .venv
# Windows: .venv\\Scripts\\Activate.ps1
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn agentflow.main:app --reload
```

Open http://localhost:8000/docs.

### Docker

```bash
docker compose up --build
```

## Workflow model

A workflow contains an ordered set of uniquely identified nodes and directed edges. Supported node types:

| Type | Purpose | Config |
|---|---|---|
| `set` | Write a value into run state | `key`, `value` |
| `tool` | Invoke an allowlisted tool | `tool`, `input`, `output_key` |
| `condition` | Choose an outgoing edge | `key`, `operator`, `value` |
| `approval` | Pause until a human decision | `message` |
| `end` | Complete the run | — |

Edges can have a condition label. For a condition node, use `true` and `false` labels. Other nodes follow their default outgoing edge.

Example workflow:

```json
{
  "name": "review-request",
  "nodes": [
    {"id": "start", "type": "set", "config": {"key": "request", "value": "Please review this change"}},
    {"id": "count", "type": "tool", "config": {"tool": "text.word_count", "input": "{{request}}", "output_key": "word_count"}},
    {"id": "gate", "type": "approval", "config": {"message": "Approve this request? "}},
    {"id": "done", "type": "end", "config": {}}
  ],
  "edges": [
    {"source": "start", "target": "count"},
    {"source": "count", "target": "gate"},
    {"source": "gate", "target": "done"}
  ]
}
```

Template values such as `{{request}}` resolve from the current run state. Values are intentionally simple strings; this is not a general-purpose expression evaluator.

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/tools` | List available tools |
| POST | `/workflows` | Create a workflow |
| GET | `/workflows` | List workflows |
| GET | `/workflows/{id}` | Get a workflow |
| POST | `/workflows/{id}/runs` | Start a run |
| GET | `/runs/{id}` | Inspect run state and trace |
| POST | `/runs/{id}/resume` | Approve or reject a pending gate |

### Create and execute

Create a workflow using the example above, then start it:

```json
POST /workflows/{workflow_id}/runs
{"input": {"ticket_id": "SUP-1042"}}
```

When a run reaches an approval node, its status becomes `waiting_approval`. Resume it with:

```json
POST /runs/{run_id}/resume
{"approved": true}
```

Fetch `GET /runs/{run_id}` to inspect the current state and ordered execution events.

## Safety boundaries

- Tools are explicitly registered; workflow input cannot import arbitrary Python modules or execute code.
- The calculator parses a restricted arithmetic AST rather than calling `eval`.
- No arbitrary shell, filesystem or unrestricted network tool is exposed.
- Approval nodes pause execution; the API does not silently approve actions.
- This MVP has no authentication or tenant isolation. Do not expose it publicly with sensitive workflows.

## Development

```bash
pytest
ruff check .
```

## Roadmap

- [ ] LLM-backed planning and structured tool selection
- [ ] Async workers, queueing and cancellation
- [ ] Retry policies, timeouts and idempotency keys
- [ ] Workflow versioning and schema migrations
- [ ] Authentication, RBAC and tenant isolation
- [ ] OpenTelemetry traces and metrics
- [ ] Web UI for graph editing and live run inspection
- [ ] Integration tests against PostgreSQL

## License

MIT
