"""
Output schema for NLP theme extraction from large SQL result sets.

Used by the chunked theme extraction pipeline in sql_query_node
to analyze text data that exceeds the LLM context window.
"""

from typing import List

from pydantic import BaseModel, Field

from core.llm.output_schemas.base import LLMOutputBase


class ThemeItem(BaseModel):
    """A single theme/category extracted from text data."""

    theme: str = Field(description="Short name of the theme or category (e.g., 'Customer service complaints')")
    count: int = Field(description="Number of entries in this batch that belong to this theme")
    examples: List[str] = Field(
        description="2-3 representative example entries (verbatim or abbreviated) that illustrate this theme"
    )


class NLPThemeExtraction(LLMOutputBase):
    """LLM output for chunked NLP theme extraction."""

    themes: List[ThemeItem] = Field(
        description="List of themes/categories identified in the text data, ordered by frequency (most common first)"
    )
    total_rows_analyzed: int = Field(
        description="Total number of text entries analyzed in this batch"
    )
