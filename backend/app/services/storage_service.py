import uuid
from pathlib import Path

from fastapi import UploadFile


class StorageService:
    STORAGE_ROOT = Path(__file__).resolve().parents[1] / "storage"
    PRIVATE_ROOT = STORAGE_ROOT / "private"
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

    @classmethod
    def ensure_storage(cls) -> None:
        cls.PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def save_uploaded_file(cls, upload_file: UploadFile, user_id: str) -> str:
        if not upload_file.filename:
            raise ValueError("filename is required")

        content_type = upload_file.content_type or ""
        if content_type not in cls.ALLOWED_MIME_TYPES:
            raise ValueError("unsupported image type")

        cls.ensure_storage()
        user_dir = cls.PRIVATE_ROOT / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(upload_file.filename).suffix.lower() or ".jpg"
        saved_name = f"{uuid.uuid4()}{suffix}"
        file_path = user_dir / saved_name

        contents = upload_file.file.read()
        file_path.write_bytes(contents)
        return file_path.relative_to(cls.STORAGE_ROOT).as_posix()
