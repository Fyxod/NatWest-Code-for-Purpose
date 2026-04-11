from langchain_huggingface import HuggingFaceEmbeddings
import torch


def get_embedding_function():
    return HuggingFaceEmbeddings(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        model_kwargs={
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "trust_remote_code": True,
        },
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 128,
        },
        query_encode_kwargs={
            "prompt": "search_query: ",
        },
    )