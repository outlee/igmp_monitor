from typing import Optional
from pydantic import BaseModel


class Alert(BaseModel):
    id: int
    channel_id: str
    channel_name: Optional[str] = None
    alert_type: str
    severity: str
    status: str
    message: Optional[str] = None
    started_at: str
    resolved_at: Optional[str] = None
    ack_at: Optional[str] = None
    thumbnail_path: Optional[str] = None


class AlertAck(BaseModel):
    note: Optional[str] = None
