import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile


class StorageService:
    STORAGE_ROOT = Path(__file__).resolve().parents[1] / "storage"
    PRIVATE_ROOT = STORAGE_ROOT / "private"
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

    @classmethod
    def ensure_storage(cls) -> None:
        cls.PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def save_uploaded_file(cls, upload_file: UploadFile, user_id: str) -> str:
        if not upload_file.filename:
            raise ValueError("filename is required")

        content_type = (upload_file.content_type or "").lower()
        if content_type not in cls.ALLOWED_MIME_TYPES:
            raise ValueError("unsupported image type")

        suffix = Path(upload_file.filename).suffix.lower()
        if suffix not in cls.ALLOWED_EXTENSIONS:
            raise ValueError("unsupported file extension")

        upload_file.file.seek(0)
        contents = upload_file.file.read()
        if len(contents) == 0:
            raise ValueError("empty file")
        if len(contents) > cls.MAX_FILE_SIZE_BYTES:
            raise ValueError("file too large")

        try:
            image = Image.open(BytesIO(contents))
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError("invalid image file") from exc

        upload_file.file.seek(0)
        cleaned = BytesIO()
        with Image.open(BytesIO(contents)) as image:
            image.load()
            if image.format in {"JPEG", "PNG", "WEBP"}:
                if image.info.get("exif"):
                    image = image.copy()
                    image.info.pop("exif", None)
                image.save(cleaned, format=image.format)
            else:
                raise ValueError("unsupported image format")

        cls.ensure_storage()
        user_dir = cls.PRIVATE_ROOT / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        saved_name = f"{uuid.uuid4()}{suffix}"
        file_path = user_dir / saved_name
        file_path.write_bytes(cleaned.getvalue())
        return file_path.relative_to(cls.STORAGE_ROOT).as_posix()
