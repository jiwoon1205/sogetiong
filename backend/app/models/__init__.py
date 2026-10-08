"""SQLAlchemy 모델 모음. Alembic이 모든 테이블을 알 수 있도록 여기서 한 번에 import 한다."""

from app.models.admin import ROLE_PERMISSIONS, AdminRole, AdminSession, AdminUser, AuditLog
from app.models.matching import (
    REPORT_REASONS,
    Block,
    ExcludedDepartment,
    Like,
    Match,
    MatchingPreference,
    MatchRead,
    Message,
    Notification,
    PreferredCampus,
    PreferredDepartment,
    Report,
)
from app.models.payment import Payment
from app.models.photo import AppearanceEvaluation, UserPhoto
from app.models.push import PushSubscription
from app.models.profile import Interest, PrivateProfile, PublicProfile, UserInterest
from app.models.university import Campus, Department, University
from app.models.user import User, UserDailyVisit, UserSession, VerificationToken
from app.models.survey import AppSetting, SurveyResponse
