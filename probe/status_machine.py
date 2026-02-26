from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ChannelStatus(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    ALARM = "ALARM"
    OFFLINE = "OFFLINE"


class AlertType(str, Enum):
    BLACK_SCREEN = "BLACK_SCREEN"
    FROZEN = "FROZEN"
    SILENT = "SILENT"
    CLIPPING = "CLIPPING"
    CC_ERROR = "CC_ERROR"
    PCR_JITTER = "PCR_JITTER"
    BITRATE_ABNORMAL = "BITRATE_ABNORMAL"
    OFFLINE = "OFFLINE"


@dataclass
class ChannelMetrics:
    channel_id: str
    channel_name: str
    is_offline: bool = False
    is_black: bool = False
    is_frozen: bool = False
    is_silent: bool = False
    is_clipping: bool = False
    cc_errors_per_sec: float = 0.0
    pcr_jitter_ms: float = 0.0
    bitrate_kbps: float = 0.0
    expected_bitrate_kbps: float = 0.0
    audio_rms: float = 0.0
    video_brightness: float = 0.0
    thumbnail_path: str = ""
    timestamp: float = 0.0


def evaluate_status(metrics: ChannelMetrics) -> ChannelStatus:
    if metrics.is_offline:
        return ChannelStatus.OFFLINE
    if metrics.is_black or metrics.is_frozen or metrics.is_silent:
        return ChannelStatus.ALARM
    warning = (
        metrics.is_clipping
        or metrics.cc_errors_per_sec > 5
        or metrics.pcr_jitter_ms > 40.0
        or (
            metrics.expected_bitrate_kbps > 0
            and abs(metrics.bitrate_kbps - metrics.expected_bitrate_kbps) / metrics.expected_bitrate_kbps > 0.3
        )
    )
    if warning:
        return ChannelStatus.WARNING
    return ChannelStatus.NORMAL


def get_active_alerts(metrics: ChannelMetrics) -> List[AlertType]:
    alerts = []
    if metrics.is_offline:
        alerts.append(AlertType.OFFLINE)
        return alerts
    if metrics.is_black:
        alerts.append(AlertType.BLACK_SCREEN)
    if metrics.is_frozen:
        alerts.append(AlertType.FROZEN)
    if metrics.is_silent:
        alerts.append(AlertType.SILENT)
    if metrics.is_clipping:
        alerts.append(AlertType.CLIPPING)
    if metrics.cc_errors_per_sec > 5:
        alerts.append(AlertType.CC_ERROR)
    if metrics.pcr_jitter_ms > 40.0:
        alerts.append(AlertType.PCR_JITTER)
    if (
        metrics.expected_bitrate_kbps > 0
        and abs(metrics.bitrate_kbps - metrics.expected_bitrate_kbps) / metrics.expected_bitrate_kbps > 0.3
    ):
        alerts.append(AlertType.BITRATE_ABNORMAL)
    return alerts
