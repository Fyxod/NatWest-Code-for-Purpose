from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.constants import SWITCHES

router = APIRouter(prefix="/settings", tags=["Settings"])

# Switches that require a server restart — cannot be toggled at runtime
_RESTART_REQUIRED = set()


class SwitchUpdate(BaseModel):
    value: bool


@router.get("/switches")
async def get_switches():
    """Return all feature switches and their current values."""
    return {"switches": SWITCHES}


@router.put("/switches/{key}")
async def update_switch(key: str, body: SwitchUpdate):
    """Toggle a feature switch at runtime (no server restart needed)."""
    if key not in SWITCHES:
        raise HTTPException(status_code=404, detail=f"Unknown switch: {key}")
    if key in _RESTART_REQUIRED:
        raise HTTPException(
            status_code=400, detail=f"{key} requires a server restart to change"
        )
    SWITCHES[key] = body.value
    print(f"[Settings] Switch {key} set to {body.value}")
    return {"key": key, "value": body.value}
