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
