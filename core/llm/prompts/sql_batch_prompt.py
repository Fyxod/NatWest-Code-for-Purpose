def sql_batch_prompt(
    data: str,
    user_question: str,
    batch_number: int,
    total_batches: int,
) -> str:
    """
    Lightweight prompt for processing one batch of a large SQL result.
    Used in MapReduce when the full result exceeds the model context window.
    """
    return (
        "You are analyzing a portion of a SQL query result to answer a user's question.\n\n"
        f"This is batch {batch_number} of {total_batches}. You are seeing a subset of the full dataset. "
        "Other batches are being processed in parallel and results will be combined.\n\n"
        f"**User Question:** {user_question}\n\n"
        f"**Data (batch {batch_number}/{total_batches}):**\n{data}\n\n"
        "**Instructions:**\n"
        "1. Answer the user's question based ONLY on the data shown above.\n"
        "2. If the question asks for counts, totals, or aggregations — provide them for THIS batch only "
        "(they will be combined later).\n"
        "3. If the question asks for listings or categorization — include all relevant items from this batch.\n"
        "4. If data in this batch is not relevant to the question, say so briefly.\n"
        "5. Be factual and concise. Do not speculate about data in other batches.\n\n"
        "Return ONLY a valid JSON object:\n"
        '{"answer": "your answer based on this batch of data"}'
    )
