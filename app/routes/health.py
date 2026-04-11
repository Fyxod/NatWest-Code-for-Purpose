"""

Health check endpoint.

Expected Input:
    - Method: GET
    - No request body or query parameters required.

Returns:
    - JSON response with the current health status of the service.
    - Example: {"status": "ok"}
"""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    return {"status": "ok"}
