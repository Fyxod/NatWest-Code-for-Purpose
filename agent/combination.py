from core.llm.client import invoke_llm
from core.llm.outputs import CombinationLLMOutput
from core.llm.prompts.combination_prompt import combination_prompt


async def combination_node(
    sub_answers: list,
    resolved_query: str,
    original_query: str,
    chunks: list | None = None,
) -> str:
    combined_prompt = combination_prompt(
        resolved_query=resolved_query or original_query,
        original_query=original_query,
        sub_answers=sub_answers,
        chunks=chunks,
    )

    result: CombinationLLMOutput = await invoke_llm(
        contents=combined_prompt,
        response_schema=CombinationLLMOutput,
    )

    return result.answer
