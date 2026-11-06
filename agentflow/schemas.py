from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict

NodeType = Literal["set", "tool", "condition", "approval", "end"]

class NodeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    type: NodeType
    config: dict[str, Any] = Field(default_factory=dict)

class EdgeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    label: str | None = None

class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    nodes: list[NodeDefinition] = Field(min_length=1, max_length=500)
    edges: list[EdgeDefinition] = Field(default_factory=list)

class WorkflowResponse(BaseModel):
    id: int
    name: str
    definition: dict[str, Any]

class RunCreate(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)

class ResumeRequest(BaseModel):
    approved: bool

class RunEventResponse(BaseModel):
    node_id: str
    event_type: str
    message: str
    data: dict[str, Any]

class RunResponse(BaseModel):
    id: int
    workflow_id: int
    status: str
    state: dict[str, Any]
    current_node: str | None
    error: str | None
    events: list[RunEventResponse]
