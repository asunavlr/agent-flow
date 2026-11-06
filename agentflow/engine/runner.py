import re
from typing import Any

from sqlalchemy.orm import Session

from agentflow.core.config import get_settings
from agentflow.models import Run, RunEvent
from agentflow.tools.registry import execute_tool

_TEMPLATE = re.compile(r"^{{\s*([a-zA-Z0-9_.-]+)\s*}}$")


def _resolve(value: Any, state: dict[str, Any]) -> Any:
    if isinstance(value, str):
        match = _TEMPLATE.match(value)
        if match:
            return state.get(match.group(1), "")
        return value
    if isinstance(value, list):
        return [_resolve(item, state) for item in value]
    if isinstance(value, dict):
        return {key: _resolve(item, state) for key, item in value.items()}
    return value


def _next_node(node_id: str, edges: list[dict], label: str | None = None) -> str | None:
    candidates = [edge for edge in edges if edge["source"] == node_id]
    if label is not None:
        selected = next((edge for edge in candidates if edge.get("label") == label), None)
        if selected:
            return selected["target"]
    default = next((edge for edge in candidates if edge.get("label") is None), None)
    return default["target"] if default else (candidates[0]["target"] if len(candidates) == 1 else None)


def _event(run: Run, node_id: str, event_type: str, message: str, data=None):
    run.events.append(
        RunEvent(node_id=node_id, event_type=event_type, message=message, data=data or {})
    )


def execute_run(db: Session, run: Run, workflow: dict, *, approval: bool | None = None) -> Run:
    nodes = {node["id"]: node for node in workflow["nodes"]}
    edges = workflow["edges"]
    settings = get_settings()
    steps = 0

    if approval is False:
        run.status = "rejected"
        _event(run, run.current_node or "approval", "rejected", "Human approval rejected.")
        db.commit()
        return run
    if approval is True:
        _event(run, run.current_node or "approval", "approved", "Human approval granted.")
        run.current_node = _next_node(run.current_node, edges)
        run.status = "running"

    while run.current_node:
        steps += 1
        if steps > settings.max_execution_steps:
            run.status = "failed"
            run.error = "Maximum execution steps exceeded (possible cycle)."
            _event(run, run.current_node, "error", run.error)
            break

        node_id = run.current_node
        node = nodes[node_id]
        kind, config = node["type"], node.get("config", {})
        try:
            if kind == "set":
                key = config.get("key")
                if not isinstance(key, str) or not key:
                    raise ValueError("set node requires a non-empty config.key")
                run.state = {**run.state, key: _resolve(config.get("value"), run.state)}
                _event(run, node_id, "completed", f"Stored value in state key '{key}'.")
                run.current_node = _next_node(node_id, edges)

            elif kind == "tool":
                tool_name = config.get("tool")
                output_key = config.get("output_key")
                if not isinstance(output_key, str) or not output_key:
                    raise ValueError("tool node requires config.output_key")
                value = _resolve(config.get("input", ""), run.state)
                result = execute_tool(tool_name, value)
                run.state = {**run.state, output_key: result}
                _event(
                    run, node_id, "completed", f"Tool '{tool_name}' executed.",
                    {"tool": tool_name, "output_key": output_key, "result": result},
                )
                run.current_node = _next_node(node_id, edges)

            elif kind == "condition":
                key = config.get("key")
                actual = run.state.get(key)
                expected = _resolve(config.get("value"), run.state)
                operator_name = config.get("operator", "equals")
                if operator_name == "equals":
                    result = actual == expected
                elif operator_name == "not_equals":
                    result = actual != expected
                elif operator_name in {"gt", "gte"}:
                    if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
                        raise ValueError("gt/gte conditions require numeric values")
                    result = actual > expected if operator_name == "gt" else actual >= expected
                else:
                    raise ValueError(f"Unsupported condition operator: {operator_name}")
                label = "true" if result else "false"
                _event(
                    run, node_id, "routed", f"Condition evaluated to {label}.",
                    {"key": key, "operator": operator_name, "result": label},
                )
                run.current_node = _next_node(node_id, edges, label)

            elif kind == "approval":
                run.status = "waiting_approval"
                run.current_node = node_id
                _event(
                    run, node_id, "waiting_approval",
                    str(config.get("message", "Human approval required.")),
                )
                db.commit()
                return run

            elif kind == "end":
                _event(run, node_id, "completed", "Workflow completed.")
                run.current_node = None
                run.status = "completed"

            else:
                raise ValueError(f"Unsupported node type: {kind}")

            if run.current_node is None and run.status == "running":
                run.status = "completed"
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            _event(run, node_id, "error", str(exc))
            break

    db.commit()
    db.refresh(run)
    return run
