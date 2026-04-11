"""
Excel Skill API — sidebar-triggered Excel generation and download.

Endpoints:
  POST /excel-skill/generate                       — kick off async Excel generation
  GET  /excel-skill/status/{id}                     — poll for completion
  GET  /excel-skill/list/{thread_id}                — list previously generated files
  GET  /excel-skill/download/{thread_id}/{filename} — download the .xlsx file
  DELETE /excel-skill/{thread_id}/{tracking_id}     — delete a generated file
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from core.utils.generation_status import (
    read_generation_status,
    write_failed_status,
    write_pending_status,
    write_result,
)

router = APIRouter(tags=["Excel Skill"])


# ─── Request Models ──────────────────────────────────────────────────

class ExcelGenerateRequest(BaseModel):
    thread_id: str
    request_text: str = Field(
        description="Natural-language description of the Excel file to create"
    )
    source_document_ids: list[str] | None = Field(
        default=None,
        description="Optional list of document IDs to use as data sources",
    )


# ─── Helpers ─────────────────────────────────────────────────────────

def _get_status_dir(user_id: str, thread_id: str) -> str:
    return f"data/{user_id}/threads/{thread_id}/excel_exports"


# ─── Generate ────────────────────────────────────────────────────────

@router.post("/excel-skill/generate")
async def generate_excel(request: Request, body: ExcelGenerateRequest = Body(...)):
    """Start async Excel file generation."""
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId
    thread_id = body.thread_id

    # Create tracking ID
    tracking_id = str(uuid.uuid4())
    status_dir = _get_status_dir(user_id, thread_id)
    os.makedirs(status_dir, exist_ok=True)
    status_path = os.path.join(status_dir, f"status_{tracking_id}.json")
    await write_pending_status(status_path)

    async def _generate():
        try:
            from core.excel_skill.pipeline import generate_excel as run_pipeline

            result = await run_pipeline(
                user_request=body.request_text,
                user_id=user_id,
                thread_id=thread_id,
                source_doc_ids=body.source_document_ids,
            )

            await write_result(
                status_path,
                {
                    "file_name": result.file_name,
                    "download_url": result.download_url,
                    "description": result.description,
                    "sheet_count": result.sheet_count,
                    "total_rows": result.total_rows,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "request_text": body.request_text,
                },
            )
        except Exception as e:
            await write_failed_status(status_path, str(e))
            print(f"[ExcelSkill:route] Generation failed: {e}")

    asyncio.create_task(_generate())

    return JSONResponse(
        content={
            "status": False,
            "message": "Generating Excel file...",
            "tracking_id": tracking_id,
        }
    )


# ─── Status ──────────────────────────────────────────────────────────

@router.get("/excel-skill/status/{tracking_id}")
async def get_status(request: Request, tracking_id: str):
    """Poll for Excel generation status."""
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId

    import glob

    pattern = f"data/{user_id}/threads/*/excel_exports/status_{tracking_id}.json"
    matches = glob.glob(pattern)
    if not matches:
        raise HTTPException(status_code=404, detail="Tracking ID not found")

    status_path = matches[0]
    gen_status = await read_generation_status(status_path)

    if gen_status is None:
        raise HTTPException(status_code=404, detail="Status file not found")

    if gen_status["state"] == "pending":
        return JSONResponse(
            content={"status": False, "message": "Generating Excel file..."}
        )
    elif gen_status["state"] == "failed":
        return JSONResponse(
            content={"status": False, "failed": True, "error": gen_status["error"]}
        )
    elif gen_status["state"] == "completed":
        return JSONResponse(
            content={"status": True, "result": gen_status["data"]}
        )


# ─── List ─────────────────────────────────────────────────────────────

@router.get("/excel-skill/list/{thread_id}")
async def list_excel_files(request: Request, thread_id: str):
    """List all previously generated Excel files for a thread."""
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId
    status_dir = _get_status_dir(user_id, thread_id)

    if not os.path.exists(status_dir):
        return JSONResponse(content={"files": []})

    files = []
    for filename in os.listdir(status_dir):
        if not filename.startswith("status_") or not filename.endswith(".json"):
            continue

        file_path = os.path.join(status_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        # Skip pending/failed status files (completed ones have no _status key)
        if "_status" in data:
            continue

        # Verify the .xlsx file still exists on disk
        xlsx_name = data.get("file_name", "")
        xlsx_path = os.path.join(status_dir, xlsx_name)
        if not xlsx_name or not os.path.exists(xlsx_path):
            continue

        # Extract tracking_id from filename: status_{tracking_id}.json
        tracking_id = filename[len("status_"):-len(".json")]

        files.append({
            "tracking_id": tracking_id,
            "file_name": data.get("file_name", ""),
            "download_url": data.get("download_url", ""),
            "description": data.get("description", ""),
            "sheet_count": data.get("sheet_count", 0),
            "total_rows": data.get("total_rows", 0),
            "created_at": data.get("created_at", ""),
            "request_text": data.get("request_text", ""),
        })

    # Sort newest first
    files.sort(key=lambda f: f.get("created_at", ""), reverse=True)

    return JSONResponse(content={"files": files})


# ─── Delete ───────────────────────────────────────────────────────────

@router.delete("/excel-skill/{thread_id}/{tracking_id}")
async def delete_excel_file(request: Request, thread_id: str, tracking_id: str):
    """Delete a generated Excel file and its status metadata."""
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId
    status_dir = _get_status_dir(user_id, thread_id)
    status_path = os.path.join(status_dir, f"status_{tracking_id}.json")

    if not os.path.exists(status_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Read status to find the .xlsx filename
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        xlsx_name = data.get("file_name", "")
    except Exception:
        xlsx_name = ""

    # Delete the status file
    os.remove(status_path)

    # Delete the .xlsx file if it exists
    if xlsx_name:
        xlsx_path = os.path.join(status_dir, xlsx_name)
        if os.path.exists(xlsx_path):
            os.remove(xlsx_path)

    return JSONResponse(content={"deleted": True})


# ─── Download ────────────────────────────────────────────────────────

@router.get("/excel-skill/download/{thread_id}/{filename}")
async def download_file(request: Request, thread_id: str, filename: str):
    """Serve the generated Excel file for download."""
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId

    # Security: ensure filename is safe
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = f"data/{user_id}/threads/{thread_id}/excel_exports/{filename}"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
