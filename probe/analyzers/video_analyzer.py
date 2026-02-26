import os
import time
from typing import Dict, Optional

import cv2
import numpy as np

from config import (
    BLACK_LUMA_THRESHOLD,
    FREEZE_DURATION_SEC,
    FREEZE_MSE_THRESHOLD,
    THUMBNAIL_DIR,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_QUALITY,
    THUMBNAIL_WIDTH,
)


class VideoAnalyzer:
    def __init__(self, channel_id: str, thumbnail_dir: str = THUMBNAIL_DIR):
        self.channel_id = channel_id
        self.thumbnail_dir = thumbnail_dir
        self.last_gray: Optional[np.ndarray] = None
        self.freeze_start: Optional[float] = None
        os.makedirs(thumbnail_dir, exist_ok=True)

    def analyze_frame(self, frame_bgr: np.ndarray, timestamp: float) -> Dict:
        result = {
            "is_black": False,
            "is_frozen": False,
            "brightness": 0.0,
            "thumbnail_path": "",
        }

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        result["brightness"] = brightness
        result["is_black"] = brightness < BLACK_LUMA_THRESHOLD

        if self.last_gray is not None:
            diff = gray.astype(np.float32) - self.last_gray.astype(np.float32)
            mse = float(np.mean(diff * diff))
            if mse < FREEZE_MSE_THRESHOLD:
                if self.freeze_start is None:
                    self.freeze_start = timestamp
                elif timestamp - self.freeze_start > FREEZE_DURATION_SEC:
                    result["is_frozen"] = True
            else:
                self.freeze_start = None
        else:
            self.freeze_start = None

        self.last_gray = gray

        is_alarm = result["is_black"] or result["is_frozen"]
        thumb_path = self._save_thumbnail(frame_bgr, timestamp, is_alarm)
        result["thumbnail_path"] = thumb_path
        return result

    def _save_thumbnail(self, frame_bgr: np.ndarray, ts: float, is_alarm: bool) -> str:
        thumb = cv2.resize(frame_bgr, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
        latest_path = os.path.join(self.thumbnail_dir, f"latest_{self.channel_id}.jpg")
        cv2.imwrite(latest_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, THUMBNAIL_QUALITY])

        if is_alarm:
            alarm_path = os.path.join(
                self.thumbnail_dir,
                f"alarm_{self.channel_id}_{int(ts)}.jpg",
            )
            cv2.imwrite(alarm_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return alarm_path
        return latest_path
