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
        settings = get_settings()

        if settings.email_backend == "console":
            if settings.environment == "prod":
                raise EmailDeliveryError("console email backend is not allowed in prod")
            # 개발용: 실제 메일 대신 서버 콘솔에 출력
            print(f"[DEV EMAIL] {email} 인증번호: {code}", flush=True)
            return

        if not settings.smtp_host:
            raise EmailDeliveryError("email delivery is not configured")

        message = EmailMessage()
        message["Subject"] = "학교 이메일 인증번호"
        message["From"] = settings.smtp_from_email
        message["To"] = email
        message.set_content(
            f"인증번호: {code}\n"
            f"이 번호는 {settings.verification_code_minutes}분 동안 유효합니다. 다른 사람에게 알려주지 마세요."
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password or "")
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            # 로그에 인증번호나 이메일 원문을 남기지 않는다
            logger.error("verification email delivery failed: %s", type(exc).__name__)
            raise EmailDeliveryError("email delivery failed") from exc
