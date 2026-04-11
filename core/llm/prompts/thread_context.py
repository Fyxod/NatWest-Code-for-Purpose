"""
Shared helper for injecting thread-level user instructions into any prompt.
"""

from typing import Dict, List, Optional


def build_thread_context_block(
    thread_instructions: Optional[List[str]] = None,
) -> Optional[Dict[str, str]]:
    """
    Return a system-role message block containing the user's thread-level
    instructions, or ``None`` if there are no instructions.

    Both ``main_prompt`` and ``self_knowledge_prompt`` call this so the
    wording stays consistent and there is a single place to update.
    """
    if not thread_instructions:
        return None

    numbered = "\n".join(
        f"{i + 1}. {inst}" for i, inst in enumerate(thread_instructions)
    )

    return {
        "role": "system",
        "parts": (
            "### User-Provided Context for This Thread\n"
            "The user has shared the following information, context, and preferences for this thread. "
            "This is **first-class supplied data** — treat every item below as if the user stated it "
            "directly in their question. You MUST actively use this information when answering "
            "any question where it is relevant:\n\n"
            f"{numbered}\n"
        ),
    }
