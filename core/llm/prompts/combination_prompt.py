import json


def combination_prompt(
    resolved_query: str,
    original_query: str,
    sub_answers: list,
    chunks: list | None = None,
) -> list:
    """
    Build a chat prompt to synthesize multiple sub-answers into one coherent response.
    Returns the standard message-list format [{role, parts}] used by all other prompts.
    """
    sub_answers_json = json.dumps(sub_answers, indent=2, ensure_ascii=False)

    # Build chunk context string from deduplicated chunks (top chunks only)
    chunk_context = ""
    if chunks:
        chunk_parts = []
        for c in chunks[:15]:  # Cap to avoid token overflow
            title = c.get("title", "Unknown")
            page = c.get("page_no", "?")
            score = c.get("rerank_score", 0.0)
            content = c.get("content", "")
            chunk_parts.append(
                f"[{title}, Page {page}] (relevance: {score:.2f})\n{content}"
            )
        chunk_context = "\n\n---\n\n".join(chunk_parts)

    contents = [
        {
            "role": "system",
            "parts": (
                "You are an expert assistant for a Retrieval-Augmented Generation (RAG) system.\n\n"
                "Your job is to synthesize multiple partial answers into one coherent, well-structured response.\n\n"
                "### Rules\n"
                "1. The **Original Question** is what the user actually asked. The **Resolved Query** is a "
                "cleaned-up version. Use both to understand the full intent.\n"
                "2. Read all Sub_answers carefully. These are partial answers to sub-parts of the question.\n"
                "3. **Cross-reference** information across sub-answers. If sub-answer 1 identifies items "
                "(e.g., teams, projects, products, features) and sub-answer 2 provides attributes "
                "(e.g., achievements, metrics, status), MAP them together explicitly.\n"
                "4. If **Document Chunks** are provided, use them as primary evidence to fill gaps, "
                "verify claims, and extract specific details that sub-answers may have missed.\n"
                "5. Remove redundancy, but keep all distinct insights.\n"
                "6. If Sub_answers contradict each other or the chunks, note the discrepancy clearly.\n"
                "7. If any Sub_answer is missing or empty, attempt to answer that part from the Document Chunks. "
                "Only state 'information not found' if both the sub-answer AND chunks lack the information.\n"
                "8. Retain the formatting of any lists/headings/bullets from Sub_answers.\n"
                "9. Ensure the final answer is in **clear, structured Markdown** with headings, bullet points, "
                "and bold text for readability.\n"
                "10. Synthesize ONLY from the provided sub-answers and document chunks. Do not add external knowledge.\n\n"
                "### CRITICAL: Cross-Referencing\n"
                "When the original question asks about multiple related aspects of the same entities "
                "(e.g., 'projects AND achievements', 'features AND costs', 'teams AND their deliverables'), "
                "you MUST present them together — not as separate disconnected sections. For example:\n"
                "- **Good**: 'PF Team — Project: Payroll Automation — Achievement: 30% processing time reduction'\n"
                "- **Bad**: Section 1 lists projects, Section 2 lists achievements with no mapping between them.\n\n"
                "### Document Naming Rules\n"
                "- **ALWAYS** use the **exact document name/title** as it appears in the sub-answers or chunks.\n"
                "- **NEVER** use generic labels like 'Document 1', 'the first document', etc.\n"
                "- Inline citations in `[Document Title, Page X]` format MUST be preserved.\n\n"
                "### Table & Data Formatting\n"
                "- When presenting **comparative data**, use **HTML tables** for reliability:\n"
                "  <table><tr><th>Aspect</th><th>Item A</th><th>Item B</th></tr>"
                "<tr><td>Detail</td><td>Value</td><td>Value</td></tr></table>\n"
                "- Use tables for **numerical data** or when comparing 3+ items.\n\n"
                "### Output\n"
                "Return only the final synthesized answer. "
                "If the user asked for a comparison, use a side-by-side structure. "
                "Otherwise, provide a coherent narrative answer that integrates all sub-answers and chunk evidence.\n"
            ),
        },
        {
            "role": "user",
            "parts": (
                f'**Original Question:** "{original_query}"\n\n'
                f'**Resolved Query:** "{resolved_query}"\n\n'
                f"**Sub_answers:**\n{sub_answers_json}\n\n"
                + (
                    f"**Document Chunks (supporting evidence):**\n{chunk_context}\n\n"
                    if chunk_context
                    else ""
                )
                + "Synthesize these into a single, coherent Markdown answer. "
                "Cross-reference information across sub-answers and use document chunks to fill gaps."
            ),
        },
    ]

    return contents
