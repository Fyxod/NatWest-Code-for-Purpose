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
        "scatter3d",
        "bubble",
        "radar",
        "composed",
        "heatmap",
        "treemap",
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
    needs_web_search: bool = Field(
        default=False,
        description=(
            "Set true when you have little/no context to confidently plan the chart "
            "and require external web context first."
        ),
    )
    web_search_queries: List[str] = Field(
        default_factory=list,
        description=(
            "2-4 focused web search queries to gather missing context. "
            "Only populate when needs_web_search=true and web context is not yet provided."
        ),
    )


class ChartSkillWebData(LLMOutputBase):
    """Structured chart rows generated from web context and/or self-knowledge."""

    x_key: str = Field(description="X-axis/category key present in each row.")
    y_keys: List[str] = Field(
        default_factory=list,
        description="Numeric series keys present in each row.",
    )
    rows: List[dict] = Field(
        default_factory=list,
        description=(
            "Array of row objects. Each row must contain x_key and one or more "
            "numeric y_keys."
        ),
    )
