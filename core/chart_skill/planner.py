"""Chart skill planner — asks LLM for a structured chart plan."""

from typing import List, Optional

from core.llm.client import invoke_llm
from core.llm.output_schemas.chart_skill_outputs import ChartSkillPlan
from core.llm.prompts.chart_skill_prompts import chart_plan_prompt


async def generate_chart_plan(
    user_request: str,
    available_schema: Optional[str],
    available_documents: Optional[List[dict]],
    preferred_chart_type: Optional[str] = None,
    prior_sql_query: Optional[str] = None,
    web_search_results: Optional[List[dict]] = None,
    allow_self_knowledge: bool = True,
    allow_web_search: bool = False,
    web_context_already_fetched: bool = False,
) -> ChartSkillPlan:
    prompt = chart_plan_prompt(
        user_request=user_request,
        available_schema=available_schema,
        available_documents=available_documents,
        preferred_chart_type=preferred_chart_type,
        prior_sql_query=prior_sql_query,
        web_search_results=web_search_results,
        allow_self_knowledge=allow_self_knowledge,
        allow_web_search=allow_web_search,
        web_context_already_fetched=web_context_already_fetched,
    )

    plan = await invoke_llm(
        response_schema=ChartSkillPlan,
        contents=prompt,
    )

    return ChartSkillPlan.model_validate(plan)
