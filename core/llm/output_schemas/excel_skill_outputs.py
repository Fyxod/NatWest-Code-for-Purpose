"""
Output schemas for the Excel Skill — LLM-generated plans for Excel file creation.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from core.llm.output_schemas.base import LLMOutputBase


class SheetColumnSpec(BaseModel):
    """Specification for a single column in an Excel sheet."""

    name: str = Field(description="Column header name")
    source: str = Field(
        description=(
            "Data source descriptor. One of: "
            "'sql' (column comes from the SQL query result), "
            "'formula:<excel_formula>' (computed column, e.g. 'formula:=SUM(B2:B100)'), "
            "'static:<value>' (constant value for all rows, e.g. 'static:USD'), "
            "'nlp:<instruction>' (requires LLM interpretation, e.g. 'nlp:classify sentiment as positive/negative/neutral')"
        )
    )
    data_type: str = Field(
        default="text",
        description="Data type: 'text', 'number', 'date', 'currency', 'percentage'",
    )
    number_format: Optional[str] = Field(
        default=None,
        description="Excel number format string, e.g. '#,##0.00', '0%', 'yyyy-mm-dd'",
    )


class SheetSpec(BaseModel):
    """Specification for a single sheet in the Excel workbook."""

    sheet_name: str = Field(description="Name of the sheet tab")
    description: str = Field(
        description="Brief description of what this sheet contains"
    )
    columns: List[SheetColumnSpec] = Field(
        description="Column definitions for this sheet"
    )
    source_query: Optional[str] = Field(
        default=None,
        description="SQL SELECT query to fetch the base data from spreadsheet tables. Required if any column source is 'sql'.",
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="Column name to sort by, prefix with '-' for descending (e.g. '-revenue')",
    )
    filter_condition: Optional[str] = Field(
        default=None,
        description="SQL WHERE clause fragment to filter rows (e.g. 'revenue > 1000')",
    )
    group_by: Optional[List[str]] = Field(
        default=None,
        description="Column names to group by for pivot-style aggregation",
    )
    aggregations: Optional[dict] = Field(
        default=None,
        description="Aggregation functions per column when group_by is set, e.g. {'revenue': 'sum', 'count': 'count'}",
    )


class ChartSpec(BaseModel):
    """Specification for a chart to embed in the Excel workbook."""

    chart_type: str = Field(
        description="Chart type: 'bar', 'line', 'pie', 'scatter', 'column'"
    )
    title: str = Field(description="Chart title")
    sheet_name: str = Field(description="Which sheet to place the chart on")
    x_column: str = Field(description="Column name for the X axis / categories")
    y_columns: List[str] = Field(
        description="Column name(s) for the Y axis / data series"
    )


class ExcelSkillPlan(LLMOutputBase):
    """LLM-generated plan for creating an Excel workbook."""

    file_name: str = Field(
        description="Suggested file name without extension (e.g. 'sales_report_q3')"
    )
    description: str = Field(
        description="Brief description of what this Excel file contains"
    )
    sheets: List[SheetSpec] = Field(
        description="List of sheets to create in the workbook"
    )
    charts: Optional[List[ChartSpec]] = Field(
        default=None,
        description="Charts to create in the workbook",
    )
    summary_sheet: bool = Field(
        default=False,
        description="Whether to add a summary sheet with key metrics at the beginning",
    )


class NLPColumnResult(LLMOutputBase):
    """LLM output for NLP-based column interpretation (e.g., sentiment analysis)."""

    values: List[str] = Field(
        description="List of interpreted values, one per input row, in the same order as the input data"
    )
