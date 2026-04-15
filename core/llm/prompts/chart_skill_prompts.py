"""
Prompt builders for Chart Skill planning.
"""

import json
from typing import List, Optional


def chart_plan_prompt(
    user_request: str,
    available_schema: Optional[str],
    available_documents: Optional[List[dict]],
    preferred_chart_type: Optional[str] = None,
    prior_sql_query: Optional[str] = None,
    web_search_results: Optional[List[dict]] = None,
    allow_self_knowledge: bool = True,
    allow_web_search: bool = False,
):
    """
    Build prompt for chart planning.

    The model returns a ChartSkillPlan with chart type, SQL query, and axis mapping.
    """
    system_prompt = (
        "You are an expert data visualization planner. "
        "Your task is to convert a user request into a robust chart plan.\n\n"
        "Return a JSON object that matches the schema exactly.\n"
        "Choose chart_type based on data semantics:\n"
        "- line: trends over time\n"
        "- bar: category comparisons\n"
        "- area: cumulative trends\n"
        "- pie: part-to-whole with few categories\n"
        "- scatter: relationship between two numeric variables\n"
        "- radar: multi-metric category comparison\n"
        "- composed: mixed multi-series visuals\n\n"
        "Rules:\n"
        "1. If spreadsheet SQL schema exists, provide sql_query using SELECT only.\n"
        "2. Prefer grouped/aggregated SQL when the user asks for summaries.\n"
        "3. x_key should be the category/time dimension.\n"
        "4. y_keys must be numeric series columns whenever possible.\n"
        "5. Do not invent columns that do not exist in schema/doc preview.\n"
        "6. Keep limit between 20 and 500 for interactive readability.\n"
        "7. If user explicitly asks chart type, honor it unless impossible.\n"
    )

    if allow_self_knowledge:
        system_prompt += (
            "8. You MAY use your own data-visualization knowledge (best practices, chart selection heuristics, "
            "aggregation strategy) to improve the plan.\n"
        )
    else:
        system_prompt += "8. Use ONLY the provided schema/doc/web context. Do NOT use outside/world knowledge.\n"

    if allow_web_search:
        system_prompt += (
            "9. If web context is provided, you may use it as additional evidence. "
            "Still prioritize local spreadsheet schema and uploaded document data for SQL columns/keys.\n"
        )
    else:
        system_prompt += "9. Do NOT rely on web/external information.\n"

    doc_json = json.dumps(available_documents or [], ensure_ascii=False, indent=2)
    web_json = json.dumps(web_search_results or [], ensure_ascii=False, indent=2)

    user_parts = [
        f"User request: {user_request}",
        (
            f"Preferred chart type: {preferred_chart_type}"
            if preferred_chart_type
            else "Preferred chart type: (none specified)"
        ),
        (
            f"Prior SQL query hint: {prior_sql_query}"
            if prior_sql_query
            else "Prior SQL query hint: (none)"
        ),
    ]

    if available_schema:
        user_parts.append("Available SQL schema:\n" f"```\n{available_schema}\n```")
    else:
        user_parts.append("Available SQL schema: (none)")

    user_parts.append(f"Available document previews:\n```json\n{doc_json}\n```")

    if allow_web_search:
        user_parts.append(f"Web search context (optional):\n```json\n{web_json}\n```")
    else:
        user_parts.append("Web search context: disabled")

    user_parts.append(
        "Return ONLY valid JSON. No markdown, no comments, no trailing commas."
    )

    return [
        {"role": "system", "parts": system_prompt},
        {"role": "user", "parts": "\n\n".join(user_parts)},
    ]
