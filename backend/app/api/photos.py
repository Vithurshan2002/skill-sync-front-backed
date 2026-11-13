"""Bounded worker-photo uploads and public, versioned JPEG thumbnails."""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app import models as m
from app import schemas as s
from app.core.auth import CurrentUser, Db, own_worker
from app.core.errors import invalid, missing
from app.services import photo_service

router = APIRouter(prefix="/api/v1", tags=["Worker photos"])
MAX_BYTES = 2 * 1024 * 1024


@router.put("/worker/profile/photo", response_model=s.Envelope[s.WorkerView])
async def upload_photo(request: Request, user: CurrentUser, db: Db):
    """Send raw JPEG/PNG/WebP bytes with the matching Content-Type (maximum 2 MB)."""
    own_worker(db, user)
    if request.headers.get("content-type", "").split(";")[0] not in {
        "image/jpeg",
        "image/png",
        "image/webp",
    }:
        invalid("photo", "Choose a JPG, PNG or WebP image.")
    data = bytearray()
    # Enforce the size limit while reading, rather than buffering an unrestricted upload.
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            invalid("photo", "The photo must be 2 MB or smaller.")
        data.extend(chunk)
    # Image decoding and synchronous database writes must not block the async request loop.
    return await run_in_threadpool(
        photo_service.save_photo,
        db,
        user,
        request.app.state.settings.photo_storage_path,
        bytes(data),
    )


@router.delete("/worker/profile/photo", response_model=s.Envelope[s.WorkerView])
def delete_photo(request: Request, user: CurrentUser, db: Db):
    own_worker(db, user)
    return photo_service.delete_photo(db, user, request.app.state.settings.photo_storage_path)


@router.get("/worker-photos/{key}.jpg")
def photo(key: str, request: Request, db: Db):
    # Only server-generated filenames referenced by a current profile are served.
    if len(key) != 32 or any(char not in "0123456789abcdef" for char in key):
        missing()
    if db.scalar(select(m.Worker.id).where(m.Worker.photo_key == key)) is None:
        missing()
    path = request.app.state.settings.photo_storage_path / f"{key}.jpg"
    if not path.is_file():
        missing()
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-cache",
        },
    )
