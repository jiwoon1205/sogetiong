import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def send_verification_code(email: str, code: str) -> None:
        settings = get_settings()
        if not settings.smtp_host:
            raise RuntimeError("email delivery is not configured")

        message = EmailMessage()
        message["Subject"] = "HUFS Match 학교 이메일 인증 코드"
        message["From"] = settings.smtp_from_email
        message["To"] = email
        message.set_content(
            f"HUFS Match 인증 코드: {code}\n"
            "이 코드는 10분 동안 유효하며, 다른 사람에게 공유하지 마세요."
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10, local_hostname="localhost") as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)