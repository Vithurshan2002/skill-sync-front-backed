"""Bounded worker-photo uploads and public, versioned JPEG thumbnails."""

import logging
import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app import models as m
from app import schemas as s
from app.core.auth import CurrentUser, Db, own_worker
from app.core.errors import invalid, missing
from app.schemas import serializers as out

router = APIRouter(prefix="/api/v1", tags=["Worker photos"])
MAX_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 16_000_000
logger = logging.getLogger(__name__)


def thumbnail(data: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    invalid("photo", "Choose a JPG, PNG or WebP image.")
                if source.width * source.height > MAX_PIXELS or max(source.size) > 8192:
                    invalid(
                        "photo", "Choose an image up to 16 megapixels and 8192 pixels per side."
                    )
                if min(source.size) < 64:
                    invalid("photo", "Choose an image at least 64 pixels wide and high.")
                if getattr(source, "n_frames", 1) != 1:
                    invalid("photo", "Choose a still image, not an animation.")
                source.load()
                oriented = ImageOps.exif_transpose(source).convert("RGBA")
                fitted = ImageOps.contain(oriented, (512, 512), method=Image.Resampling.LANCZOS)
                clean = Image.new("RGB", fitted.size, "white")
                clean.paste(fitted, mask=fitted.getchannel("A"))
                result = BytesIO()
                clean.save(result, format="JPEG", quality=85, optimize=True)
                return result.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        invalid("photo", "This image cannot be read. Choose a valid JPG, PNG or WebP image.")


def remove_file(folder: Path, key: str | None) -> None:
    if key:
        try:
            (folder / f"{key}.jpg").unlink(missing_ok=True)
        except OSError:
            logger.warning("An obsolete worker photo could not be removed.")


def save_photo(db, user, folder: Path, data: bytes):
    encoded = thumbnail(data)
    worker = db.scalar(
        select(m.Worker)
        .where(m.Worker.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    old_key = worker.photo_key
    key = uuid4().hex
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with (folder / f"{key}.jpg").open("xb") as output:
            output.write(encoded)
        worker.photo_key = key
        db.commit()
    except Exception:
        db.rollback()
        remove_file(folder, key)
        raise
    remove_file(folder, old_key)
    return {"data": out.worker(worker, private=True)}


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
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            invalid("photo", "The photo must be 2 MB or smaller.")
        data.extend(chunk)
    return await run_in_threadpool(
        save_photo, db, user, request.app.state.settings.photo_storage_path, bytes(data)
    )


@router.delete("/worker/profile/photo", response_model=s.Envelope[s.WorkerView])
def delete_photo(request: Request, user: CurrentUser, db: Db):
    own_worker(db, user)
    worker = db.scalar(
        select(m.Worker)
        .where(m.Worker.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    old_key = worker.photo_key
    worker.photo_key = None
    db.commit()
    remove_file(request.app.state.settings.photo_storage_path, old_key)
    return {"data": out.worker(worker, private=True)}


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
