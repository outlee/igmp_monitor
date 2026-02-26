import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import REDIS_URL

router = APIRouter(prefix="/api/v1/sim", tags=["simulator"])
logger = logging.getLogger(__name__)

FAULT_TYPES = ["BLACK_SCREEN", "FROZEN", "SILENT", "PACKET_LOSS", "BITRATE_DROP"]


class FaultRequest(BaseModel):
    channel_id: str
    fault_type: str
    duration_sec: int = 30


class FaultClearRequest(BaseModel):
    channel_id: str


@router.post("/trigger")
async def trigger_fault(req: FaultRequest):
    if req.fault_type not in FAULT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown fault type: {req.fault_type}")
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        cmd = json.dumps({
            "action": "trigger_fault",
            "channel_id": req.channel_id,
            "fault_type": req.fault_type,
            "duration_sec": req.duration_sec,
        })
        await r.publish("sim_command", cmd)
        logger.info("Published sim fault command: %s", cmd)
        return {"status": "ok", "channel_id": req.channel_id, "fault_type": req.fault_type}
    finally:
        await r.aclose()


@router.post("/clear")
async def clear_fault(req: FaultClearRequest):
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        cmd = json.dumps({
            "action": "clear_fault",
            "channel_id": req.channel_id,
        })
        await r.publish("sim_command", cmd)
        return {"status": "ok", "channel_id": req.channel_id}
    finally:
        await r.aclose()


@router.get("/faults")
async def list_fault_types():
    return {"fault_types": FAULT_TYPES}
