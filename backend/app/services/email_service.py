import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


class EmailService:
    @staticmethod
    def send_verification_code(email: str, code: str) -> None:
        minutes = get_settings().verification_code_minutes
        _send(
            email,
            "학교 이메일 인증번호",
            f"인증번호: {code}\n이 번호는 {minutes}분 동안 유효합니다. 다른 사람에게 알려주지 마세요.",
            dev_log=f"인증번호: {code}",
        )

    @staticmethod
    def send_already_registered_notice(email: str) -> None:
        """이미 가입된 주소로 가입 인증번호를 요청했을 때 보내는 안내 (인증번호 없음)."""
        _send(
            email,
            "이미 가입된 이메일입니다",
            "이 주소로 가입 인증번호 요청이 들어왔지만, 이미 가입된 계정이 있어서 인증번호는 보내지 않았습니다.\n\n"
            "- 로그인 화면에서 이 이메일로 로그인하세요.\n"
            "- 비밀번호가 기억나지 않으면 로그인 화면의 '비밀번호 찾기'로 재설정할 수 있습니다.\n\n"
            "본인이 요청하지 않았다면 이 메일을 무시하세요. 계정에는 아무 변화가 없습니다.",
            dev_log="이미 가입된 주소 안내 메일",
        )

    @staticmethod
    def send_password_reset_code(email: str, code: str) -> None:
        minutes = get_settings().verification_code_minutes
        _send(
            email,
            "비밀번호 재설정 인증번호",
            f"비밀번호 재설정 인증번호: {code}\n"
            f"이 번호는 {minutes}분 동안 유효합니다. 다른 사람에게 알려주지 마세요.\n\n"
            "본인이 요청하지 않았다면 이 메일을 무시하세요. 비밀번호는 바뀌지 않습니다.",
            dev_log=f"비밀번호 재설정 인증번호: {code}",
        )

    @staticmethod
    def send_password_changed_notice(email: str) -> None:
        _send(
            email,
            "비밀번호가 변경되었습니다",
            "계정의 비밀번호가 방금 변경되었고, 모든 기기에서 로그아웃되었습니다.\n\n"
            "본인이 변경하지 않았다면 즉시 비밀번호 재설정을 다시 진행하고 운영진에게 알려주세요.",
            dev_log="비밀번호 변경 안내 메일",
        )

    # ---------- 사진 검수 결과 (사용자에게) ----------

    @staticmethod
    def send_photo_approved(email: str) -> None:
        site = get_settings().site_url
        _send(
            email,
            "사진 검수가 끝났어요",
            "올려주신 사진의 검수가 끝나서 이제 추천을 받을 수 있어요.\n\n"
            f"지금 확인하기: {site}/discover\n\n"
            "사진 원본은 다른 학생에게 보이지 않아요.",
            dev_log="사진 승인 안내 메일",
        )

    @staticmethod
    def send_photo_rejected(email: str, reason: str) -> None:
        site = get_settings().site_url
        _send(
            email,
            "사진을 다시 올려주세요",
            f"올려주신 사진이 반려되었어요.\n\n사유: {reason}\n\n"
            f"새 사진 올리기: {site}/profile",
            dev_log="사진 반려 안내 메일",
        )

    # ---------- 운영진 알림 ----------

    @staticmethod
    def send_admin_photo_queue(email: str, pending_count: int) -> None:
        site = get_settings().site_url
        _send(
            email,
            f"[운영] 검수 대기 사진 {pending_count}장",
            f"검수를 기다리는 사진이 {pending_count}장 쌓였어요.\n\n"
            f"검수하러 가기: {site}/admin/photos\n\n"
            "(대기 사진이 10장 쌓일 때 한 번 보내요. 검수해서 줄어든 뒤 다시 10장이 되면 또 보내요.)",
            dev_log=f"관리자 사진 알림 ({pending_count}장)",
        )

    @staticmethod
    def send_admin_new_report(email: str, reason: str) -> None:
        site = get_settings().site_url
        label = REPORT_REASON_LABELS.get(reason, reason)
        _send(
            email,
            f"[운영] 새 신고: {label}",
            f"새 신고가 접수됐어요. 사유: {label}\n\n"
            f"확인하러 가기: {site}/admin/reports\n\n"
            "처리 목표: 24시간 이내",
            dev_log=f"관리자 신고 알림 ({reason})",
        )


REPORT_REASON_LABELS = {
    "SEXUAL_HARASSMENT": "성희롱",
    "ABUSIVE_LANGUAGE": "욕설",
    "THREAT": "협박",
    "STALKING": "스토킹",
    "OBSCENE_CONTENT": "음란물",
    "IMPERSONATION": "사칭",
    "MONEY_REQUEST": "금전 요구",
    "PERSONAL_INFO_REQUEST": "개인정보 요구",
    "SPAM": "스팸",
    "OTHER": "기타",
}


def _send(email: str, subject: str, body: str, *, dev_log: str) -> None:
    settings = get_settings()

    if settings.email_backend == "console":
        if settings.environment == "prod":
            raise EmailDeliveryError("console email backend is not allowed in prod")
        # 개발용: 실제 메일 대신 서버 콘솔에 출력
        print(f"[DEV EMAIL] {email} {dev_log}", flush=True)
        return

    if not settings.smtp_host:
        raise EmailDeliveryError("email delivery is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        # 로그에 인증번호나 이메일 원문을 남기지 않는다
        logger.error("email delivery failed (%s): %s", subject, type(exc).__name__)
        raise EmailDeliveryError("email delivery failed") from exc
