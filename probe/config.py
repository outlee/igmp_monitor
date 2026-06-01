import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
if not INFLUXDB_TOKEN or INFLUXDB_TOKEN == "iptv-monitor-super-secret-token-2024":
    INFLUXDB_TOKEN = "CHANGE_ME__USE_STRONG_RANDOM_TOKEN"
    logger.warning("INFLUXDB_TOKEN is using an insecure default! Please set a strong token in .env")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iptv")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "metrics")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SQLITE_PATH = os.getenv("SQLITE_PATH", "/data/db/iptv.db")
THUMBNAIL_DIR = os.getenv("THUMBNAIL_DIR", "/data/thumbnails")
SIM_VIDEO_DIR = os.getenv("SIM_VIDEO_DIR", "/data/videos")

WORKER_COUNT = int(os.getenv("WORKER_COUNT", "10"))
CHANNELS_PER_WORKER = int(os.getenv("CHANNELS_PER_WORKER", "30"))

UDP_RECV_BUFFER = 4 * 1024 * 1024
UDP_TIMEOUT_SEC = 15.0

# ==================== 告警阈值调优区（误报主要来源）====================
# 黑屏：平均亮度低于此值（0-255，建议 8~20，根据实际画面调）
BLACK_LUMA_THRESHOLD = 16
# 需要连续多少个采样周期都满足黑屏条件才真正触发（减少单帧异常导致的误报）
BLACK_CONFIRM_SAMPLES = 2

# 冻屏：连续帧 MSE 低于此值持续超过 FREEZE_DURATION_SEC 触发
FREEZE_MSE_THRESHOLD = 0.5          # 非常敏感，调高可减少误报
FREEZE_DURATION_SEC = 10
FREEZE_CONFIRM_SAMPLES = 2

# 视频采样间隔（秒），太频繁会增加 CPU 和误报
# 建议值：5~10 秒。调大可显著降低 CPU，但告警响应会稍慢。
FRAME_SAMPLE_INTERVAL_SEC = 8

# 静音：RMS 低于此值持续 SILENCE_DURATION_SEC 秒
SILENCE_RMS_THRESHOLD = 0.001       # 极低，安静片段或低码率音频容易误报
SILENCE_DURATION_SEC = 5
SILENCE_CONFIRM_SAMPLES = 2

CLIP_THRESHOLD = 0.98
CLIP_RATIO_THRESHOLD = 0.01

# CC 错误每秒超过此值 → WARNING
CC_ERROR_THRESHOLD = 5

# PCR 抖动超过此值（毫秒）→ WARNING
PCR_JITTER_THRESHOLD_MS = 40.0

BITRATE_DEVIATION_THRESHOLD = 0.3

# 花屏（马赛克）检测
MOSAIC_CORRUPT_RATIO_THRESHOLD = 0.005   # 连续采样中损坏帧占比阈值（0.5%）
MOSAIC_LOW_VAR_THRESHOLD = 5.0     # 块方差低于此值视为大块马赛克
MOSAIC_HIGH_VAR_THRESHOLD = 2000.0  # 块方差高于此值视为噪点花屏
MOSAIC_BLOCK_SIZE = 16      # 块大小（像素）
MOSAIC_DURATION_SEC = 3.0    # 持续此秒数才触发告警
MOSAIC_CONFIRM_SAMPLES = 2

# 音频卡顿检测
STUTTER_PTS_RATIO = 2.0   # 实际间隔/期望间隔 超此倍数视为卡顿
STUTTER_RATE_THRESHOLD = 2     # 窗口内卡顿事件达此次数触发告警
STUTTER_WINDOW_SEC = 10.0  # 滑动窗口长度（秒）

INFLUX_BATCH_SIZE = 300
INFLUX_FLUSH_INTERVAL_MS = 1000

THUMBNAIL_WIDTH = 320
THUMBNAIL_HEIGHT = 180
THUMBNAIL_QUALITY = 75
