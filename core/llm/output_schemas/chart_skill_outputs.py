"""
Output schemas for Chart Skill planning.
"""

from typing import List, Literal, Optional

from pydantic import Field

from core.llm.output_schemas.base import LLMOutputBase


class ChartSkillPlan(LLMOutputBase):
    """LLM-generated plan for creating an interactive chart."""

    title: str = Field(description="Human-friendly chart title.")
    description: str = Field(
        description="Short description of what this chart represents."
    )
    chart_type: Literal[
        "bar",
        "line",
        "area",
        "pie",
        "scatter",
        "radar",
        "composed",
    ] = Field(
        description="The best chart type for the user's request and available data."
    )
    sql_query: Optional[str] = Field(
        default=None,
        description=(
            "SQLite SELECT query to fetch chart data from spreadsheet tables. "
            "Required when spreadsheet SQL data is available."
        ),
    )
    x_key: Optional[str] = Field(
        default=None, description="Column name to use as x-axis/category key."
    )
    y_keys: List[str] = Field(
        default_factory=list,
        description="One or more numeric column names to plot as series.",
    )
    limit: Optional[int] = Field(
        default=300,
        description="Suggested maximum number of rows to visualize for readability.",
    )
