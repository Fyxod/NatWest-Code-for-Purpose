"""Grounded inference prompt — used when the LLM cannot answer directly from retrieved
chunks but the context is rich enough for analytical reasoning.

Triggered by: action='failure' + use_self_knowledge=False + chunks available.
The LLM reasons on top of the document content rather than refusing to answer.
"""

from typing import Any, Dict, List, Optional

from core.llm.prompts.thread_context import build_thread_context_block

# Prepended in the node (not the prompt) so it is always present, verbatim.
GROUNDED_INFERENCE_PREFIX = (
    "> **Analytical Inference Notice:** The retrieved documents do not directly answer "
    "this question. The following is a reasoned analysis grounded in the document "
    "content, supplemented by general knowledge where noted.\n\n---\n\n"
)


def _format_chunks(chunks: List[Dict[str, Any]], max_chunks: int = 15) -> str:
    """Format retrieved chunk dicts into a readable block for the prompt."""
    parts = []
    for i, chunk in enumerate(chunks[:max_chunks]):
        content = chunk.get("content", chunk.get("page_content", "")).strip()
        meta = chunk.get("metadata", {})
        title = chunk.get("title") or meta.get("title", "Document")
        page = chunk.get("page_no") or meta.get("page_number", "")
        page_str = f", page {page}" if page else ""
        parts.append(f"[Excerpt {i + 1} — {title}{page_str}]\n{content}")
    return "\n\n---\n\n".join(parts)


def grounded_inference_prompt(
    chunks: List[Dict[str, Any]],
    question: str,
    thread_instructions: Optional[List[str]] = None,
) -> list:
    """Build the grounded inference prompt.

    The LLM is given the retrieved document excerpts as its foundation and is
    explicitly allowed — and required — to reason beyond the literal text to
    address analytical or inferential questions.

    Args:
        chunks: Retrieved document chunks from state.chunks.
        question: The user's original question.
        thread_instructions: Optional per-thread user instructions.

    Returns:
        List of prompt message dicts ready for invoke_llm.
    """
    contents = []

    # ── System role ──
    contents.append(
        {
            "role": "system",
            "parts": (
                "You are an analytical expert assistant.\n\n"
                "The user's question goes beyond what is explicitly stated in the retrieved "
                "document excerpts below. However, the document content provides a rich "
                "foundation. Your task is to reason analytically on top of this content.\n\n"
                "### Rules\n"
                "- Ground every major claim in the provided document excerpts.\n"
                "- You MAY draw on your general knowledge to extend, interpret, and apply "
                "what the documents describe — especially for questions about use cases, "
                "implications, comparisons, recommendations, or strategic applications.\n"
                "- Clearly signal when you are citing the document vs. reasoning beyond it:\n"
                "  - Document-supported: *'The document states...'*, *'According to the paper...'*\n"
                "  - Inference / extension: *'This suggests...'*, *'One could infer...'*, "
                "*'Drawing from general knowledge...'*, *'A natural application would be...'*\n"
                "- Do NOT fabricate specific numbers, citations, or claims that are not in "
                "the documents or your verified knowledge.\n"
                "- If the question is entirely outside the document's domain, state that "
                "clearly and answer from general knowledge only.\n\n"
                "### Output format\n"
                "Use Markdown with headings (`##`, `###`), bullet points, and **bold** key "
                "terms. Keep each idea concise. End with a short summary.\n"
            ),
        }
    )

    # ── Thread-level user instructions ──
    thread_ctx = build_thread_context_block(thread_instructions)
    if thread_ctx:
        contents.append(thread_ctx)

    # ── Retrieved document context ──
    chunk_text = _format_chunks(chunks)
    contents.append(
        {
            "role": "system",
            "parts": (
                "**Retrieved Document Excerpts (your grounding context):**\n\n"
                f"{chunk_text}\n"
            ),
        }
    )

    # ── User question ──
    contents.append(
        {
            "role": "user",
            "parts": (
                f"**Question:** {question}\n\n"
                "This question requires analytical reasoning that may go beyond what is "
                "explicitly written in the excerpts above. Use the document as your "
                "foundation and reason from there."
            ),
        }
    )

    # ── JSON schema reminder ──
    contents.append(
        {
            "role": "user",
            "parts": "Return ONLY a valid JSON object matching the required schema. No markdown fencing, no commentary.",
        }
    )

    return contents
