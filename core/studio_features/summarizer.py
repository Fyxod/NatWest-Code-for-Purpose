import asyncio
import datetime
import json
import os
import re
import time
from typing import List

import aiofiles

from app.socket_handler import sio
from core.constants import (
    SWITCHES,
)
from core.database import db
from core.llm.client import invoke_llm
from core.llm.outputs import (
    GlobalSummarizerLLMOutput,
    SummarizerLLMOutputCombination,
    SummarizerLLMOutputSingle,
)
from core.llm.prompts.summarizer_prompt import (
    combine_summaries_prompt,
    global_summarization_prompt,
    summarize_documents_prompt,
)
from core.models.document import Document, Documents


def limit_words(text, max_words=15000):
    words = text.split()  # Split text into words (whitespace-based)
    if len(words) > max_words:
        words = words[:max_words]  # Cut off after max_words
    return " ".join(words)


def build_chunk_summarizer_prompt(title: str, chunk_text: str) -> str:
    """
    Builds the summarizer prompt for a single chunk of a document.
    """
    formatted_chunk = {
        "title": title,
        "text": re.sub(r"[\x00\n\t]+", " ", chunk_text).strip(),
    }
    return summarize_documents_prompt(document=str(formatted_chunk))


def chunk_text(text: str, max_words: int = 10000) -> list[str]:
    """
    Splits the text into chunks of up to `max_words` words.
    """
    words = text.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


async def process_document_with_chunks(document: Document):
    """
    Summarizes a document with conditional chunking:
    - ≤10k words: summarize directly
    - 10k-11k words: summarize directly (avoid unnecessary chunking)
    - >11k words: split into chunks of ~10k and combine summaries
    """
    word_count = len(document.full_text.split())
    partial_summaries = []

    if word_count <= 11000:
        # Just one summary, no chunking
        prompt = build_chunk_summarizer_prompt(document.title, document.full_text)
        result = None
        for attempt in range(5):
            try:
                result = await invoke_llm(
                    response_schema=SummarizerLLMOutputSingle,
                    contents=prompt,
                )
                if result and result.summary and len(result.summary.split()) >= 5:
                    document.summary = result.summary
                    return
            except Exception as e:
                print(f"Error summarizing document {document.id}: {e}")
        print(f"Failed to summarize document {document.id}")
        return

    # If >11k words → chunk + combine
    chunks = chunk_text(document.full_text, max_words=10000)

    # Step 1: Summarize each chunk
    for idx, chunk in enumerate(chunks):
        prompt = build_chunk_summarizer_prompt(document.title, chunk)
        result = None
        for attempt in range(5):  # retry logic
            try:
                result = await invoke_llm(
                    response_schema=SummarizerLLMOutputSingle,
                    contents=prompt,
                )
                if result and result.summary and len(result.summary.split()) >= 5:
                    partial_summaries.append(result.summary)
                    print(
                        f"Successfully summarized chunk {idx} of document {document.id}"
                    )
                    break
            except Exception as e:
                print(f"Error summarizing chunk {idx} of document {document.id}: {e}")

        if not result:
            print(f"Failed to summarize chunk {idx} of document {document.id}")

    # Step 2: Combine partial summaries into final summary
    if partial_summaries:
        partial_summaries = json.dumps(
            partial_summaries,
            ensure_ascii=False,
        )

        combine_prompt = combine_summaries_prompt(
            title=document.title, partial_summaries=partial_summaries
        )
        try:
            combined_result = await invoke_llm(
                response_schema=SummarizerLLMOutputCombination,
                contents=combine_prompt,
            )
            if combined_result and combined_result.summary:
                document.summary = combined_result.summary
        except Exception as e:
            print(f"Error combining summaries for document {document.id}: {e}")


async def summarize_documents(parsed_data: Documents):
    parsed_dir = f"data/{parsed_data.user_id}/threads/{parsed_data.thread_id}/parsed"
    os.makedirs(parsed_dir, exist_ok=True)

    documents = parsed_data.documents

    async def process_document(i, document):
        await sio.emit(
            f"{parsed_data.user_id}/progress",
            {"message": f"Summarizing {document.title} in chunks"},
        )
        await process_document_with_chunks(document)

        if document.summary:
            await sio.emit(
                f"{parsed_data.user_id}/progress",
                {"message": f"Completed summary for {document.title}"},
            )
        else:
            await sio.emit(
                f"{parsed_data.user_id}/progress",
                {"message": f"Failed to summarize {document.title}"},
            )

    if SWITCHES["SUMMARIZATION"]:
        try:
            batch_size = 1
            total_docs = len(documents)
            for batch_start in range(0, total_docs, batch_size):
                batch = [
                    (i, documents[i])
                    for i in range(
                        batch_start, min(batch_start + batch_size, total_docs)
                    )
                ]
                await asyncio.gather(*(process_document(i, doc) for i, doc in batch))

            # Save per-document summaries
            for document in parsed_data.documents:
                document_dict = document.model_dump()
                document_dict["thread_id"] = parsed_data.thread_id
                document_dict["user_id"] = parsed_data.user_id
                document_json = json.dumps(document_dict, ensure_ascii=False)

                name, _ = os.path.splitext(document.file_name)
                json_file_path = os.path.join(parsed_dir, f"{name}.json")

                async with aiofiles.open(json_file_path, "w", encoding="utf-8") as f:
                    await f.write(document_json)
        except Exception as e:
            print(f"Error during summarization: {e}")

    if SWITCHES["SUMMARIZATION"]:
        await global_summarizer(parsed_data.user_id, parsed_data.thread_id)


async def global_summarizer(user_id: str, thread_id: str):
    """
    Asynchronously summarizes all documents for a user in a specific thread.
    """
    save_dir = f"data/{user_id}/threads/{thread_id}"
    parsed_dir = f"data/{user_id}/threads/{thread_id}/parsed"
    os.makedirs(parsed_dir, exist_ok=True)

    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        print(f"User with ID {user_id} not found")
        await sio.emit(f"{user_id}/{thread_id}/global", {"status": False})
        return
    user_threads = user.get("threads", {})

    if thread_id not in user_threads:
        print(f"No thread found with ID {thread_id} for user {user_id}")
        await sio.emit(f"{user_id}/{thread_id}/global", {"status": False})
        return

    summaries = []
    thread_documents = user_threads.get(thread_id, {}).get("documents", [])
    if not thread_documents:
        print(f"No documents found in thread {thread_id} for user {user_id}")
        await sio.emit(f"{user_id}/{thread_id}/global", {"status": False})
        return

    for document in thread_documents:
        file_name = document["file_name"]
        if not file_name:
            print(f"Document {document['id']} has no file name, skipping...")
            continue

        name, _ = os.path.splitext(file_name)
        json_file_path = os.path.join(parsed_dir, f"{name}.json")

        if not os.path.exists(json_file_path):
            print(f"Parsed file {json_file_path} does not exist, skipping...")
            continue

        async with aiofiles.open(json_file_path, "r", encoding="utf-8") as f:
            content = await f.read()
        document_data = json.loads(content)

        if document_data.get("summary"):
            summaries.append(
                {"title": document_data["title"], "summary": document_data["summary"]}
            )

    if not summaries:
        print(f"No summaries found for thread {thread_id} for user {user_id}")
        err_msg = "No individual summaries found. Please summarize individual documents before generating global summary."
        try:
            async with aiofiles.open(
                os.path.join(save_dir, "global_summary.json"), "w", encoding="utf-8"
            ) as f:
                await f.write(json.dumps({"error": err_msg}, ensure_ascii=False))
        except Exception:
            pass
        await sio.emit(f"{user_id}/{thread_id}/global", {"status": False})
        return

    summary_prompt = global_summarization_prompt(
        summaries=summaries,
    )

    try:
        start_time = time.time()
        print("Starting global summarization...")
        result: GlobalSummarizerLLMOutput = await invoke_llm(
            response_schema=GlobalSummarizerLLMOutput,
            contents=summary_prompt,
        )

        end_time = time.time()
        print(
            f"Global summarization completed in LLM response time {end_time - start_time:.2f} seconds"
        )
        # save the global summary to a json file
        global_summary_path = os.path.join(save_dir, "global_summary.json")

        result_dict = result.model_dump()

        async with aiofiles.open(global_summary_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(result_dict, indent=2, ensure_ascii=False))
        await sio.emit(f"{user_id}/{thread_id}/global", {"status": True})

        if result.title:
            await updateThread(user_id, thread_id, result.title)

    except Exception as e:
        print(f"Error during global summarization: {e}")
        try:
            async with aiofiles.open(
                os.path.join(save_dir, "global_summary.json"), "w", encoding="utf-8"
            ) as f:
                await f.write(
                    json.dumps(
                        {"error": f"Summarization failed: {e}"}, ensure_ascii=False
                    )
                )
        except Exception:
            pass


async def updateThread(user_id: str, thread_id: str, updated_title: str):
    now = datetime.datetime.now(datetime.timezone.utc)
    db.users.update_one(
        {"userId": user_id},
        {
            "$set": {
                f"threads.{thread_id}.thread_name": updated_title,
                f"threads.{thread_id}.updatedAt": now,
            }
        },
    )

    event_name = f"{user_id}/title_update"
    event_data = {"thread_id": thread_id, "new_title": updated_title}

    await sio.emit(event_name, event_data)
