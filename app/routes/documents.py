import mimetypes
import os
from typing import Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from core.config import settings
from core.database import db
from core.models.user import UserJwtPayload

router = APIRouter(prefix="/data", tags=["documents"])

INLINE_MEDIA_PREFIXES = ("image/", "text/", "audio/", "video/")
INLINE_MEDIA_TYPES = {"application/json"}
DEFAULT_MEDIA_TYPE = "application/octet-stream"


def _extract_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", maxsplit=1)[1]
    token = request.query_params.get("token")
    return token


def _decode_token(token: Optional[str]) -> UserJwtPayload:
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token missing")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return UserJwtPayload(**payload)
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def _is_inline_media(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    return (
        mime_type.startswith(INLINE_MEDIA_PREFIXES) or mime_type in INLINE_MEDIA_TYPES
    )


def _get_thread_document(
    user_id: str, thread_id: str, file_name: str
) -> Optional[Dict]:
    projection = {f"threads.{thread_id}.documents": 1, "_id": 0}
    user = db.users.find_one({"userId": user_id}, projection)
    if not user:
        return None

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        return None

    documents = thread.get("documents", [])
    for document in documents:
        if document.get("file_name") == file_name:
            return document
    return None


@router.get("/{user_id}/threads/{thread_id}/uploads/{file_name:path}")
async def get_document(
    request: Request,
    user_id: str,
    thread_id: str,
    file_name: str,
):
    """Serve uploaded documents while enforcing ownership checks."""

    token = _extract_token(request)
    payload = _decode_token(token)

    if payload.userId != user_id:
        raise HTTPException(status_code=403, detail="Access denied for this document")

    clean_file_name = os.path.basename(file_name)
    if clean_file_name != file_name:
        raise HTTPException(status_code=400, detail="Invalid file name")

    document = _get_thread_document(user_id, thread_id, clean_file_name)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    upload_root = os.path.abspath(
        os.path.join("data", user_id, "threads", thread_id, "uploads")
    )
    file_path = os.path.abspath(os.path.join(upload_root, clean_file_name))

    if not file_path.startswith(upload_root):
        raise HTTPException(status_code=400, detail="Invalid document path")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file missing on server")

    mime_type, _ = mimetypes.guess_type(file_path)
    serve_inline = _is_inline_media(mime_type)

    safe_filename = document.get("title") or clean_file_name
    quoted_filename = quote(safe_filename)
    disposition = "inline" if serve_inline else "attachment"

    response = FileResponse(file_path, media_type=mime_type or DEFAULT_MEDIA_TYPE)
    response.headers["Content-Disposition"] = (
        f"{disposition}; filename*=UTF-8''{quoted_filename}"
    )
    return response
