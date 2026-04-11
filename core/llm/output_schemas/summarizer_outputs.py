from typing import List

from pydantic import BaseModel, Field

from core.llm.output_schemas.base import LLMOutputBase


class SummarizerLLMOutputSingle(LLMOutputBase):
    summary: str = Field(description="The summary of the document.")


class SummarizerLLMOutputCombination(LLMOutputBase):
    summary: str = Field(description="The summary of the document.")


class SummarizerLLMOutput(LLMOutputBase):
    summaries: List[SummarizerLLMOutputSingle] = Field(
        description="List of summaries for each document."
    )


class GlobalSummarizerLLMOutput(LLMOutputBase):
    title: str = Field(
        description="A concise and descriptive title for the collection of documents."
    )
    summary: str = Field(
        description="The global summary of all provided document summaries."
    )
