from typing import Optional

from agent.graph_helpers import get_recent_history
from core.llm.client import invoke_llm
from core.llm.outputs import DecompositionLLMOutput
from core.llm.prompts.decomposition_prompt import decomposition_prompt


async def decomposition_node(
    question: str,
    messages: list,
    has_spreadsheet_data: bool = False,
    spreadsheet_schema: Optional[str] = None,
) -> DecompositionLLMOutput:
    recent_chat_history = get_recent_history(full_history=messages, turns=5)

    prompt = decomposition_prompt(
        recent_history=recent_chat_history,
        question=question,
        has_spreadsheet_data=has_spreadsheet_data,
        spreadsheet_schema=spreadsheet_schema,
    )

    result: DecompositionLLMOutput = await invoke_llm(
        contents=prompt,
        response_schema=DecompositionLLMOutput,
    )
    return result
