"""
Excel Skill Planner — uses LLM to generate an ExcelSkillPlan from the user's request.
"""

from typing import List, Optional

from core.llm.client import invoke_llm
from core.llm.output_schemas.excel_skill_outputs import ExcelSkillPlan
from core.llm.prompts.excel_skill_prompts import excel_plan_prompt


async def generate_excel_plan(
    user_request: str,
    available_schema: Optional[str],
    available_documents: Optional[List[dict]],
    prior_sql_query: Optional[str] = None,
) -> ExcelSkillPlan:
    """
    Call the LLM to generate a structured plan for the Excel workbook.

    Args:
        user_request: The user's natural-language request (e.g., "create a pivot of sales by region").
        available_schema: SQLiteManager schema string (table definitions), or None.
        available_documents: List of document metadata dicts, or None.
        prior_sql_query: A SQL query already executed in this conversation whose
            filtered result set the Excel should reflect. Passed as an advisory
            hint to the planner — the WHERE clause must be preserved, but JOINs
            and column selection are permitted.

    Returns:
        ExcelSkillPlan with sheets, columns, charts, etc.
    """
    prompt = excel_plan_prompt(
        user_request=user_request,
        available_schema=available_schema,
        available_documents=available_documents,
        prior_sql_query=prior_sql_query,
    )

    plan = await invoke_llm(
        response_schema=ExcelSkillPlan,
        contents=prompt,
    )

    plan = ExcelSkillPlan.model_validate(plan)

    # Sanitize file name
    plan.file_name = _sanitize_filename(plan.file_name)

    return plan


def _sanitize_filename(name: str) -> str:
    """Ensure the file name is safe for filesystem use."""
    import re

    # Remove anything that isn't alphanumeric, underscore, or hyphen
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized[:50] or "excel_export"
