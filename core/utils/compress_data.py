import copy
import math

from core.utils.count_tokens import count_tokens


def compress_global_file_data(
    data: list[dict], max_tokens: int, gpu_model: str, prompt_offset: int = 0
):
    """
    Compresses the 'content' field of each dict in the list 'data' so that the total token count
    does not exceed (max_tokens - prompt_offset). Uses count_tokens(text, gpu_model) to count tokens.
    Shortens content as little as possible per iteration. If already fits, returns data unchanged.
    Args:
            data (list of dict): Each dict has 'title' and 'content'.
            max_tokens (int): The token limit.
            gpu_model (str): Model name for count_tokens.
            prompt_offset (int): Tokens to reserve (subtract from max_tokens).
    Returns:
            list of dict: Compressed data.
    """

    # Defensive copy
    docs = copy.deepcopy(data)
    limit = max_tokens - prompt_offset - 1000  # Extra buffer

    def total_tokens(docs):
        return sum(
            count_tokens(doc["title"] + "\n" + doc["content"], gpu_model)
            for doc in docs
        )

    if total_tokens(docs) <= limit:
        return docs

    # How much to trim per doc per iteration (in chars)
    min_trim = 10
    max_iters = 1000
    for _ in range(max_iters):
        current_tokens = total_tokens(docs)
        if current_tokens <= limit:
            break
        # Find docs with non-empty content
        nonempty = [i for i, doc in enumerate(docs) if len(doc["content"]) > min_trim]
        if not nonempty:
            break
        # Distribute trim across docs
        trim_per_doc = max(
            min_trim, math.ceil((current_tokens - limit) / max(len(nonempty), 1) * 4)
        )
        for i in nonempty:
            content = docs[i]["content"]
            if len(content) > trim_per_doc:
                docs[i]["content"] = content[:-trim_per_doc]
            else:
                docs[i]["content"] = ""
        # After trimming, check again
    return docs
