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
