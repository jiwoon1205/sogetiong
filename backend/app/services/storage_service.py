"""사진 검증·정리와 private storage 저장 (설계도 §6, §38).

업로드된 사진은 항상 새 JPEG로 다시 저장한다. 이 과정에서 EXIF·GPS 등
모든 메타데이터가 사라지고, 이미지로 위장한 악성 파일도 걸러진다.
"""

import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# 압축 폭탄 방지: 파일은 작아도 화소 수가 크면 풀 때 메모리를 많이 쓴다.
# 사진을 열자마자(픽셀을 풀기 전에) 가로×세로를 확인해서 이보다 크면 거절한다.
# (2,500만 화소 ≈ 6000×4000, 일반 휴대폰 사진은 1,200만~5,000만 화소 중 대부분 통과)
MAX_PIXELS = 25_000_000
# Pillow 자체 안전장치도 같은 기준으로 맞춘다 (이 값의 2배를 넘으면 Pillow가 직접 오류를 낸다)
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class PhotoValidationError(ValueError):
    pass


@dataclass
class ProcessedPhoto:
    data: bytes
    mime_type: str
    width: int
    height: int


def process_upload(upload: UploadFile) -> ProcessedPhoto:
    settings = get_settings()

    # 1) 확장자 + MIME 타입 (이것만으로는 믿지 않는다)
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise PhotoValidationError("jpg, png, webp 파일만 올릴 수 있습니다.")
    if (upload.content_type or "").lower() not in ALLOWED_MIME_TYPES:
        raise PhotoValidationError("jpg, png, webp 파일만 올릴 수 있습니다.")

    # 2) 크기 제한 (제한보다 1바이트 더 읽어서 초과 여부 판단)
    raw = upload.file.read(settings.photo_max_bytes + 1)
    if not raw:
        raise PhotoValidationError("빈 파일입니다.")
    if len(raw) > settings.photo_max_bytes:
        raise PhotoValidationError(f"사진은 {settings.photo_max_bytes // (1024 * 1024)}MB 이하만 올릴 수 있습니다.")

    # 3) 실제 이미지인지 내용으로 검사
    #    Image.open()은 파일 머리말(가로·세로·형식)만 읽고, 픽셀은 아직 풀지 않는다.
    #    그래서 여기서 화소 수를 먼저 확인하면 메모리를 거의 쓰지 않고 거절할 수 있다.
    try:
        with Image.open(BytesIO(raw)) as probe:
            fmt = probe.format
            _check_pixels(probe.size)
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise PhotoValidationError("지원하지 않는 이미지 형식입니다.")

        # 4) 다시 열어서 크기 줄이기 → 회전 보정 → 메타데이터 없는 새 JPEG로 저장
        max_side = settings.photo_max_side
        with Image.open(BytesIO(raw)) as image:
            _check_pixels(image.size)
            if image.format == "JPEG":
                # JPEG는 풀 때부터 1/2, 1/4, 1/8 크기로 작게 풀 수 있다 (메모리 대폭 절약).
                # 긴 변이 max_side 이상으로 남는 만큼만 줄이므로 화질 손해는 없다.
                w, h = image.size
                ratio = max_side / max(w, h)
                if ratio < 1:
                    image.draft("RGB", (max(1, int(w * ratio)), max(1, int(h * ratio))))
            # 회전 보정·축소를 제자리(in place)에서 해서 큰 사본이 여러 개 생기지 않게 한다.
            ImageOps.exif_transpose(image, in_place=True)
            if image.mode not in ("RGB", "L", "RGBA"):
                # 팔레트(P) 등은 먼저 바꿔야 축소 화질이 좋다
                image = image.convert("RGBA")
            image.thumbnail((max_side, max_side))
            if image.mode == "RGBA":
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            out = BytesIO()
            image.save(out, format="JPEG", quality=90)
            width, height = image.size
    except PhotoValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as exc:
        raise PhotoValidationError("올바른 이미지 파일이 아닙니다.") from exc

    return ProcessedPhoto(data=out.getvalue(), mime_type="image/jpeg", width=width, height=height)


def _check_pixels(size: tuple[int, int]) -> None:
    width, height = size
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise PhotoValidationError("사진 해상도가 너무 큽니다. 2,500만 화소 이하로 줄여서 올려 주세요.")


# ---------- 저장소 ----------

class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    """개발용 저장소. 운영에서는 R2/S3 private bucket 구현으로 교체한다 (설계도 §50)."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid storage key")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def get_storage() -> StorageBackend:
    settings = get_settings()
    return LocalStorage(settings.local_storage_dir)


def new_storage_key(user_id: uuid.UUID) -> str:
    """서버가 만든 파일명. 사용자가 올린 원래 파일명은 쓰지 않는다."""
    return f"photos/{user_id}/{uuid.uuid4()}.jpg"
