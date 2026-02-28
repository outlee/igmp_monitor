import csv
import io
import ipaddress
import re
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from db.influx import query_channel_metrics
from db.redis_client import get_redis
from db.sqlite import get_db
from models.channel import (
    BatchImportRequest,
    BatchImportResult,
    ChannelConfig,
    ChannelCreate,
    ChannelManageItem,
    ChannelStatus,
    ChannelUpdate,
    MetricPoint,
)

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
                is_mosaic=bool(int(data.get("is_mosaic", 0))) if data else False,
                mosaic_ratio=float(data.get("mosaic_ratio", 0)) if data else 0.0,
                is_stuttering=bool(int(data.get("is_stuttering", 0))) if data else False,
                stutter_count=int(data.get("stutter_count", 0)) if data else 0,
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


@router.get("/manage", response_model=List[ChannelManageItem])
async def list_channels_manage():
    """返回全部频道含disabled，用于管理界面"""
    db = await get_db()
    async with db.execute(
        "SELECT id, name, multicast_ip, multicast_port, group_name, sort_order, enabled, expected_bitrate_kbps "
        "FROM channels ORDER BY sort_order ASC"
    ) as cur:
        rows = await cur.fetchall()
    return [
        ChannelManageItem(
            id=row["id"],
            name=row["name"],
            multicast_ip=row["multicast_ip"],
            multicast_port=row["multicast_port"],
            group_name=row["group_name"] or "default",
            sort_order=row["sort_order"] or 0,
            enabled=bool(row["enabled"]),
            expected_bitrate_kbps=float(row["expected_bitrate_kbps"] or 0),
        )
        for row in rows
    ]


@router.post("/batch-import", response_model=BatchImportResult)
async def batch_import(body: BatchImportRequest):
    """批量导入CSV频道数据
    格式: 频道名,组播IP,端口,分组(可选)
    """
    errors: List[str] = []
    success = 0
    failed = 0

    db = await get_db()

    # Get current max channel id for auto-increment
    async with db.execute("SELECT id FROM channels ORDER BY id DESC LIMIT 1") as cur:
        last = await cur.fetchone()
    if last:
        last_num = int(re.sub(r"[^0-9]", "", last["id"]))
    else:
        last_num = 0

    # Get max sort_order
    async with db.execute("SELECT MAX(sort_order) as max_order FROM channels") as cur:
        max_order_row = await cur.fetchone()
        max_sort_order = max_order_row["max_order"] or 0

    lines = body.csv_text.strip().split("\n")
    rows_to_insert = []

    for idx, line in enumerate(lines):
        line_num = idx + 1
        line = line.strip()
        if not line:
            continue

        parts = line.split(",")
        if len(parts) < 3:
            errors.append(f"第{line_num}行: 格式错误，至少需要3列（频道名,组播IP,端口）")
            failed += 1
            continue

        name = parts[0].strip()
        ip_str = parts[1].strip()
        port_str = parts[2].strip()
        group = parts[3].strip() if len(parts) >= 4 else "default"

        if not name:
            errors.append(f"第{line_num}行: 频道名不能为空")
            failed += 1
            continue

        # Validate multicast IP
        try:
            ip = ipaddress.IPv4Address(ip_str)
            # Check if it's in multicast range (224.0.0.0 - 239.255.255.255)
            if not (224 <= int(ip.packed[0]) <= 239):
                errors.append(f"第{line_num}行: IP {ip_str} 不在组播地址范围(224.0.0.0-239.255.255.255)")
                failed += 1
                continue
        except ValueError:
            errors.append(f"第{line_num}行: IP地址格式错误 {ip_str}")
            failed += 1
            continue

        # Validate port
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                errors.append(f"第{line_num}行: 端口 {port} 超出范围(1-65535)")
                failed += 1
                continue
        except ValueError:
            errors.append(f"第{line_num}行: 端口号格式错误 {port_str}")
            failed += 1
            continue

        # Check for duplicate ip:port
        async with db.execute(
            "SELECT id FROM channels WHERE multicast_ip=? AND multicast_port=?",
            (str(ip), port),
        ) as cur:
            dup = await cur.fetchone()
        if dup:
            errors.append(f"第{line_num}行: 组播地址 {ip}:{port} 已被频道 {dup['id']} 占用")
            failed += 1
            continue

        last_num += 1
        max_sort_order += 1
        channel_id = f"ch{last_num:03d}"
        rows_to_insert.append((channel_id, name, str(ip), port, group, max_sort_order))

    # Insert valid rows
    for row in rows_to_insert:
        await db.execute(
            "INSERT INTO channels (id, name, multicast_ip, multicast_port, group_name, sort_order, enabled, expected_bitrate_kbps) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, 0)",
            (*row,),
        )
        success += 1

    await db.commit()
    return BatchImportResult(success=success, failed=failed, errors=errors)


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
        is_mosaic=bool(int(data.get("is_mosaic", 0))) if data else False,
        mosaic_ratio=float(data.get("mosaic_ratio", 0)) if data else 0.0,
        is_stuttering=bool(int(data.get("is_stuttering", 0))) if data else False,
        stutter_count=int(data.get("stutter_count", 0)) if data else 0,
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


@router.post("", response_model=ChannelManageItem, status_code=201)
async def create_channel(body: ChannelCreate):
    """创建新频道"""
    db = await get_db()

    # 生成自增 channel_id
    async with db.execute("SELECT id FROM channels ORDER BY id DESC LIMIT 1") as cur:
        last = await cur.fetchone()
    if last:
        last_num = int(re.sub(r"[^0-9]", "", last["id"]))
        new_id = f"ch{last_num + 1:03d}"
    else:
        new_id = "ch001"

    # 检查重复 ip:port
    async with db.execute(
        "SELECT id FROM channels WHERE multicast_ip=? AND multicast_port=?",
        (body.multicast_ip, body.multicast_port),
    ) as cur:
        dup = await cur.fetchone()
    if dup:
        raise HTTPException(
            status_code=400,
            detail=f"组播地址 {body.multicast_ip}:{body.multicast_port} 已被频道 {dup['id']} 占用",
        )

    await db.execute(
        "INSERT INTO channels (id, name, multicast_ip, multicast_port, group_name, sort_order, enabled, expected_bitrate_kbps) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            new_id,
            body.name,
            body.multicast_ip,
            body.multicast_port,
            body.group_name,
            body.sort_order,
            int(body.enabled),
            body.expected_bitrate_kbps,
        ),
    )
    await db.commit()

    return ChannelManageItem(
        id=new_id,
        name=body.name,
        multicast_ip=body.multicast_ip,
        multicast_port=body.multicast_port,
        group_name=body.group_name,
        sort_order=body.sort_order,
        enabled=body.enabled,
        expected_bitrate_kbps=body.expected_bitrate_kbps,
    )


@router.put("/{channel_id}", response_model=ChannelManageItem)
async def update_channel(channel_id: str, body: ChannelUpdate):
    """更新频道信息"""
    db = await get_db()

    # Check if channel exists
    async with db.execute("SELECT * FROM channels WHERE id=?", (channel_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")

    # If updating ip or port, check for duplicates
    if body.multicast_ip is not None or body.multicast_port is not None:
        new_ip = body.multicast_ip if body.multicast_ip is not None else row["multicast_ip"]
        new_port = body.multicast_port if body.multicast_port is not None else row["multicast_port"]

        async with db.execute(
            "SELECT id FROM channels WHERE multicast_ip=? AND multicast_port=? AND id!=?",
            (new_ip, new_port, channel_id),
        ) as cur:
            dup = await cur.fetchone()
        if dup:
            raise HTTPException(
                status_code=400,
                detail=f"组播地址 {new_ip}:{new_port} 已被频道 {dup['id']} 占用",
            )

    # Build SET clause
    fields = []
    params = []

    for field in ["name", "multicast_ip", "multicast_port", "group_name", "sort_order", "enabled", "expected_bitrate_kbps"]:
        val = getattr(body, field)
        if val is not None:
            fields.append(f"{field}=?")
            if field == "enabled":
                params.append(int(val))
            else:
                params.append(val)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(channel_id)
    await db.execute(f"UPDATE channels SET {', '.join(fields)} WHERE id=?", params)
    await db.commit()

    # Return updated channel
    async with db.execute(
        "SELECT id, name, multicast_ip, multicast_port, group_name, sort_order, enabled, expected_bitrate_kbps "
        "FROM channels WHERE id=?",
        (channel_id,),
    ) as cur:
        updated = await cur.fetchone()

    return ChannelManageItem(
        id=updated["id"],
        name=updated["name"],
        multicast_ip=updated["multicast_ip"],
        multicast_port=updated["multicast_port"],
        group_name=updated["group_name"] or "default",
        sort_order=updated["sort_order"] or 0,
        enabled=bool(updated["enabled"]),
        expected_bitrate_kbps=float(updated["expected_bitrate_kbps"] or 0),
    )


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str):
    """删除频道"""
    db = await get_db()

    # Check if channel exists
    async with db.execute("SELECT id FROM channels WHERE id=?", (channel_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")

    await db.execute("DELETE FROM channels WHERE id=?", (channel_id,))
    await db.commit()
    return {"channel_id": channel_id, "deleted": True}
