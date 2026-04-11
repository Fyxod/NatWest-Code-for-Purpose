"""
Routes for file upload functionality.
Routes:
-------
POST /upload/
    Handle multiple file uploads for a user, optionally associating them with a thread.
    Also supports creating a thread without files.
    Input (from frontend):
        - files: Optional list of files to upload (multipart/form-data)
        - thread_id: Optional string, existing thread ID to associate files with (form field)
        - thread_name: Optional string, name for a new thread if thread_id is not provided (form field)
        - User authentication must be present in request.state.user
    Behavior:
        - If no files are provided and thread_name is provided (and no thread_id): create a new thread and return it with empty documents.
        - If thread_id is provided and no files are provided: do nothing and return the thread_id with empty documents.
    Returns (JSON):
        - On success:
                "thread_id": <thread_id>,
                "documents": [
                        {"docId": <document_id>,
                         "title": <document_title>,
                         "type": <document_type>,
                         "time_uploaded": <datetime>,
                         "file_name": <file_name>}
                    ...
        - On error:
                "error": <error_message>
"""

import asyncio
import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.socket_handler import sio
from core.database import db
from core.embeddings.vectorstore import save_documents_to_store
from core.models.document import Documents
from core.parsers.process_files import process_files
from core.services.upload_files import upload_files
from core.studio_features.summarizer import summarize_documents

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/")
async def upload_file(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    thread_id: Optional[str] = Form(None),
    thread_name: Optional[str] = Form(None),
):
    """Handle multiple file uploads."""
    file_count = len(files) if files else 0
    print(f"Received upload request with {file_count} files")

    payload = request.state.user
    if not payload:
        print("User not authenticated")
        return {"error": "User not authenticated"}

    user_id = payload.userId
    await sio.emit(f"{user_id}/progress", {"message": "request for upload received"})
    # Find user in DB
    user = db.users.find_one({"userId": user_id}, {"_id": 0, "password": 0})
    if not user:
        print(f"User {user_id} not found in database")
        await sio.emit(f"{user_id}/progress", {"message": "User not found"})
        return {"error": "User not found"}

    now = datetime.datetime.now(datetime.timezone.utc)

    # Determine if we have files to process
    has_files = bool(files) and len(files) > 0

    # If no files provided
    if not has_files:
        if thread_id:
            # Validate the thread belongs to user, but make no modifications
            print(f"No files provided. Returning existing thread_id: {thread_id}")
            user_threads = user.get("threads", {})
            if thread_id not in user_threads:
                print(f"Thread {thread_id} not found for user {user_id}")
                await sio.emit(f"{user_id}/progress", {"message": "Thread not found"})
                return {"error": "Thread not found for the user"}

            return {
                "status": "success",
                "message": "No files provided; returning existing thread",
                "thread_id": thread_id,
                "documents": [],
            }
        else:
            # Create a new empty thread only if thread_name is provided
            if thread_name:
                print("No files provided. Creating a new thread only.")
                thread_id = str(uuid.uuid4())[:7]
                new_thread = {
                    f"threads.{thread_id}": {
                        "thread_name": thread_name or "New Thread",
                        "documents": [],
                        "chats": [],
                        "createdAt": now,
                        "updatedAt": now,
                    }
                }
                db.users.update_one({"userId": user_id}, {"$set": new_thread})
                return {
                    "status": "success",
                    "message": "Thread created with no files",
                    "thread_id": thread_id,
                    "documents": [],
                }
            else:
                print("No files and no thread_name provided")
                return {
                    "error": "No files provided. Provide thread_name to create a new thread or thread_id to use an existing one.",
                }

    # Files are provided; proceed with normal flow
    # Create new thread if thread_id not provided
    if not thread_id:
        print("Creating a new thread")
        thread_id = str(uuid.uuid4())[:7]
        new_thread = {
            f"threads.{thread_id}": {
                "thread_name": thread_name or "New Thread",
                "documents": [],
                "chats": [],
                "createdAt": now,
                "updatedAt": now,
            }
        }
        db.users.update_one({"userId": user_id}, {"$set": new_thread})
    else:
        print(f"Updating existing thread with ID: {thread_id}")
        # Check if thread exists for this user
        user_threads = user.get("threads", {})
        if thread_id not in user_threads:
            print(f"Thread {thread_id} not found for user {user_id}")
            return {"error": "Thread not found for the user"}

        db.users.update_one(
            {"userId": user_id},
            {
                "$set": {
                    f"threads.{thread_id}.updatedAt": now,
                }
            },
        )

    # Upload and parse files
    files_data = await upload_files(files, user_id, thread_id)
    if not files_data:
        return {"error": "No files uploaded or failed to upload files"}

    parsed_data: Documents = await process_files(files_data, user_id, thread_id)

    async def _safe_summarize(data):
        try:
            await summarize_documents(data)
        except Exception as e:
            print(f"[upload] Background summarization failed: {e}")

    asyncio.create_task(_safe_summarize(parsed_data.model_copy()))
    # Check if any documents were successfully parsed
    if not parsed_data.documents:
        return {"error": "No documents could be processed successfully"}

    # Build document objects for DB
    parsed_data_dict = parsed_data.model_dump()
    documents_to_add = [
        {
            "docId": doc.get("id"),
            "title": doc.get("title"),
            "type": doc.get("type"),
            "time_uploaded": now,
            "file_name": doc.get("file_name"),
        }
        for doc in parsed_data_dict.get("documents", [])
    ]

    # Add document objects to the thread
    db.users.update_one(
        {"userId": user_id},
        {
            "$push": {f"threads.{thread_id}.documents": {"$each": documents_to_add}},
            "$set": {f"threads.{thread_id}.updatedAt": now},
        },
    )

    # Save documents to vector store
    await save_documents_to_store(parsed_data, user_id, thread_id)

    return {
        "status": "success",
        "message": "Files uploaded and processed",
        "thread_id": thread_id,
        "documents": documents_to_add,
    }
