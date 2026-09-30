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

# 파일 종류는 "내용"으로만 판단한다 (아래 3번). 확장자·MIME 타입은 휴대폰·PC마다 제각각이라 믿지 않는다.
#   예) 윈도우는 JPEG를 .jfif로 저장, 일부 안드로이드는 MIME을 image/jpg 또는 빈 값으로 보냄
# MPO = 휴대폰 카메라(삼성·아이폰 등)가 찍은 JPEG. 내용은 JPEG인데 사진 여러 장이 들어 있는 형식이라
#       Pillow가 "MPO"로 알려준다 → 예전에는 "지원하지 않는 형식"으로 거절됐다 (2026-09-30 수정)
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
JPEG_FAMILY = {"JPEG", "MPO"}
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

    # 1) 확장자·MIME 타입 검사는 하지 않는다 → 3)에서 파일 내용으로 확인한다.
    #    (이름만 .jpg인 가짜 파일은 어차피 3)에서 걸러지고, 진짜 사진인데 이름이 .jfif인 경우는 통과시킨다)

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
            raise PhotoValidationError("jpg, png, webp 사진만 올릴 수 있어요. (아이폰 HEIC 사진은 설정 > 카메라 > 포맷 > '높은 호환성'으로 찍거나 캡처해서 올려주세요)")

        # 4) 다시 열어서 크기 줄이기 → 회전 보정 → 메타데이터 없는 새 JPEG로 저장
        max_side = settings.photo_max_side
        with Image.open(BytesIO(raw)) as image:
            _check_pixels(image.size)
            if image.format in JPEG_FAMILY:
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
