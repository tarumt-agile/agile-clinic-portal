from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from agile_ci_demo.core.config import settings


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


# In-memory outbox recording every email the app has sent. Always populated (used by
# tests and as a fallback view when no SMTP server is configured).
_outbox: list[SentEmail] = []


def send_email(to: str, subject: str, body: str) -> SentEmail:
    """Record an email and deliver it via SMTP if credentials are configured."""
    email = SentEmail(to=to, subject=subject, body=body)
    _outbox.append(email)

    if settings.smtp_host and settings.smtp_username and settings.smtp_password:
        _send_via_smtp(
            email,
            host=settings.smtp_host,
            username=settings.smtp_username,
            password=settings.smtp_password,
        )

    return email


def _send_via_smtp(email: SentEmail, *, host: str, username: str, password: str) -> None:
    message = EmailMessage()
    message["Subject"] = email.subject
    message["From"] = settings.smtp_from or username
    message["To"] = email.to
    message.set_content(email.body)

    with smtplib.SMTP(host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(username, password)
        server.send_message(message)


def get_outbox() -> list[SentEmail]:
    return list(_outbox)


def clear_outbox() -> None:
    _outbox.clear()
