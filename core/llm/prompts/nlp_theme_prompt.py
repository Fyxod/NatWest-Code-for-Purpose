"""
Lightweight prompt for chunked NLP theme extraction.

Designed to be fast — minimal instructions, small output schema.
Each chunk gets this prompt independently; results are merged after.
"""

from typing import List


def nlp_theme_extraction_prompt(
    entries: List[str],
    user_question: str,
    batch_number: int,
    total_batches: int,
) -> str:
    """
    Build a prompt for extracting themes/categories from a batch of text entries.

    Args:
        entries: List of text values to analyze (one per row)
        user_question: The original user question (for context on what to look for)
        batch_number: Which batch this is (1-indexed)
        total_batches: Total number of batches
    """
    data_str = "\n".join(f"{i + 1}. {entry}" for i, entry in enumerate(entries))

    return (
        "You are a data analyst performing theme extraction.\n\n"
        f"**User's question:** {user_question}\n\n"
        f"## Text Data (batch {batch_number}/{total_batches}, {len(entries)} entries)\n"
        f"{data_str}\n\n"
        "## Task\n"
        "Analyze the text entries above and identify the main themes, categories, or patterns.\n\n"
        "## Rules\n"
        "1. Identify 3-10 distinct themes (not too granular, not too broad).\n"
        "2. For each theme, count how many entries belong to it.\n"
        "3. Provide 2-3 short representative examples per theme (abbreviated if long).\n"
        "4. An entry can belong to multiple themes if applicable.\n"
        "5. Order themes by frequency (most common first).\n"
        f"6. Set `total_rows_analyzed` to {len(entries)}.\n\n"
        "Return ONLY a valid JSON object matching the required schema. "
        "No markdown fencing, no commentary.\n"
    )
