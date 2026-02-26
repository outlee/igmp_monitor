import os
from dotenv import load_dotenv

load_dotenv()

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "iptv-monitor-super-secret-token-2024")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iptv")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "metrics")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SQLITE_PATH = os.getenv("SQLITE_PATH", "/data/db/iptv.db")
THUMBNAIL_DIR = os.getenv("THUMBNAIL_DIR", "/data/thumbnails")
