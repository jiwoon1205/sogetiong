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
Image.MAX_IMAGE_PIXELS = 40_000_000  # 압축 폭탄 방지


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
    try:
        with Image.open(BytesIO(raw)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise PhotoValidationError("지원하지 않는 이미지 형식입니다.")

        # 4) 다시 열어서 회전 보정 → 크기 조정 → 메타데이터 없는 새 JPEG로 저장
        with Image.open(BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((settings.photo_max_side, settings.photo_max_side))
            out = BytesIO()
            image.save(out, format="JPEG", quality=90)
            width, height = image.size
    except PhotoValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as exc:
        raise PhotoValidationError("올바른 이미지 파일이 아닙니다.") from exc

    return ProcessedPhoto(data=out.getvalue(), mime_type="image/jpeg", width=width, height=height)


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
