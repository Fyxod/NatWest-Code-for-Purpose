"""
Routes for thread management functionality.
"""

import asyncio
import datetime
import json
import os
import shutil
import uuid

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from core.database import db
from core.embeddings.vectorstore import (
    add_existing_document_to_store,
    delete_document_from_chroma,
    rebuild_bm25_after_deletion,
)
from core.models.document import Document, Page
from core.services.sqlite_manager import SQLiteManager
from core.services.triple_store import TripleStore
from core.models.thread import (
    AddExistingDocumentRequest,
    InstructionCreateRequest,
    InstructionUpdateRequest,
    ThreadCreateRequest,
    ThreadUpdateRequest,
)

router = APIRouter(prefix="/thread", tags=["thread"])


# ── Helpers ──


def _get_authenticated_user(request: Request):
    """Retrieve the authenticated user payload and database document."""

    payload = request.state.user
    if not payload:
        return (
            None,
            None,
            JSONResponse({"error": "User not authenticated"}, status_code=401),
        )

    user_id = payload.userId

    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        return None, None, JSONResponse({"error": "User not found"}, status_code=404)

    return payload, user, None


def _error(msg: str, status_code: int = 400) -> JSONResponse:
    """Return a consistent JSON error response with proper HTTP status code."""
    return JSONResponse({"error": msg}, status_code=status_code)


# ── Thread CRUD ──


@router.post("/")
async def create_thread(request: Request, thread_data: ThreadCreateRequest):
    """Create a new empty thread for the user."""

    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    # Create new thread
    thread_id = str(uuid.uuid4())[:7]
    now = datetime.datetime.now(datetime.timezone.utc)

    new_thread = {
        f"threads.{thread_id}": {
            "thread_name": thread_data.thread_name,
            "documents": [],
            "chats": [],
            "createdAt": now,
            "updatedAt": now,
            "instructions": [],
        }
    }

    # Add thread to user
    db.users.update_one({"userId": user_id}, {"$set": new_thread})

    return {
        "status": "success",
        "message": "Thread created successfully",
        "thread_id": thread_id,
        "thread_name": thread_data.thread_name,
    }


@router.get("/{thread_id}")
async def get_thread(request: Request, thread_id: str):
    """Get a specific thread for the authenticated user."""
    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    # Check if thread exists
    if thread_id not in user.get("threads", {}):
        return _error("Thread not found", 404)

    return {
        "status": "success",
        "thread": user["threads"][thread_id],
    }


@router.get("/")
async def get_threads(request: Request):
    """Get all threads for the authenticated user."""

    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    return {"status": "success", "threads": user.get("threads", {})}


@router.put("/{thread_id}")
async def update_thread(
    request: Request, thread_id: str, thread_data: ThreadUpdateRequest
):
    """Update thread name."""
    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    # Check if thread exists
    if thread_id not in user.get("threads", {}):
        return _error("Thread not found", 404)

    # Update thread name
    now = datetime.datetime.now(datetime.timezone.utc)
    db.users.update_one(
        {"userId": user_id},
        {
            "$set": {
                f"threads.{thread_id}.thread_name": thread_data.thread_name,
                f"threads.{thread_id}.updatedAt": now,
            }
        },
    )

    return {
        "status": "success",
        "message": "Thread name updated successfully",
        "thread_id": thread_id,
        "thread_name": thread_data.thread_name,
    }


@router.delete("/{thread_id}")
async def delete_thread(request: Request, thread_id: str):
    """Delete a thread for the authenticated user."""

    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        print(f"DELETE /thread/{thread_id} - auth error")
        return error_response

    user_id = payload.userId

    print(f"DELETE /thread/{thread_id} - User ID: {user_id}")

    if not thread_id:
        print(f"DELETE /thread/{thread_id} - Thread ID is required")
        return _error("Thread ID is required", 400)

    if thread_id not in user.get("threads", {}):
        print(f"DELETE /thread/{thread_id} - Thread not found")
        return _error("Thread not found", 404)

    try:
        # Remove thread from user
        result = db.users.update_one(
            {"userId": user_id}, {"$unset": {f"threads.{thread_id}": ""}}
        )

        if result.modified_count > 0:
            print(f"DELETE /thread/{thread_id} - Thread deleted successfully")
            return {
                "status": "success",
                "message": "Thread deleted successfully",
                "thread_id": thread_id,
            }
        else:
            print(f"DELETE /thread/{thread_id} - No documents modified")
            return {
                "status": "error",
                "message": "Failed to delete thread - no documents modified",
                "thread_id": thread_id,
            }
    except Exception as e:
        print(f"DELETE /thread/{thread_id} - Error deleting thread: {str(e)}")
        return _error(f"Error deleting thread: {str(e)}", 500)


@router.delete("/{thread_id}/document/{doc_id}")
async def delete_document(request: Request, thread_id: str, doc_id: str):
    """Delete a specific document from a thread, cleaning up all storage."""

    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return _error("Thread not found", 404)

    documents = thread.get("documents", [])
    doc_entry = next((d for d in documents if d.get("docId") == doc_id), None)
    if not doc_entry:
        return _error("Document not found in thread", 404)

    file_name = doc_entry.get("file_name", "")

    try:
        # 1. Remove from MongoDB
        now = datetime.datetime.now(datetime.timezone.utc)
        db.users.update_one(
            {"userId": user_id},
            {
                "$pull": {f"threads.{thread_id}.documents": {"docId": doc_id}},
                "$set": {f"threads.{thread_id}.updatedAt": now},
            },
        )

        # 2. Delete from ChromaDB
        try:
            await delete_document_from_chroma(user_id, thread_id, doc_id)
        except Exception as e:
            print(f"Warning: ChromaDB cleanup failed for doc {doc_id}: {e}")

        # 3. Rebuild BM25 index
        try:
            await asyncio.to_thread(
                rebuild_bm25_after_deletion, user_id, thread_id, doc_id
            )
        except Exception as e:
            print(f"Warning: BM25 rebuild failed for thread {thread_id}: {e}")

        # 4. Delete entity-relation triples for this document
        try:
            deleted_triples = await asyncio.to_thread(
                TripleStore.delete_document_triples, user_id, thread_id, doc_id
            )
            print(f"Deleted {deleted_triples} triples for doc {doc_id}")
        except Exception as e:
            print(f"Warning: Triple cleanup failed for doc {doc_id}: {e}")

        # 5. Drop SQLite tables for this document (spreadsheets)
        try:
            await asyncio.to_thread(
                SQLiteManager.drop_tables_for_document, user_id, thread_id, doc_id
            )
        except Exception as e:
            print(f"Warning: SQLite table cleanup failed for doc {doc_id}: {e}")

        # 6. Delete uploaded file from disk
        if file_name:
            upload_path = os.path.join(
                "data", user_id, "threads", thread_id, "uploads", file_name
            )
            if os.path.exists(upload_path):
                os.remove(upload_path)

        # 7. Delete parsed JSON from disk
        # Try new doc_id-keyed path first; fall back to old filename-stem path
        # for backward compatibility with documents indexed before this change.
        parsed_base = os.path.join("data", user_id, "threads", thread_id, "parsed")
        parsed_by_id = os.path.join(parsed_base, f"{doc_id}.json")
        if os.path.exists(parsed_by_id):
            os.remove(parsed_by_id)
        elif file_name:
            name_without_ext = os.path.splitext(file_name)[0]
            parsed_by_name = os.path.join(parsed_base, f"{name_without_ext}.json")
            if os.path.exists(parsed_by_name):
                os.remove(parsed_by_name)

        # 8. Delete extracted images directory from disk
        # Try new doc_id-keyed dir first; fall back to old filename-stem dir.
        images_root = os.path.join("data", user_id, "threads", thread_id, "images")
        images_by_id = os.path.join(images_root, doc_id)
        if os.path.isdir(images_by_id):
            shutil.rmtree(images_by_id, ignore_errors=True)
        elif file_name:
            name_without_ext = os.path.splitext(file_name)[0]
            images_by_name = os.path.join(images_root, name_without_ext)
            if os.path.isdir(images_by_name):
                shutil.rmtree(images_by_name, ignore_errors=True)

        # Return updated documents list
        updated_user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
        updated_docs = (
            updated_user.get("threads", {}).get(thread_id, {}).get("documents", [])
            if updated_user
            else []
        )

        return {
            "status": "success",
            "message": "Document deleted successfully",
            "thread_id": thread_id,
            "deleted_doc_id": doc_id,
            "documents": jsonable_encoder(updated_docs),
        }

    except Exception as e:
        print(f"Error deleting document {doc_id} from thread {thread_id}: {e}")
        return _error(f"Failed to delete document: {str(e)}", 500)


@router.post("/{thread_id}/documents/add-existing")
async def add_existing_document(
    request: Request,
    thread_id: str,
    body: AddExistingDocumentRequest,
):
    """Add an existing document from another thread without re-parsing/OCR."""

    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId
    source_thread_id = body.source_thread_id
    doc_id = body.doc_id

    # Validate target thread exists
    if thread_id not in user.get("threads", {}):
        return _error("Target thread not found", 404)

    # Validate source thread exists
    source_thread = user.get("threads", {}).get(source_thread_id)
    if not source_thread:
        return _error("Source thread not found", 404)

    # Cannot add to same thread
    if thread_id == source_thread_id:
        return _error("Source and target thread cannot be the same", 400)

    # Find document in source thread
    source_docs = source_thread.get("documents", [])
    doc_entry = next((d for d in source_docs if d.get("docId") == doc_id), None)
    if not doc_entry:
        return _error("Document not found in source thread", 404)

    # Prevent duplicates in target thread
    target_docs = user["threads"][thread_id].get("documents", [])
    if any(d.get("docId") == doc_id for d in target_docs):
        return _error("Document already exists in target thread", 409)

    file_name = doc_entry.get("file_name", "")
    if not file_name:
        return _error("Document has no associated file", 400)

    # Load parsed JSON from source thread.
    # New layout (post rag-pipeline-improvements): parsed/{doc_id}.json
    # Legacy layout: parsed/{filename_stem}.json — try new first, fall back for old data.
    name_without_ext = os.path.splitext(file_name)[0]
    parsed_dir = os.path.join("data", user_id, "threads", source_thread_id, "parsed")
    source_parsed_path = os.path.join(parsed_dir, f"{doc_id}.json")
    if not os.path.exists(source_parsed_path):
        legacy_path = os.path.join(parsed_dir, f"{name_without_ext}.json")
        if os.path.exists(legacy_path):
            source_parsed_path = legacy_path
        else:
            return _error(
                "Parsed document data not found. Please re-upload the document.", 404
            )

    try:
        with open(source_parsed_path, "r", encoding="utf-8") as f:
            doc_data = json.load(f)
    except Exception as e:
        return _error(f"Failed to read parsed document: {str(e)}", 500)

    # Reconstruct Document object (handle both key conventions)
    pages_raw = doc_data.get("content", doc_data.get("pages", []))
    pages = []
    for p in pages_raw:
        page_number = p.get("number", p.get("page_number", 1))
        page_text = p.get("text", "")
        page_images = p.get("images", [])
        pages.append(Page(number=page_number, text=page_text, images=page_images))

    doc_obj = Document(
        id=doc_data.get("id", doc_id),
        type=doc_data.get("type", doc_entry.get("type", "unknown")),
        file_name=file_name,
        content=pages,
        title=doc_data.get("title", doc_entry.get("title", "Untitled")),
        full_text=doc_data.get("full_text", ""),
    )

    try:
        # 1. Embed and index in vectorstore + BM25 (fast, no OCR)
        await add_existing_document_to_store(doc_obj, user_id, thread_id)

        # 2. Copy uploaded file to target thread
        source_upload = os.path.join(
            "data", user_id, "threads", source_thread_id, "uploads", file_name
        )
        target_upload_dir = os.path.join(
            "data", user_id, "threads", thread_id, "uploads"
        )
        os.makedirs(target_upload_dir, exist_ok=True)
        target_upload = os.path.join(target_upload_dir, file_name)
        if os.path.exists(source_upload) and not os.path.exists(target_upload):
            shutil.copy2(source_upload, target_upload)

        # 3. Copy parsed JSON to target thread using doc_id filename (new layout).
        target_parsed_dir = os.path.join(
            "data", user_id, "threads", thread_id, "parsed"
        )
        os.makedirs(target_parsed_dir, exist_ok=True)
        target_parsed = os.path.join(target_parsed_dir, f"{doc_id}.json")
        if not os.path.exists(target_parsed):
            shutil.copy2(source_parsed_path, target_parsed)

        # 4. Copy images directory if it exists.
        # New layout: images/{doc_id}/; legacy: images/{filename_stem}/.
        source_images_dir = os.path.join(
            "data", user_id, "threads", source_thread_id, "images", doc_id
        )
        if not os.path.isdir(source_images_dir):
            # Fall back to legacy filename-stem layout
            source_images_dir = os.path.join(
                "data", user_id, "threads", source_thread_id, "images", name_without_ext
            )
        target_images_dir = os.path.join(
            "data", user_id, "threads", thread_id, "images", doc_id
        )
        if os.path.isdir(source_images_dir) and not os.path.isdir(target_images_dir):
            shutil.copytree(source_images_dir, target_images_dir)

        # 5. Add document entry to MongoDB target thread
        now = datetime.datetime.now(datetime.timezone.utc)
        new_doc_entry = {
            "docId": doc_id,
            "title": doc_entry.get("title", "Untitled"),
            "type": doc_entry.get("type", "unknown"),
            "time_uploaded": now,
            "file_name": file_name,
        }
        db.users.update_one(
            {"userId": user_id},
            {
                "$push": {f"threads.{thread_id}.documents": new_doc_entry},
                "$set": {f"threads.{thread_id}.updatedAt": now},
            },
        )

        return {
            "status": "success",
            "message": "Document added to thread successfully",
            "thread_id": thread_id,
            "document": jsonable_encoder(new_doc_entry),
        }

    except Exception as e:
        print(f"Error adding existing document {doc_id} to thread {thread_id}: {e}")
        return _error(f"Failed to add document: {str(e)}", 500)


@router.get("/{thread_id}/chats")
async def get_thread_chats(
    request: Request,
    thread_id: str,
    skip: int = 0,
    limit: int = 50,
):
    """Get paginated chat messages for a thread."""
    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return JSONResponse({"error": "Thread not found"}, status_code=404)

    chats = thread.get("chats", [])
    total = len(chats)
    page = chats[skip : skip + limit]

    return {
        "status": "success",
        "chats": jsonable_encoder(page),
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.delete("/{thread_id}/chats/{chat_index}")
async def delete_chat_from_thread(request: Request, thread_id: str, chat_index: int):
    """Delete a specific chat message by index from a thread."""

    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return _error("Thread not found", 404)

    chats = thread.get("chats", [])

    if not isinstance(chat_index, int) or chat_index < 0 or chat_index >= len(chats):
        return _error("Invalid chat index", 400)

    updated_chats = chats[:chat_index] + chats[chat_index + 1 :]

    now = datetime.datetime.now(datetime.timezone.utc)

    db.users.update_one(
        {"userId": user_id},
        {
            "$set": {
                f"threads.{thread_id}.chats": updated_chats,
                f"threads.{thread_id}.updatedAt": now,
            }
        },
    )

    return {
        "status": "success",
        "message": "Chat deleted successfully",
        "thread_id": thread_id,
        "deleted_index": chat_index,
        "chats": jsonable_encoder(updated_chats),
    }


@router.delete("/{thread_id}/chats")
async def clear_thread_chats(request: Request, thread_id: str):
    """Remove all chat messages from a thread."""

    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    if thread_id not in user.get("threads", {}):
        return _error("Thread not found", 404)

    now = datetime.datetime.now(datetime.timezone.utc)

    db.users.update_one(
        {"userId": user_id},
        {
            "$set": {
                f"threads.{thread_id}.chats": [],
                f"threads.{thread_id}.updatedAt": now,
            }
        },
    )

    return {
        "status": "success",
        "message": "All chats cleared successfully",
        "thread_id": thread_id,
        "chats": [],
    }


# ── Thread Instructions ──


@router.get("/{thread_id}/instructions")
async def get_instructions(request: Request, thread_id: str):
    """Get all instructions for a thread."""
    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return _error("Thread not found", 404)

    return {
        "status": "success",
        "instructions": thread.get("instructions", []),
    }


@router.post("/{thread_id}/instructions")
async def add_instruction(
    request: Request, thread_id: str, body: InstructionCreateRequest
):
    """Add a new instruction to a thread."""
    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    if thread_id not in user.get("threads", {}):
        return _error("Thread not found", 404)

    instruction = {
        "id": str(uuid.uuid4())[:8],
        "text": body.text,
        "selected": True,
    }

    now = datetime.datetime.now(datetime.timezone.utc)
    db.users.update_one(
        {"userId": user_id},
        {
            "$push": {f"threads.{thread_id}.instructions": instruction},
            "$set": {f"threads.{thread_id}.updatedAt": now},
        },
    )

    return {
        "status": "success",
        "instruction": instruction,
    }


@router.put("/{thread_id}/instructions/{instruction_id}")
async def update_instruction(
    request: Request,
    thread_id: str,
    instruction_id: str,
    body: InstructionUpdateRequest,
):
    """Update an instruction's text or selected state."""
    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return _error("Thread not found", 404)

    instructions = thread.get("instructions", [])
    idx = next(
        (i for i, ins in enumerate(instructions) if ins["id"] == instruction_id), None
    )
    if idx is None:
        return _error("Instruction not found", 404)

    update_fields = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    if body.text is not None:
        update_fields[f"threads.{thread_id}.instructions.{idx}.text"] = body.text
    if body.selected is not None:
        update_fields[f"threads.{thread_id}.instructions.{idx}.selected"] = (
            body.selected
        )
    update_fields[f"threads.{thread_id}.updatedAt"] = now

    db.users.update_one({"userId": user_id}, {"$set": update_fields})

    # Return updated instruction
    updated = instructions[idx].copy()
    if body.text is not None:
        updated["text"] = body.text
    if body.selected is not None:
        updated["selected"] = body.selected

    return {
        "status": "success",
        "instruction": updated,
    }


@router.delete("/{thread_id}/instructions/{instruction_id}")
async def delete_instruction(request: Request, thread_id: str, instruction_id: str):
    """Delete an instruction from a thread."""
    payload, user, error_response = _get_authenticated_user(request)
    if error_response:
        return error_response

    user_id = payload.userId

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return _error("Thread not found", 404)

    instructions = thread.get("instructions", [])
    updated_instructions = [ins for ins in instructions if ins["id"] != instruction_id]

    if len(updated_instructions) == len(instructions):
        return _error("Instruction not found", 404)

    now = datetime.datetime.now(datetime.timezone.utc)
    db.users.update_one(
        {"userId": user_id},
        {
            "$set": {
                f"threads.{thread_id}.instructions": updated_instructions,
                f"threads.{thread_id}.updatedAt": now,
            }
        },
    )

    return {
        "status": "success",
        "message": "Instruction deleted successfully",
    }
