"""
GLM-OCR Parser Module

Uses Ollama-served GLM-OCR (0.9B) for structured document OCR.
Outputs Markdown with proper tables, formulas, and layout preservation.

GLM-OCR achieves 94.62 on OmniDocBench V1.5 (#1 overall).
Architecture: CogViT encoder + PP-DocLayout-V3 + GLM-0.5B decoder.

Per official deployment guide (zai-org/GLM-OCR/examples/ollama-deploy):
  - Uses Ollama's native /api/generate endpoint (NOT /api/chat)
  - Model: glm-ocr:latest (or custom Modelfile variant)
  - Template: {{ .Prompt }} — prompt passed directly

Follows the project's async httpx pattern (see core/parsers/vlm.py).
"""

import asyncio
import base64
import io
import os
import time
import traceback

import httpx
from PIL import Image

from core.config import settings
from core.constants import GLM_OCR_MODEL, GLM_OCR_WORKERS

LOCAL_BASE_URL = settings.LOCAL_BASE_URL

# Prompts matching GLM-OCR's expected format (per Ollama model page)
GLM_OCR_TEXT_PROMPT = "Text Recognition:"
GLM_OCR_TABLE_PROMPT = "Table Recognition:"
GLM_OCR_FIGURE_PROMPT = "Figure Recognition:"

# Max image dimension — GLM-OCR handles higher res than the VLM
GLM_OCR_MAX_IMAGE_DIM = 2048

# Concurrency controls (lazy-init singletons)
_GLM_OCR_SEMAPHORE = None
_GLM_OCR_SEMAPHORE_LOCK = asyncio.Lock()


async def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore for concurrency limiting."""
    global _GLM_OCR_SEMAPHORE
    if _GLM_OCR_SEMAPHORE is not None:
        return _GLM_OCR_SEMAPHORE
    async with _GLM_OCR_SEMAPHORE_LOCK:
        if _GLM_OCR_SEMAPHORE is None:
            _GLM_OCR_SEMAPHORE = asyncio.Semaphore(GLM_OCR_WORKERS)
    return _GLM_OCR_SEMAPHORE


def _resize_image(image_bytes: bytes, max_dim: int) -> bytes:
    """Resize image so its longest side is at most max_dim pixels. Returns PNG bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if max(w, h) <= max_dim:
        return image_bytes  # Already small enough

    scale = max_dim / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    print(f"[GLM-OCR] Resized image {w}x{h} -> {new_w}x{new_h}")
    return buf.getvalue()


def _encode_image_base64(
    image_input, max_dim: int = GLM_OCR_MAX_IMAGE_DIM
) -> str:
    """Encode an image file path or raw bytes to a base64 string, resizing if needed."""
    if isinstance(image_input, str):
        with open(image_input, "rb") as f:
            raw = f.read()
    elif isinstance(image_input, bytes):
        raw = image_input
    else:
        raise TypeError(f"Expected str (path) or bytes, got {type(image_input)}")

    resized = _resize_image(raw, max_dim)
    return base64.b64encode(resized).decode("utf-8")


async def glm_ocr_parse(
    image_input,
    mode: str = "text",
    port: int = 5002, # GLM-OCR SDK server default port
) -> str:
    """
    Run GLM-OCR on a single image via the local GLM-OCR Python SDK Server.

    Uses standard /glmocr/parse with image data URIs.
    Requires the dual-service deployment:
      1. vLLM running on port 8080 (serves the raw GLM-OCR model)
      2. `python -m glmocr.server` running on port 5002 (handles PP-DocLayout-V3 & calls vLLM)

    Args:
        image_input: File path (str) or raw PNG bytes.
        mode: Recognition mode — "text", "table", "figure" (Ignored by SDK which infers layout automatically).
        port: GLM-OCR SDK server API port (default: 5002).

    Returns:
        Extracted Markdown string, or "" on failure.
    """
    try:
        start_time = time.time()
        # Get base64 without data URI prefix (we add it in the payload)
        image_b64 = _encode_image_base64(image_input)

        semaphore = await _get_semaphore()
        async with semaphore:
            # GLM-OCR SDK Server endpoint
            url = f"{LOCAL_BASE_URL}:{port}/glmocr/parse"

            payload = {
                # The SDK expects an array of Data URIs (or local paths)
                "images": [f"data:image/png;base64,{image_b64}"]
            }

            label = (
                os.path.basename(image_input)
                if isinstance(image_input, str)
                else "bytes"
            )
            print(f"[GLM-OCR] Sending {label} to Local SDK Server (port {port})...")

            # Use separate timeouts: fast connect, very long read time for layout + generation
            timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

            # The SDK returns {"result": "markdown..."} or similar
            result_data = response.json()
            
            # The SDK response schema varies by version:
            #   {"result": "markdown..."}
            #   {"responses": ["markdown..."]}
            #   {"markdown_result": "markdown...", "json_result": [...]}
            content = ""
            if "result" in result_data:
                content = result_data["result"]
            elif "markdown_result" in result_data:
                content = result_data["markdown_result"]
            elif "responses" in result_data and isinstance(result_data["responses"], list):
                content = "\n\n".join(result_data["responses"])
            else:
                # Unknown schema — log it but don't dump raw JSON into page text
                print(f"[GLM-OCR] Unexpected response keys: {list(result_data.keys())}")
                content = ""

            content = content.strip()

            elapsed = time.time() - start_time
            print(f"[GLM-OCR] Completed in {elapsed:.2f}s | {len(content)} chars extracted.")
            return content

    except httpx.ConnectError:
        print(f"[GLM-OCR] Connection refused at {LOCAL_BASE_URL}:{port}. Is the local GLM-OCR Python SDK Server running?")
        return ""
    except httpx.TimeoutException:
        print(f"[GLM-OCR] Request timed out. Layout inference + VLM may be overloaded.")
        return ""
    except httpx.HTTPStatusError as e:
        print(f"[GLM-OCR] HTTP error {e.response.status_code}: {e.response.text[:200]}")
        return ""
    except Exception as e:
        print(f"[GLM-OCR] Unexpected error: {e}")
        traceback.print_exc()
        return ""


async def glm_ocr_parse_concurrent(
    images: list,
    page_labels: list[str] | None = None,
    mode: str = "text",
    port: int = 5002,
    max_concurrent: int = 3,
) -> list[str]:
    """
    Process multiple images concurrently using async single-image GLM-OCR calls.

    Args:
        images: List of file paths (str) or raw bytes, one per page/image.
        page_labels: Optional labels for logging (e.g. ["Page 1", "Slide 3"]).
        mode: Recognition mode — "text", "table", or "figure".
        port: GLM-OCR SDK server API port (default 5002).
        max_concurrent: Max simultaneous GLM-OCR calls.

    Returns:
        List of extracted Markdown strings, one per input image.
        Empty string for images where extraction failed.
    """
    if not images:
        return []

    total = len(images)
    labels = page_labels or [f"Page {i + 1}" for i in range(total)]
    semaphore = asyncio.Semaphore(max_concurrent)

    print(
        f"[GLM-OCR] Concurrent processing: {total} images, max {max_concurrent} at a time"
    )
    overall_start = time.time()

    async def _process_one(idx: int, img_input) -> str:
        async with semaphore:
            print(f"[GLM-OCR] Starting {labels[idx]}...")
            result = await glm_ocr_parse(img_input, mode=mode, port=port)
            if result:
                print(f"[GLM-OCR] {labels[idx]} done ({len(result)} chars)")
            else:
                print(f"[GLM-OCR] {labels[idx]} returned empty")
            return result

    # Launch all tasks, semaphore limits concurrency
    tasks = [_process_one(i, img) for i, img in enumerate(images)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to empty strings
    final = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"[GLM-OCR] {labels[i]} failed with error: {r}")
            final.append("")
        else:
            final.append(r or "")

    elapsed = time.time() - overall_start
    extracted = sum(1 for r in final if r)
    print(
        f"[GLM-OCR] Concurrent processing complete: {extracted}/{total} images in {elapsed:.2f}s"
    )
    return final
