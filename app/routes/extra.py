import asyncio
import json
import os
from typing import List

import aiofiles
from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

from core.database import db
from core.models.document import Document, Documents
from core.studio_features.mind_map import create_mind_map_global
from core.utils.generation_status import (
    write_pending_status,
    read_generation_status,
)

router = APIRouter(prefix="", tags=["extra"])
_mind_map_jobs_in_progress: set[str] = set()


class MindMapRequest(BaseModel):
    thread_id: str
    document_id: str
    regenerate: bool = False


class GlobalSummaryRequest(BaseModel):
    thread_id: str
    regenerate: bool = False


class MindMapGenerateRequest(BaseModel):
    thread_id: str
    regenerate: bool = False


def _mind_map_file_path(user_id: str, thread_id: str) -> str:
    mind_map_dir = f"data/{user_id}/threads/{thread_id}/mind_maps"
    name = f"{user_id}_{thread_id}_global_mind_map.json"
    return os.path.join(mind_map_dir, name)


async def _read_json(path: str) -> dict:
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()
    return json.loads(content)


async def _load_parsed_documents(
    user_id: str, thread_id: str, thread_documents: list[dict]
) -> List[Document]:
    parsed_dir = f"data/{user_id}/threads/{thread_id}/parsed"
    if not os.path.exists(parsed_dir):
        return []

    parsed_documents: List[Document] = []
    seen_paths: set[str] = set()

    for metadata in thread_documents:
        file_name = metadata.get("file_name")
        if not file_name:
            continue
        name, _ = os.path.splitext(file_name)
        file_path = os.path.join(parsed_dir, f"{name}.json")
        if not os.path.exists(file_path) or file_path in seen_paths:
            continue
        try:
            data = await _read_json(file_path)
            parsed_documents.append(Document.model_validate(data))
            seen_paths.add(file_path)
        except Exception:
            continue

    if parsed_documents:
        return parsed_documents

    for file_name in os.listdir(parsed_dir):
        if not file_name.endswith(".json"):
            continue
        file_path = os.path.join(parsed_dir, file_name)
        if file_path in seen_paths:
            continue
        try:
            data = await _read_json(file_path)
            parsed_documents.append(Document.model_validate(data))
            seen_paths.add(file_path)
        except Exception:
            continue

    return parsed_documents


async def _run_mind_map_generation(parsed_data: Documents, job_key: str):
    try:
        await create_mind_map_global(parsed_data)
    finally:
        _mind_map_jobs_in_progress.discard(job_key)


@router.post("/mindmap/generate")
async def generate_mind_map(request: Request, body: MindMapGenerateRequest = Body(...)):

    payload = request.state.user

    if not payload:
        return {"error": "User not authenticated"}

    user_id = payload.userId
    thread_id = body.thread_id

    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        return {"error": "User not found"}

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return {"error": "Thread not found"}

    thread_documents = thread.get("documents", [])
    if len(thread_documents) == 0:
        return {"mind_map": False, "message": "No documents found in the thread"}

    file_path = _mind_map_file_path(user_id, thread_id)
    if body.regenerate and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    job_key = f"{user_id}:{thread_id}"
    if job_key in _mind_map_jobs_in_progress:
        return {
            "mind_map": True,
            "status": False,
            "message": "Mind map creation under progress...",
        }

    if os.path.exists(file_path):
        try:
            data = await _read_json(file_path)
            return {"mind_map": True, "status": True, "data": data, "message": ""}
        except Exception:
            pass

    parsed_documents = await _load_parsed_documents(
        user_id, thread_id, thread_documents
    )
    if not parsed_documents:
        return {
            "mind_map": False,
            "message": "Parsed documents are not ready yet. Please generate summaries first.",
        }

    parsed_data = Documents(
        documents=parsed_documents,
        thread_id=thread_id,
        user_id=user_id,
    )

    _mind_map_jobs_in_progress.add(job_key)
    asyncio.create_task(_run_mind_map_generation(parsed_data, job_key))

    return {
        "mind_map": True,
        "status": False,
        "message": "Mind map creation started...",
    }


@router.get("/mindmap/{thread_id}")
async def get_mind_map(request: Request, thread_id: str):

    payload = request.state.user

    if not payload:
        return {"error": "User not authenticated"}

    user_id = payload.userId
    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        return {"error": "User not found"}

    thread = user["threads"].get(thread_id)
    if not thread:
        return {"error": "Thread not found"}

    if len(thread.get("documents", [])) == 0:
        return {"mind_map": False, "message": "No documents found in the thread"}

    file_path = _mind_map_file_path(user_id, thread_id)
    if os.path.exists(file_path):
        try:
            data = await _read_json(file_path)

            return {"mind_map": True, "status": True, "data": data, "message": ""}
        except Exception:
            pass

    job_key = f"{user_id}:{thread_id}"
    if job_key in _mind_map_jobs_in_progress:
        return {
            "mind_map": True,
            "status": False,
            "message": "Mind map creation under progress...",
        }

    return {
        "mind_map": False,
        "message": "Mind map not generated yet. Use Generate Mind Map in this modal to start.",
    }


@router.post("/summary")
async def get_summary(request: Request, body: MindMapRequest = Body(...)):

    payload = request.state.user

    if not payload:
        return {"error": "User not authenticated"}

    thread_id = body.thread_id
    document_id = body.document_id
    regenerate = body.regenerate
    print(f"Fetching summary for document_id: {document_id} in thread_id: {thread_id}")

    user_id = payload.userId
    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        return {"error": "User not found"}

    thread = user["threads"].get(thread_id)
    if not thread:
        return {"error": "Thread not found"}

    parsed_dir = f"data/{user_id}/threads/{thread_id}/parsed"
    if not os.path.exists(parsed_dir):
        return {"error": "Parsed directory does not exist"}

    for filename in os.listdir(parsed_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(parsed_dir, filename)
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                data = json.loads(content)
                if isinstance(data, dict) and data.get("id") == document_id:
                    # On regenerate, clear existing summary and kick off generation
                    if regenerate:
                        data["summary"] = ""
                        data["_summary_status"] = "pending"
                        async with aiofiles.open(
                            file_path, "w", encoding="utf-8"
                        ) as write_f:
                            await write_f.write(json.dumps(data, ensure_ascii=False))

                        asyncio.create_task(_generate_document_summary(data, file_path))
                        return {
                            "status": False,
                            "error": "Summary not yet generated. Generating...",
                        }

                    # Check if summary generation failed
                    if data.get("_summary_status") == "failed":
                        return {
                            "status": False,
                            "error": data.get(
                                "_summary_error", "Summary generation failed"
                            ),
                            "failed": True,
                        }

                    # Check if summary is being generated (pending)
                    if data.get("_summary_status") == "pending":
                        return {
                            "status": False,
                            "error": "Summary not yet generated. Generating...",
                        }

                    # Summary exists — return it
                    if data.get("summary"):
                        return {"status": True, "summary": data.get("summary")}

                    # No summary yet — trigger first-time on-demand generation
                    data["_summary_status"] = "pending"
                    async with aiofiles.open(
                        file_path, "w", encoding="utf-8"
                    ) as write_f:
                        await write_f.write(json.dumps(data, ensure_ascii=False))

                    asyncio.create_task(_generate_document_summary(data, file_path))
                    return {
                        "status": False,
                        "error": "Summary not yet generated. Generating...",
                    }
            except Exception as e:
                continue

    return {
        "status": False,
        "error": "Document not found in parsed data",
        "failed": True,
    }


async def _generate_document_summary(data: dict, file_path: str):
    """Background task to generate/regenerate a single document summary."""
    from core.models.document import Document
    from core.studio_features.summarizer import process_document_with_chunks

    try:
        doc = Document.model_validate(data)
        await process_document_with_chunks(doc)
        # Reload latest state to avoid race condition with concurrent writes
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            reread_content = await f.read()
        reread_data = json.loads(reread_content)
        reread_data["summary"] = doc.summary or ""
        reread_data.pop("_summary_status", None)
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(reread_data, ensure_ascii=False))
    except Exception as e:
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                err_content = await f.read()
            err_data = json.loads(err_content)
            err_data["_summary_status"] = "failed"
            err_data["_summary_error"] = str(e)
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(err_data, ensure_ascii=False))
        except Exception:
            pass
        print(f"Failed generating individual summary: {e}")


@router.post("/summary/global")
async def get_global_summary(request: Request, body: GlobalSummaryRequest = Body(...)):

    payload = request.state.user

    if not payload:
        return {"error": "User not authenticated"}

    thread_id = body.thread_id
    regenerate = body.regenerate
    print(f"Fetching global summary for thread_id: {thread_id}")

    user_id = payload.userId
    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        return {"error": "User not found"}

    thread = user["threads"].get(thread_id)
    if not thread:
        return {"error": "Thread not found"}

    thread_dir = f"data/{user_id}/threads/{thread_id}"
    file_path = os.path.join(thread_dir, "global_summary.json")

    if regenerate and os.path.exists(file_path):
        os.remove(file_path)

    if not os.path.exists(file_path):
        # Write pending status to prevent duplicate tasks from subsequent polls
        await write_pending_status(file_path)

        from core.studio_features.summarizer import global_summarizer

        asyncio.create_task(global_summarizer(user_id, thread_id))

        return {
            "status": False,
            "error": "Global Summary not yet generated. Generating...",
        }

    gen_status = await read_generation_status(file_path)
    if gen_status is None:
        return {
            "status": False,
            "error": "Global Summary not yet generated. Generating...",
        }
    elif gen_status["state"] == "pending":
        return {
            "status": False,
            "error": "Global Summary not yet generated. Generating...",
        }
    elif gen_status["state"] == "failed":
        return {
            "status": False,
            "error": gen_status["error"],
            "failed": True,
        }
    elif gen_status["state"] == "completed":
        data = gen_status["data"]
        if isinstance(data, dict):
            if "error" in data:
                return {"status": False, "error": data["error"], "failed": True}
            return {"status": True, "summary": data.get("summary")}

    return {
        "status": False,
        "error": "Global Summary not yet generated. Generating...",
    }
