"""
Chart Skill API — sidebar/chat-triggered chart generation and artifact management.

Endpoints:
  POST   /chart-skill/generate                     — kick off async chart generation
  GET    /chart-skill/status/{id}                  — poll generation status
  GET    /chart-skill/list/{thread_id}             — list generated charts
  GET    /chart-skill/item/{thread_id}/{chart_id}  — fetch chart artifact JSON
  GET    /chart-skill/download/{thread_id}/{name}  — download chart JSON/CSV
  DELETE /chart-skill/{thread_id}/{tracking_id}    — delete chart + metadata
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

router = APIRouter(tags=["Chart Skill"])


class ChartGenerateRequest(BaseModel):
    thread_id: str
    request_text: str = Field(
        description="Natural-language description of chart to create"
    )
    chart_type: str | None = Field(
        default=None, description="Optional preferred chart type"
    )
    source_document_ids: list[str] | None = Field(
        default=None,
        description="Optional list of document IDs to use as data sources",
    )


def _get_status_dir(user_id: str, thread_id: str) -> str:
    return f"data/{user_id}/threads/{thread_id}/chart_exports"


@router.post("/chart-skill/generate")
async def generate_chart(request: Request, body: ChartGenerateRequest = Body(...)):
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId
    thread_id = body.thread_id

    tracking_id = str(uuid.uuid4())
    status_dir = _get_status_dir(user_id, thread_id)
    os.makedirs(status_dir, exist_ok=True)
    status_path = os.path.join(status_dir, f"status_{tracking_id}.json")
    await write_pending_status(status_path)

    async def _generate():
        try:
            from core.chart_skill.pipeline import generate_chart as run_pipeline

            result = await run_pipeline(
                user_request=body.request_text,
                user_id=user_id,
                thread_id=thread_id,
                source_doc_ids=(
                    body.source_document_ids
                    if body.source_document_ids is not None
                    else []
                ),
                preferred_chart_type=body.chart_type,
                allow_self_knowledge=True,
                allow_web_search=True,
            )

            await write_result(
                status_path,
                {
                    "chart_id": result.chart_id,
                    "title": result.title,
                    "description": result.description,
                    "chart_type": result.chart_type,
                    "x_key": result.x_key,
                    "y_keys": result.y_keys,
                    "row_count": result.row_count,
                    "item_url": result.item_url,
                    "download_json_url": result.download_json_url,
                    "download_csv_url": result.download_csv_url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "request_text": body.request_text,
                },
            )
        except Exception as e:
            await write_failed_status(status_path, str(e))
            print(f"[ChartSkill:route] Generation failed: {e}")

    asyncio.create_task(_generate())

    return JSONResponse(
        content={
            "status": False,
            "message": "Generating chart...",
            "tracking_id": tracking_id,
        }
    )


@router.get("/chart-skill/status/{tracking_id}")
async def get_status(request: Request, tracking_id: str):
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId

    import glob

    pattern = f"data/{user_id}/threads/*/chart_exports/status_{tracking_id}.json"
    matches = glob.glob(pattern)
    if not matches:
        raise HTTPException(status_code=404, detail="Tracking ID not found")

    status_path = matches[0]
    gen_status = await read_generation_status(status_path)
    if gen_status is None:
        raise HTTPException(status_code=404, detail="Status file not found")

    if gen_status["state"] == "pending":
        return JSONResponse(content={"status": False, "message": "Generating chart..."})
    if gen_status["state"] == "failed":
        return JSONResponse(
            content={"status": False, "failed": True, "error": gen_status["error"]}
        )

    return JSONResponse(content={"status": True, "result": gen_status["data"]})


@router.get("/chart-skill/list/{thread_id}")
async def list_charts(request: Request, thread_id: str):
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId
    status_dir = _get_status_dir(user_id, thread_id)

    if not os.path.exists(status_dir):
        return JSONResponse(content={"charts": []})

    charts = []
    for filename in os.listdir(status_dir):
        if not filename.startswith("status_") or not filename.endswith(".json"):
            continue

        status_path = os.path.join(status_dir, filename)
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if "_status" in data:
            continue

        chart_id = data.get("chart_id", "")
        item_path = os.path.join(status_dir, f"chart_{chart_id}.json")
        csv_path = os.path.join(status_dir, f"chart_{chart_id}.csv")
        if not chart_id or not os.path.exists(item_path):
            continue

        tracking_id = filename[len("status_") : -len(".json")]
        charts.append(
            {
                "tracking_id": tracking_id,
                "chart_id": chart_id,
                "title": data.get("title", "Untitled chart"),
                "description": data.get("description", ""),
                "chart_type": data.get("chart_type", "bar"),
                "x_key": data.get("x_key", ""),
                "y_keys": data.get("y_keys", []),
                "row_count": data.get("row_count", 0),
                "item_url": data.get(
                    "item_url", f"/chart-skill/item/{thread_id}/{chart_id}"
                ),
                "download_json_url": f"/chart-skill/download/{thread_id}/chart_{chart_id}.json",
                "download_csv_url": (
                    f"/chart-skill/download/{thread_id}/chart_{chart_id}.csv"
                    if os.path.exists(csv_path)
                    else None
                ),
                "created_at": data.get("created_at", ""),
                "request_text": data.get("request_text", ""),
            }
        )

    charts.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return JSONResponse(content={"charts": charts})


@router.get("/chart-skill/item/{thread_id}/{chart_id}")
async def get_chart_item(request: Request, thread_id: str, chart_id: str):
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId
    file_path = (
        f"data/{user_id}/threads/{thread_id}/chart_exports/chart_{chart_id}.json"
    )
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Chart not found")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read chart: {e}")

    return JSONResponse(content={"status": True, "chart": data})


@router.delete("/chart-skill/{thread_id}/{tracking_id}")
async def delete_chart(request: Request, thread_id: str, tracking_id: str):
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId
    status_dir = _get_status_dir(user_id, thread_id)
    status_path = os.path.join(status_dir, f"status_{tracking_id}.json")

    if not os.path.exists(status_path):
        raise HTTPException(status_code=404, detail="Chart not found")

    chart_id = ""
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            chart_id = data.get("chart_id", "")
    except Exception:
        pass

    os.remove(status_path)

    if chart_id:
        json_path = os.path.join(status_dir, f"chart_{chart_id}.json")
        csv_path = os.path.join(status_dir, f"chart_{chart_id}.csv")
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)

    return JSONResponse(content={"deleted": True})


@router.get("/chart-skill/download/{thread_id}/{file_name}")
async def download_chart_artifact(request: Request, thread_id: str, file_name: str):
    payload = request.state.user
    if not payload:
        raise HTTPException(status_code=401, detail="User not authenticated")

    user_id = payload.userId

    if ".." in file_name or "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Invalid file name")

    export_dir = f"data/{user_id}/threads/{thread_id}/chart_exports"
    file_path = os.path.join(export_dir, file_name)

    # Backward compatibility: older metadata may reference {chart_id}.json/csv
    # while persisted files are named chart_{chart_id}.json/csv.
    if not os.path.exists(file_path):
        root, ext = os.path.splitext(file_name)
        if ext in {".json", ".csv"} and root and not root.startswith("chart_"):
            legacy_path = os.path.join(export_dir, f"chart_{root}{ext}")
            if os.path.exists(legacy_path):
                file_path = legacy_path

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "application/json"
    if file_name.endswith(".csv"):
        media_type = "text/csv"

    return FileResponse(path=file_path, filename=file_name, media_type=media_type)
