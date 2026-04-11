from typing import List, Optional

from pydantic import BaseModel, Field

from core.llm.output_schemas.base import LLMOutputBase


class Node(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    children: List["Node"] = []

    class Config:
        arbitrary_types_allowed = True


class FlatNode(BaseModel):
    id: str
    title: str
    parent_id: Optional[str] = None


class MindMapOutput(LLMOutputBase):
    mind_map: List[FlatNode] = Field(description="The generated mind map structure.")


class FlatNodeWithDescription(BaseModel):
    id: str
    title: str
    description: str


class FlatNodeWithDescriptionOutput(LLMOutputBase):
    mind_map: List[FlatNodeWithDescription]


class MindMap(BaseModel):
    user_id: str
    thread_id: str
    document_id: str
    roots: List[Node]


class GlobalMindMap(BaseModel):
    user_id: str
    thread_id: str
    roots: List[Node]
