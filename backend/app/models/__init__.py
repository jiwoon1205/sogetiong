"""SQLAlchemy models package."""

from app.models.matching import (
    AdminRole,
    AdminUser,
    AppearanceEvaluation,
    AuditLog,
    Block,
    ExcludedDepartment,
    Interest,
    Like,
    Match,
    MatchingPreference,
    Message,
    Notification,
    PhotoReview,
    PreferredDepartment,
    Report,
    UserInterest,
    VerificationToken,
)
from app.models.profile import PrivateProfile, PublicProfile
from app.models.university import Campus, Department, University
from app.models.user import User
