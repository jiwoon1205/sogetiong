import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._common import created_at, pk, updated_at


class University(Base):
    __tablename__ = "universities"

    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email_domain: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)  # 예: hufs.ac.kr
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    campuses = relationship("Campus", back_populates="university")


class Campus(Base):
    __tablename__ = "campuses"
    __table_args__ = (UniqueConstraint("university_id", "name", name="uq_campus_name"),)

    id: Mapped[uuid.UUID] = pk()
    university_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("universities.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    university = relationship("University", back_populates="campuses")
    departments = relationship("Department", back_populates="campus")


class Department(Base):
    """학과는 캠퍼스마다 다를 수 있으므로 캠퍼스에 속한다 (설계도 §11)."""

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("campus_id", "name", name="uq_department_name"),)

    id: Mapped[uuid.UUID] = pk()
    campus_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("campuses.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    campus = relationship("Campus", back_populates="departments")
