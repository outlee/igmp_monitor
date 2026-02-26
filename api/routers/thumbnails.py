import os
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import THUMBNAIL_DIR

router = APIRouter(prefix="/api/v1/thumbnails", tags=["thumbnails"])


@router.get("/{channel_id}/latest")
async def get_latest_thumbnail(channel_id: str):
    path = os.path.join(THUMBNAIL_DIR, f"latest_{channel_id}.jpg")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=5"})


@router.get("/{channel_id}/alarms", response_model=List[str])
async def list_alarm_thumbnails(channel_id: str):
    prefix = f"alarm_{channel_id}_"
    files = []
    try:
        for fname in sorted(os.listdir(THUMBNAIL_DIR)):
            if fname.startswith(prefix) and fname.endswith(".jpg"):
                files.append(f"/api/v1/thumbnails/{channel_id}/alarm/{fname}")
    except OSError:
        pass
    return files


@router.get("/{channel_id}/alarm/{filename}")
async def get_alarm_thumbnail(channel_id: str, filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(THUMBNAIL_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")
