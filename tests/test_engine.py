import pytest
from fastapi.testclient import TestClient

from agentflow.db import Base, engine
from agentflow.main import app
from agentflow.tools.registry import execute_tool


def test_safe_calculator_supports_arithmetic():
    assert execute_tool("math.calculate", "2 + 3 * 4") == 14


def test_calculator_rejects_python_execution():
    with pytest.raises((ValueError, SyntaxError)):
        execute_tool("math.calculate", "__import__('os').system('echo unsafe')")


def test_text_tools():
    assert execute_tool("text.word_count", "one two three") == 3
    assert execute_tool("text.uppercase", "agent flow") == "AGENT FLOW"


def test_workflow_requires_one_start_node():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        response = client.post("/workflows", json={
            "name": "invalid",
            "nodes": [
                {"id": "a", "type": "end", "config": {}},
                {"id": "b", "type": "end", "config": {}}
            ],
            "edges": []
        })
        assert response.status_code == 422


def test_workflow_executes_tool_and_records_trace():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        created = client.post("/workflows", json={
            "name": "word-count",
            "nodes": [
                {"id": "count", "type": "tool", "config": {
                    "tool": "text.word_count", "input": "{{message}}", "output_key": "words"
                }},
                {"id": "finish", "type": "end", "config": {}}
            ],
            "edges": [{"source": "count", "target": "finish"}]
        })
        assert created.status_code == 201
        workflow_id = created.json()["id"]
        started = client.post(f"/workflows/{workflow_id}/runs", json={
            "input": {"message": "hello from agent flow"}
        })
        assert started.status_code == 201
        result = started.json()
        assert result["status"] == "completed"
        assert result["state"]["words"] == 4
        assert len(result["events"]) == 2


def test_approval_pauses_and_resumes():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        created = client.post("/workflows", json={
            "name": "approval",
            "nodes": [
                {"id": "gate", "type": "approval", "config": {"message": "Review this action"}},
                {"id": "finish", "type": "end", "config": {}}
            ],
            "edges": [{"source": "gate", "target": "finish"}]
        })
        workflow_id = created.json()["id"]
        started = client.post(f"/workflows/{workflow_id}/runs", json={"input": {}})
        run_id = started.json()["id"]
        assert started.json()["status"] == "waiting_approval"
        resumed = client.post(f"/runs/{run_id}/resume", json={"approved": True})
        assert resumed.json()["status"] == "completed"
