"""
Pydantic models for thread-related data and API requests.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


# ── Data Models ──


class ThreadInstruction(BaseModel):
    """A single user-defined instruction attached to a thread."""

    id: str
    text: str
    selected: bool = True


# ── Request Schemas ──


class ThreadCreateRequest(BaseModel):
    thread_name: str = "New Chat"


class ThreadUpdateRequest(BaseModel):
    thread_name: str


class InstructionCreateRequest(BaseModel):
    text: str


class InstructionUpdateRequest(BaseModel):
    text: Optional[str] = None
    selected: Optional[bool] = None


class InstructionBulkSelectRequest(BaseModel):
    instruction_ids: List[str]
    selected: bool


class AddExistingDocumentRequest(BaseModel):
    source_thread_id: str
    doc_id: str
