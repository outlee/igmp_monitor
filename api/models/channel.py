from typing import List, Optional
from pydantic import BaseModel


class ChannelStatus(BaseModel):
    channel_id: str
    channel_name: str
    status: str
    bitrate_kbps: float = 0.0
    is_black: bool = False
    is_frozen: bool = False
    is_silent: bool = False
    is_clipping: bool = False
    is_mosaic: bool = False
    mosaic_ratio: float = 0.0
    is_stuttering: bool = False
    stutter_count: int = 0
    cc_errors_per_sec: float = 0.0
    pcr_jitter_ms: float = 0.0
    audio_rms: float = 0.0
    video_brightness: float = 0.0
    thumbnail_path: str = ""
    updated_at: float = 0.0
    group_name: str = "default"
    sort_order: int = 0


class ChannelConfig(BaseModel):
    id: str
    name: str
    multicast_ip: str
    multicast_port: int = 1234
    group_name: str = "default"
    sort_order: int = 0
    enabled: bool = True
    expected_bitrate_kbps: float = 0.0


class MetricPoint(BaseModel):
    time: str
    bitrate_kbps: float = 0.0
    cc_errors_per_sec: float = 0.0
    pcr_jitter_ms: float = 0.0
    video_brightness: float = 0.0
    audio_rms: float = 0.0
    is_black: int = 0
    is_frozen: int = 0
    is_silent: int = 0
    status: str = "NORMAL"


class ChannelCreate(BaseModel):
    name: str
    multicast_ip: str
    multicast_port: int = 1234
    group_name: str = "default"
    sort_order: int = 0
    enabled: bool = True
    expected_bitrate_kbps: float = 0.0


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    multicast_ip: Optional[str] = None
    multicast_port: Optional[int] = None
    group_name: Optional[str] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None
    expected_bitrate_kbps: Optional[float] = None


class ChannelManageItem(BaseModel):
    """用于管理界面展示，包含 disabled 频道"""
    id: str
    name: str
    multicast_ip: str
    multicast_port: int
    group_name: str
    sort_order: int
    enabled: bool
    expected_bitrate_kbps: float


class BatchImportRequest(BaseModel):
    csv_text: str


class BatchImportResult(BaseModel):
    success: int
    failed: int
    errors: List[str]
