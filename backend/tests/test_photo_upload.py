"""사진 업로드 안전장치 (메모리 폭탄 방지).

파일 크기는 작아도(수백 KB) 가로×세로가 아주 큰 사진은, 풀어서 처리하는 순간
메모리를 1GB 넘게 쓸 수 있다. 작은 서버(e2-micro, 1GB)는 이런 사진 한 장에 멈출 수 있다.
"""

import os
import subprocess
import sys
import textwrap
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from PIL import Image

from app.services.storage_service import MAX_PIXELS, PhotoValidationError, process_upload
from tests.conftest import signup

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _image_bytes(size, fmt="JPEG", mode="RGB", **save_kw) -> bytes:
    out = BytesIO()
    Image.new(mode, size, (200, 180, 160) if mode == "RGB" else 0).save(out, format=fmt, **save_kw)
    return out.getvalue()


def _upload(data: bytes, name="me.jpg", mime="image/jpeg") -> UploadFile:
    return UploadFile(file=BytesIO(data), filename=name, headers={"content-type": mime})


def test_huge_resolution_is_rejected_before_decoding():
    # 8000×5000 = 4,000만 화소. 단색이라 파일은 작지만 풀면 메모리를 많이 쓴다.
    data = _image_bytes((8000, 5000), quality=30)
    assert len(data) < 5 * 1024 * 1024
    with pytest.raises(PhotoValidationError, match="해상도"):
        process_upload(_upload(data))


def test_huge_png_is_rejected():
    data = _image_bytes((100, MAX_PIXELS // 100 + 1), fmt="PNG", mode="L")
    with pytest.raises(PhotoValidationError, match="해상도"):
        process_upload(_upload(data, "a.png", "image/png"))


def test_normal_phone_photo_is_shrunk_and_rotated():
    # 4000×1000 사진 + "90도 돌려서 보세요"(EXIF Orientation=6) → 세로 사진으로 저장돼야 한다
    image = Image.new("RGB", (4000, 1000), (10, 20, 30))
    exif = image.getexif()
    exif[0x0112] = 6
    out = BytesIO()
    image.save(out, format="JPEG", exif=exif)
    result = process_upload(_upload(out.getvalue()))
    assert (result.width, result.height) == (512, 2048)
    saved = Image.open(BytesIO(result.data))
    assert saved.format == "JPEG" and saved.size == (512, 2048)
    assert not saved.getexif()  # 메타데이터는 모두 제거


@pytest.mark.parametrize(
    "mode,fmt,name,mime",
    [("P", "PNG", "a.png", "image/png"), ("LA", "PNG", "a.png", "image/png"), ("RGBA", "WEBP", "a.webp", "image/webp"), ("CMYK", "JPEG", "a.jpg", "image/jpeg")],
)
def test_other_color_modes_still_work(mode, fmt, name, mime):
    result = process_upload(_upload(_image_bytes((3000, 2000), fmt=fmt, mode=mode), name, mime))
    assert (result.width, result.height) == (2048, 1365)


def test_api_returns_400_for_huge_resolution(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    r = a.post("/api/v1/me/photos", files={"file": ("big.jpg", _image_bytes((8000, 5000), quality=30), "image/jpeg")})
    assert r.status_code == 400
    assert "해상도" in r.json()["detail"]


@pytest.mark.skipif(sys.platform == "win32", reason="메모리 측정(resource 모듈)은 리눅스·맥에서만")
def test_large_photo_uses_little_memory(tmp_path):
    """6000×4000(2,400만 화소, 허용 범위) 사진을 처리해도 메모리가 크게 늘지 않아야 한다."""
    photo = tmp_path / "big.jpg"
    photo.write_bytes(_image_bytes((6000, 4000), quality=50))
    script = textwrap.dedent(
        f"""
        import resource, sys
        from io import BytesIO
        from fastapi import UploadFile
        from app.services.storage_service import process_upload
        before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        data = open({str(photo)!r}, "rb").read()
        process_upload(UploadFile(file=BytesIO(data), filename="a.jpg", headers={{"content-type": "image/jpeg"}}))
        after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        scale = 1 if sys.platform == "darwin" else 1024  # 맥은 바이트, 리눅스는 KB 단위
        print((after - before) * scale // (1024 * 1024))
        """
    )
    env = {**os.environ, "PYTHONPATH": str(BACKEND_DIR)}
    used_mb = int(subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True).stdout.strip())
    # 예전 방식은 이 사진에 약 280MB를 썼다. 작게 풀기(draft) 덕분에 100MB 아래로 떨어져야 한다.
    assert used_mb < 100, used_mb


# ---------- 2026-09-30: JPEG 업로드 오류 · 여러 장 제출 ----------

def _mpo_bytes() -> bytes:
    """휴대폰 카메라가 찍은 JPEG(MPO: 사진 안에 작은 사진이 하나 더 들어 있음)."""
    out = BytesIO()
    Image.new("RGB", (400, 300), (120, 90, 60)).save(
        out, format="MPO", save_all=True, append_images=[Image.new("RGB", (160, 120), (1, 2, 3))]
    )
    return out.getvalue()


@pytest.mark.parametrize(
    "name,mime",
    [("photo.jpg", "image/jpeg"), ("photo.jfif", "image/jpeg"), ("photo.jpeg", "image/jpg"), ("photo", ""), ("IMG.JPG", "application/octet-stream")],
)
def test_jpeg_is_accepted_whatever_the_name_or_mime(name, mime):
    """이름·MIME이 제각각이어도 내용이 JPEG면 받는다 (윈도우 .jfif, 안드로이드 image/jpg 등)."""
    result = process_upload(_upload(_image_bytes((300, 200)), name, mime))
    assert result.mime_type == "image/jpeg"


def test_phone_camera_mpo_jpeg_is_accepted():
    data = _mpo_bytes()
    assert Image.open(BytesIO(data)).format == "MPO"  # 예전에는 이 형식이라 거절됐다
    result = process_upload(_upload(data))
    assert (result.width, result.height) == (400, 300)
    assert Image.open(BytesIO(result.data)).format == "JPEG"


def test_fake_image_is_still_rejected():
    with pytest.raises(PhotoValidationError):
        process_upload(_upload(b"<html>not an image</html>", "evil.jpg", "image/jpeg"))


def test_gif_is_rejected():
    out = BytesIO()
    Image.new("P", (10, 10)).save(out, format="GIF")
    with pytest.raises(PhotoValidationError, match="jpg, png, webp"):
        process_upload(_upload(out.getvalue(), "a.gif", "image/gif"))


def test_upload_up_to_three_photos_as_one_submission(sent_codes, db):
    from tests.conftest import admin_login, approve

    a = signup(sent_codes, db, "a@hufs.ac.kr")
    files = [("files", (f"{i}.jpg", _image_bytes((300, 400)), "image/jpeg")) for i in range(3)]
    r = a.post("/api/v1/me/photos", files=files)
    assert r.status_code == 201, r.text
    assert r.json()["photo_count"] == 3
    mine = a.get("/api/v1/me/photos").json()
    assert len(mine["photos"]) == 1 and mine["photos"][0]["photo_count"] == 3

    admin = admin_login(db)
    queue = admin.get("/api/v1/admin/photo-reviews").json()["photos"]
    assert len(queue) == 1 and queue[0]["photo_count"] == 3  # 대기열에는 묶음 하나
    detail = admin.get(f"/api/v1/admin/photo-reviews/{queue[0]['photo_id']}").json()
    assert len(detail["image_urls"]) == 3
    for url in detail["image_urls"]:
        assert admin.get(url).status_code == 200
    approve(admin, queue[0]["photo_id"])
    assert admin.get("/api/v1/admin/photo-reviews").json()["photos"] == []
    assert a.get("/api/v1/me/photos").json()["photos"][0]["review_status"] == "APPROVED"


def test_more_than_three_photos_is_rejected(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    files = [("files", (f"{i}.jpg", _image_bytes((50, 50)), "image/jpeg")) for i in range(4)]
    r = a.post("/api/v1/me/photos", files=files)
    assert r.status_code == 400
    assert "3장" in r.json()["detail"]


def test_one_bad_photo_saves_nothing(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    files = [("files", ("ok.jpg", _image_bytes((50, 50)), "image/jpeg")), ("files", ("bad.jpg", b"nope", "image/jpeg"))]
    r = a.post("/api/v1/me/photos", files=files)
    assert r.status_code == 400
    assert "2번째 사진" in r.json()["detail"]
    assert a.get("/api/v1/me/photos").json()["photos"] == []
