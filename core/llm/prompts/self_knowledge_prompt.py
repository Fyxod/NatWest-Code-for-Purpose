from typing import Any, Dict, List, Optional

from core.constants import INTERNAL, EXTERNAL
from core.llm.prompts.thread_context import build_thread_context_block


def self_knowledge_prompt(
    messages: list,
    question: str,
    thread_instructions: Optional[List[str]] = None,
):
    contents = []
    contents.append(
        {
            "role": "system",
            "parts": (
                "You are an expert assistant that answers questions based on your own knowledge.\n"
                "Your job is to give **clear, structured, and modular answers** using Markdown formatting.\n\n"
                "### Guidelines\n"
                "- Use **headings (`##`, `###`)** for major sections.\n"
                "- Use **bullet points** and **numbered lists** to organize ideas.\n"
                "- Highlight important terms in **bold** and examples in *italics*.\n"
                "- Avoid long paragraphs — keep each idea short and readable.\n"
                "- Merge overlapping ideas and remove redundancy.\n\n"
                "### Output Structure\n"
                "```\n"
                "## Overview\n"
                "(Brief explanation)\n\n"
                "## Key Details\n"
                "- **Point 1:** Explanation...\n"
                "- **Point 2:** Explanation...\n\n"
                "## Additional Insights\n"
                "- *Optional examples, comparisons, or clarifications.*\n\n"
                "## Summary\n"
                "(Final concise conclusion)\n"
                "```\n"
            ),
        }
    )

    # Thread-level user context
    thread_ctx = build_thread_context_block(thread_instructions)
    if thread_ctx:
        contents.append(thread_ctx)

    # Conversation history (disabled — messages is always empty now)
    if messages:
        for m in messages:
            if m.type == "human":
                contents.append({"role": "user", "parts": m.content})
            elif m.type == "ai":
                contents.append({"role": "assistant", "parts": m.content})

    # Final user question
    contents.append({"role": "user", "parts": f"**Question:** {question}\n"})

    # JSON formatting requirement
    contents.append(
        {
            "role": "user",
            "parts": "Return ONLY a valid JSON object matching the required schema. No markdown fencing, no commentary.",
        }
    )

    return contents
