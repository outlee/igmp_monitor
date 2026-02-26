import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db.influx import close_influx
from db.redis_client import close_redis
from db.sqlite import close_db
from routers import alerts, channels, simulator, thumbnails
from websocket.manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ws_manager.start()
    logger.info("WebSocket manager started")
    yield
    await ws_manager.stop()
    await close_redis()
    await close_influx()
    await close_db()
    logger.info("API server shutdown")


app = FastAPI(
    title="IPTV Monitor API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(channels.router)
app.include_router(alerts.router)
app.include_router(thumbnails.router)
app.include_router(simulator.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/realtime")
async def ws_realtime(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
