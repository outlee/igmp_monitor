import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from db.influx import query_channel_metrics
from db.redis_client import get_redis
from db.sqlite import get_db
from models.channel import ChannelConfig, ChannelStatus, MetricPoint

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


@router.get("", response_model=List[ChannelStatus])
async def list_channels():
    db = await get_db()
    async with db.execute(
        "SELECT id, name, group_name, sort_order, multicast_ip, multicast_port FROM channels WHERE enabled=1 ORDER BY sort_order ASC"
    ) as cur:
        rows = await cur.fetchall()

    redis = await get_redis()
    channels = []
    for row in rows:
        channel_id = row["id"]
        data = await redis.hgetall(f"channel:{channel_id}:status")
        updated_at = float(data.get("updated_at", 0)) if data else 0
        now = time.time()
        is_offline = (now - updated_at > 30) if updated_at > 0 else True

        status = data.get("status", "OFFLINE") if data and not is_offline else "OFFLINE"
        channels.append(
            ChannelStatus(
                channel_id=channel_id,
                channel_name=data.get("channel_name", row["name"]) if data else row["name"],
                status=status,
                bitrate_kbps=float(data.get("bitrate_kbps", 0)) if data else 0.0,
                is_black=bool(int(data.get("is_black", 0))) if data else False,
                is_frozen=bool(int(data.get("is_frozen", 0))) if data else False,
                is_silent=bool(int(data.get("is_silent", 0))) if data else False,
                is_clipping=bool(int(data.get("is_clipping", 0))) if data else False,
                cc_errors_per_sec=float(data.get("cc_errors_per_sec", 0)) if data else 0.0,
                pcr_jitter_ms=float(data.get("pcr_jitter_ms", 0)) if data else 0.0,
                audio_rms=float(data.get("audio_rms", 0)) if data else 0.0,
                video_brightness=float(data.get("video_brightness", 0)) if data else 0.0,
                thumbnail_path=data.get("thumbnail_path", "") if data else "",
                updated_at=updated_at,
                group_name=row["group_name"] or "default",
                sort_order=row["sort_order"] or 0,
            )
        )
    return channels


@router.get("/stats/overview")
async def get_overview():
    redis = await get_redis()
    keys = await redis.keys("channel:*:status")
    stats = {"NORMAL": 0, "WARNING": 0, "ALARM": 0, "OFFLINE": 0, "total": 0}
    now = time.time()
    for key in keys:
        data = await redis.hgetall(key)
        if not data:
            continue
        updated_at = float(data.get("updated_at", 0))
        if now - updated_at > 30:
            stats["OFFLINE"] += 1
        else:
            s = data.get("status", "OFFLINE")
            if s in stats:
                stats[s] += 1
        stats["total"] += 1
    return stats


@router.get("/{channel_id}/metrics", response_model=List[MetricPoint])
async def get_channel_metrics(
    channel_id: str,
    range: str = Query(default="5m", pattern="^[0-9]+[smhd]$"),
):
    return await query_channel_metrics(channel_id, range)


@router.get("/{channel_id}", response_model=ChannelStatus)
async def get_channel(channel_id: str):
    db = await get_db()
    async with db.execute(
        "SELECT id, name, group_name, sort_order FROM channels WHERE id=?",
        (channel_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")

    redis = await get_redis()
    data = await redis.hgetall(f"channel:{channel_id}:status")
    updated_at = float(data.get("updated_at", 0)) if data else 0
    now = time.time()
    is_offline = (now - updated_at > 30) if updated_at > 0 else True
    status = data.get("status", "OFFLINE") if data and not is_offline else "OFFLINE"

    return ChannelStatus(
        channel_id=channel_id,
        channel_name=data.get("channel_name", row["name"]) if data else row["name"],
        status=status,
        bitrate_kbps=float(data.get("bitrate_kbps", 0)) if data else 0.0,
        is_black=bool(int(data.get("is_black", 0))) if data else False,
        is_frozen=bool(int(data.get("is_frozen", 0))) if data else False,
        is_silent=bool(int(data.get("is_silent", 0))) if data else False,
        is_clipping=bool(int(data.get("is_clipping", 0))) if data else False,
        cc_errors_per_sec=float(data.get("cc_errors_per_sec", 0)) if data else 0.0,
        pcr_jitter_ms=float(data.get("pcr_jitter_ms", 0)) if data else 0.0,
        audio_rms=float(data.get("audio_rms", 0)) if data else 0.0,
        video_brightness=float(data.get("video_brightness", 0)) if data else 0.0,
        thumbnail_path=data.get("thumbnail_path", "") if data else "",
        updated_at=updated_at,
        group_name=row["group_name"] or "default",
        sort_order=row["sort_order"] or 0,
    )


@router.post("/{channel_id}/enable")
async def toggle_channel(channel_id: str, enabled: bool = True):
    db = await get_db()
    await db.execute("UPDATE channels SET enabled=? WHERE id=?", (int(enabled), channel_id))
    await db.commit()
    return {"channel_id": channel_id, "enabled": enabled}
