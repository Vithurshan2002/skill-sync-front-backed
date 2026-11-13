from io import BytesIO

import pytest
from PIL import Image

from app.models import Worker
from app.photos import thumbnail
from tests.helpers import account, worker


def image_bytes(fmt="PNG", size=(120, 80)):
    output = BytesIO()
    Image.new("RGB", size, "navy").save(output, format=fmt)
    return output.getvalue()


def upload(api, headers, body=None, mime="image/png"):
    return api.put(
        "/api/v1/worker/profile/photo",
        headers={**headers, "Content-Type": mime},
        content=body if body is not None else image_bytes(),
    )


@pytest.mark.parametrize("size", [(120, 240), (240, 120), (120, 120)])
def test_thumbnail_preserves_top_and_bottom_of_entire_photo(size):
    source = Image.new("RGB", size, "blue")
    source.paste("red", (0, 0, size[0], size[1] // 4))
    source.paste("green", (0, 3 * size[1] // 4, size[0], size[1]))
    body = BytesIO()
    source.save(body, format="PNG")
    with Image.open(BytesIO(thumbnail(body.getvalue()))) as result:
        assert max(result.size) == 512
        assert abs(result.width / result.height - size[0] / size[1]) < 0.01
        red = result.getpixel((result.width // 2, result.height // 8))
        green = result.getpixel((result.width // 2, 7 * result.height // 8))
        assert red[0] > 200 and red[1] < 30 and red[2] < 30
        assert green[1] > 100 and green[0] < 30 and green[2] < 30
        assert result.getpixel((result.width // 2, 0))[0] > 200


@pytest.mark.parametrize(
    "fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_photo_upload_replacement_removal_and_public_thumbnail(api, fmt, mime):
    headers, professional, _ = worker(api)
    first = upload(api, headers, image_bytes(fmt), mime)
    assert first.status_code == 200, first.text
    photo_url = first.json()["data"]["photoUrl"]
    assert first.json()["data"]["approvalStatus"] == "approved"
    public = api.get(f"/api/v1/workers/{professional['id']}").json()["data"]
    assert public["photoUrl"] == photo_url
    thumbnail = api.get(photo_url)
    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"] == "image/jpeg"
    assert thumbnail.headers["x-content-type-options"] == "nosniff"
    with Image.open(BytesIO(thumbnail.content)) as image:
        assert image.size == (512, 341)
        assert not image.getexif()
    second_url = upload(api, headers).json()["data"]["photoUrl"]
    assert second_url != photo_url
    assert api.get(photo_url).status_code == 404
    assert len(list(api.app.state.settings.photo_storage_path.glob("*.jpg"))) == 1
    assert (
        api.delete("/api/v1/worker/profile/photo", headers=headers).json()["data"]["photoUrl"]
        is None
    )
    assert api.get(second_url).status_code == 404
    assert list(api.app.state.settings.photo_storage_path.glob("*.jpg")) == []
    assert api.delete("/api/v1/worker/profile/photo", headers=headers).status_code == 200


def test_photo_writes_require_worker_and_only_affect_own_profile(api):
    headers, first, _ = worker(api)
    other_headers, second, _ = worker(api)
    assert upload(api, {}).status_code == 401
    for role in ["customer", "admin"]:
        forbidden, _ = account(api, role)
        assert upload(api, forbidden).status_code == 403
        assert api.delete("/api/v1/worker/profile/photo", headers=forbidden).status_code == 403
    url = upload(api, headers).json()["data"]["photoUrl"]
    assert api.delete("/api/v1/worker/profile/photo", headers=other_headers).status_code == 200
    assert api.get(url).status_code == 200
    with api.app.state.sessions() as db:
        assert db.get(Worker, first["id"]).photo_key
        assert db.get(Worker, second["id"]).photo_key is None


def test_invalid_photos_do_not_replace_existing_photo(api):
    headers, _, _ = worker(api)
    url = upload(api, headers).json()["data"]["photoUrl"]
    for body, mime in [
        (b"not an image", "image/png"),
        (b"<svg></svg>", "image/svg+xml"),
        (b"x" * (2 * 1024 * 1024 + 1), "image/jpeg"),
        (image_bytes(size=(32, 32)), "image/png"),
        (image_bytes(size=(5000, 4000)), "image/png"),
    ]:
        result = upload(api, headers, body, mime)
        assert result.status_code == 422, result.text
        assert "photo" in result.json()["error"]["fields"]
        assert api.get("/api/v1/worker/profile", headers=headers).json()["data"]["photoUrl"] == url
    assert len(list(api.app.state.settings.photo_storage_path.glob("*.jpg"))) == 1
    assert api.get("/api/v1/worker-photos/not-a-valid-key.jpg").status_code == 404


def test_photo_storage_failure_preserves_old_image(api, monkeypatch):
    headers, professional, _ = worker(api)
    url = upload(api, headers).json()["data"]["photoUrl"]
    from pathlib import Path

    original = Path.open

    def fail_write(path, mode="r", *args, **kwargs):
        if mode == "xb":
            raise OSError("Disk unavailable")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_write)
    with pytest.raises(OSError):
        upload(api, headers)
    assert api.get("/api/v1/worker/profile", headers=headers).json()["data"]["photoUrl"] == url
    assert api.get(url).status_code == 200
