def doc_batch_prompt(
    chunks: str,
    user_question: str,
    batch_number: int,
    total_batches: int,
) -> str:
    """
    Lightweight prompt for processing one batch of document chunks.
    Used in MapReduce when the total retrieved context exceeds the model context window.
    """
    return (
        "You are analyzing a subset of document excerpts to answer a user's question.\n\n"
        f"This is batch {batch_number} of {total_batches}. You are seeing a subset of the full document set. "
        "Other batches are being processed in parallel and results will be combined.\n\n"
        f"**User Question:** {user_question}\n\n"
        f"**Document Excerpts (batch {batch_number}/{total_batches}):**\n{chunks}\n\n"
        "**Instructions:**\n"
        "1. Answer the user's question using ONLY the document excerpts shown above.\n"
        "2. Be thorough — extract all relevant facts, figures, and insights from these excerpts.\n"
        "3. If the excerpts are not relevant to the question, respond with exactly: [NO RELEVANT INFO]\n"
        "4. Do NOT speculate about content in other batches.\n"
        "5. Attribute information to document titles when known.\n\n"
        "Return ONLY a valid JSON object:\n"
        '{"answer": "your answer based on this batch of document excerpts"}'
    )
