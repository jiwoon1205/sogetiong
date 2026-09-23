import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PublicProfile(Base):
    __tablename__ = "public_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(80), nullable=False)
    campus_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mbti: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    ideal_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    appearance_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="public_profile")


class PrivateProfile(Base):
    __tablename__ = "private_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    student_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    birth_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    student_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    university_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    campus_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_photo_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="private_profile")
