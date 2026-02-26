from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from db.sqlite import get_db
from models.alert import Alert, AlertAck

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _row_to_alert(row) -> Alert:
    return Alert(
        id=row["id"],
        channel_id=row["channel_id"],
        channel_name=row["channel_name"],
        alert_type=row["alert_type"],
        severity=row["severity"],
        status=row["status"],
        message=row["message"],
        started_at=row["started_at"],
        resolved_at=row["resolved_at"],
        ack_at=row["ack_at"],
        thumbnail_path=row["thumbnail_path"],
    )


@router.get("", response_model=List[Alert])
async def list_alerts(
    status: Optional[str] = Query(default=None),
    channel_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
):
    db = await get_db()
    conditions = []
    params = []
    if status:
        conditions.append("status=?")
        params.append(status)
    if channel_id:
        conditions.append("channel_id=?")
        params.append(channel_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])
    async with db.execute(
        f"SELECT * FROM alerts {where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
        params,
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_alert(r) for r in rows]


@router.get("/{alert_id}", response_model=Alert)
async def get_alert(alert_id: int):
    db = await get_db()
    async with db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _row_to_alert(row)


@router.post("/{alert_id}/ack")
async def ack_alert(alert_id: int, body: AlertAck = AlertAck()):
    db = await get_db()
    await db.execute(
        "UPDATE alerts SET status='ACKNOWLEDGED', ack_at=CURRENT_TIMESTAMP WHERE id=?",
        (alert_id,),
    )
    await db.commit()
    return {"alert_id": alert_id, "status": "ACKNOWLEDGED"}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int):
    db = await get_db()
    await db.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
    await db.commit()
    return {"alert_id": alert_id, "deleted": True}
