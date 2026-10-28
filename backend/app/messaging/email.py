import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger(__name__)


def send_email(to: list[str], subject: str, body: str) -> bool:
    """Send a plain-text email via SMTP (e.g. Gmail with an app password)."""
    if not (settings.smtp_host and settings.smtp_user and to):
        log.warning("Email not sent (SMTP not configured or no recipients): %s", subject)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        log.exception("Failed to send email: %s", subject)
        return False
