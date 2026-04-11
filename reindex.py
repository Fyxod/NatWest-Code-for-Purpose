"""
Re-indexing migration script for RAG pipeline optimization.

This script re-indexes all existing documents with:
1. New embedding model (nomic-ai/nomic-embed-text-v1.5)
2. Improved chunking (512 chars, sentence-boundary aware)
3. Contextual enrichment (title + page prepended)
4. BM25 index creation for hybrid search

Usage:
    python reindex.py

This will clear old ChromaDB data and rebuild everything from parsed documents.
"""

import asyncio
import json
import math
import os
import shutil
import sys
import time

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import db
from core.embeddings.vectorstore import (
    SEARCH_DOCUMENT_PREFIX,
    _build_and_save_bm25,
    chunk_page_text,
    embedding_function,
    get_vectorstore,
)


async def reindex_user(user_id: str):
    """Re-index all documents for a single user."""
    user = db.users.find_one({"userId": user_id}, {"_id": 0})
    if not user:
        print(f"  [SKIP] User {user_id} not found in database")
        return

    threads = user.get("threads", {})
    if not threads:
        print(f"  [SKIP] User {user_id} has no threads")
        return

    # Clear old ChromaDB data for this user
    chroma_path = os.path.join("data", user_id, "chroma")
    if os.path.exists(chroma_path):
        print(f"  [CLEAR] Removing old ChromaDB data at {chroma_path}")
        shutil.rmtree(chroma_path)

    # Clear old BM25 data for this user
    bm25_path = os.path.join("data", user_id, "bm25")
    if os.path.exists(bm25_path):
        print(f"  [CLEAR] Removing old BM25 data at {bm25_path}")
        shutil.rmtree(bm25_path)

    for thread_id, thread_data in threads.items():
        documents = thread_data.get("documents", [])
        if not documents:
            continue

        parsed_dir = os.path.join("data", user_id, "threads", thread_id, "parsed")
        if not os.path.exists(parsed_dir):
            print(f"  [SKIP] No parsed data for thread {thread_id}")
            continue

        print(f"  [THREAD] Re-indexing thread {thread_id} ({len(documents)} documents)")

        vectorstore = await asyncio.to_thread(get_vectorstore, user_id, thread_id)
        chunk_data = []

        for doc_info in documents:
            doc_id = doc_info.get("docId", "")
            file_name = doc_info.get("file_name", "")
            title = doc_info.get("title", "Untitled")

            if not file_name:
                continue

            name, _ = os.path.splitext(file_name)
            json_file = os.path.join(parsed_dir, f"{name}.json")

            if not os.path.exists(json_file):
                print(f"    [SKIP] Parsed file not found: {json_file}")
                continue

            with open(json_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            pages = doc_data.get("content", [])
            for page in pages:
                page_no = page.get("number", 1)
                page_text = page.get("text", "")
                if not page_text.strip():
                    continue

                chunks = chunk_page_text(page_text)
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{doc_id}_page{page_no}_chunk{i}"

                    # Contextual enrichment with search_document prefix
                    enriched_chunk = f"{SEARCH_DOCUMENT_PREFIX}Document: {title}\nPage {page_no}\n\n{chunk}"

                    metadata = {
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "document_id": doc_id,
                        "page_no": page_no,
                        "chunk_index": i,
                        "file_name": file_name,
                        "title": title,
                    }
                    chunk_data.append((chunk_id, enriched_chunk, metadata))

        if not chunk_data:
            print(f"    [SKIP] No chunks to index for thread {thread_id}")
            continue

        print(f"    [INDEX] {len(chunk_data)} chunks to embed and store")

        # Build BM25 index
        _build_and_save_bm25(chunk_data, user_id, thread_id)

        # Batch embed and upsert to ChromaDB
        batch_size = 5000
        total_batches = math.ceil(len(chunk_data) / batch_size)

        for batch_idx in range(total_batches):
            batch = chunk_data[batch_idx * batch_size : (batch_idx + 1) * batch_size]
            batch_ids, batch_texts, batch_metadatas = zip(*batch)

            start = time.time()
            embeddings = await asyncio.to_thread(
                embedding_function.embed_documents, list(batch_texts)
            )
            elapsed = time.time() - start
            print(
                f"    [EMBED] Batch {batch_idx + 1}/{total_batches} in {elapsed:.2f}s"
            )

            await asyncio.to_thread(
                vectorstore._collection.upsert,
                embeddings=embeddings,
                documents=list(batch_texts),
                metadatas=list(batch_metadatas),
                ids=list(batch_ids),
            )

        print(f"    [DONE] Thread {thread_id}: {len(chunk_data)} chunks indexed")


async def main():
    print("=" * 60)
    print("RAG Pipeline Re-indexing Migration")
    print("=" * 60)
    print()
    print("This will re-index all documents with:")
    print("  - nomic-embed-text-v1.5 search_document/search_query prefixes")
    print("  - Smaller chunks: 512 chars (was 1000)")
    print("  - Contextual enrichment: title + page prepended")
    print("  - BM25 index with improved tokenization")
    print()

    # Get all users
    users = list(db.users.find({}, {"userId": 1, "_id": 0}))
    print(f"Found {len(users)} users to re-index")
    print()

    total_start = time.time()
    for user in users:
        user_id = user["userId"]
        print(f"[USER] {user_id}")
        await reindex_user(user_id)
        print()

    total_time = time.time() - total_start
    print(f"Re-indexing complete in {total_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
