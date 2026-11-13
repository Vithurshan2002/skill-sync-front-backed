"""Worker image processing and transactional photo storage."""

import logging
import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.core.errors import invalid
from app.schemas import serializers as out

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
                # Apply camera orientation before resizing, then flatten transparency for JPEG.
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


def save_photo(db: Session, user: m.User, folder: Path, data: bytes) -> dict:
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
        # A database rollback cannot remove a file, so undo the new file separately.
        db.rollback()
        remove_file(folder, key)
        raise
    # Remove the old image only after the database points to the new one.
    remove_file(folder, old_key)
    return {"data": out.worker(worker, private=True)}


def delete_photo(db: Session, user: m.User, folder: Path) -> dict:
    worker = db.scalar(
        select(m.Worker)
        .where(m.Worker.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    old_key = worker.photo_key
    worker.photo_key = None
    db.commit()
    remove_file(folder, old_key)
    return {"data": out.worker(worker, private=True)}
