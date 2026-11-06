from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentflow.db import get_db, initialize_database
from agentflow.engine.runner import execute_run
from agentflow.models import Run, Workflow
from agentflow.schemas import (
    ResumeRequest, RunCreate, RunResponse, WorkflowCreate, WorkflowResponse,
)
from agentflow.tools.registry import list_tools


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="AgentFlow API",
    description="Observable workflow orchestration with tools, branching and human approval.",
    version="0.1.0",
    lifespan=lifespan,
)


def validate_graph(payload: WorkflowCreate) -> str:
    nodes = {node.id: node for node in payload.nodes}
    if len(nodes) != len(payload.nodes):
        raise HTTPException(status_code=422, detail="Node IDs must be unique")
    for edge in payload.edges:
        if edge.source not in nodes or edge.target not in nodes:
            raise HTTPException(status_code=422, detail="Every edge must reference existing nodes")
    incoming = {node_id: 0 for node_id in nodes}
    for edge in payload.edges:
        incoming[edge.target] += 1
    starts = [node_id for node_id, count in incoming.items() if count == 0]
    if len(starts) != 1:
        raise HTTPException(status_code=422, detail="Workflow must have exactly one start node")
    for node in payload.nodes:
        if node.type == "condition":
            labels = {edge.label for edge in payload.edges if edge.source == node.id}
            if not {"true", "false"}.issubset(labels):
                raise HTTPException(
                    status_code=422,
                    detail=f"Condition node '{node.id}' requires true and false outgoing edges",
                )
    return starts[0]


def serialize_run(run: Run) -> RunResponse:
    return RunResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        status=run.status,
        state=run.state,
        current_node=run.current_node,
        error=run.error,
        events=[
            {
                "node_id": event.node_id,
                "event_type": event.event_type,
                "message": event.message,
                "data": event.data,
            }
            for event in run.events
        ],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tools")
def tools():
    return {"tools": list_tools()}


@app.post("/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate, db: Session = Depends(get_db)):
    validate_graph(payload)
    workflow = Workflow(name=payload.name, definition=payload.model_dump())
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return WorkflowResponse(id=workflow.id, name=workflow.name, definition=workflow.definition)


@app.get("/workflows", response_model=list[WorkflowResponse])
def list_workflows(db: Session = Depends(get_db)):
    rows = db.scalars(select(Workflow).order_by(Workflow.id.desc())).all()
    return [
        WorkflowResponse(id=row.id, name=row.name, definition=row.definition)
        for row in rows
    ]


@app.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = db.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowResponse(id=workflow.id, name=workflow.name, definition=workflow.definition)


@app.post("/workflows/{workflow_id}/runs", response_model=RunResponse, status_code=201)
def start_run(workflow_id: int, payload: RunCreate, db: Session = Depends(get_db)):
    workflow = db.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    start_node = validate_graph(WorkflowCreate.model_validate(workflow.definition))
    run = Run(
        workflow_id=workflow.id,
        status="running",
        state=payload.input,
        current_node=start_node,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    execute_run(db, run, workflow.definition)
    return serialize_run(run)


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize_run(run)


@app.post("/runs/{run_id}/resume", response_model=RunResponse)
def resume_run(run_id: int, payload: ResumeRequest, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "waiting_approval" or not run.current_node:
        raise HTTPException(status_code=409, detail="Run is not waiting for approval")
    execute_run(db, run, run.workflow.definition, approval=payload.approved)
    return serialize_run(run)
