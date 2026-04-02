import logging
from abc import ABC, abstractmethod
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


class EmailSender(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender(EmailSender):
    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info(
            "\n--- EMAIL ---\nTo: %s\nSubject: %s\nBody:\n%s\n--- END EMAIL ---",
            to,
            subject,
            body,
        )
        print(f"\n--- EMAIL ---\nTo: {to}\nSubject: {subject}\nBody:\n{body}\n--- END EMAIL ---")


class SmtpEmailSender(EmailSender):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr
        self.use_tls = use_tls

    async def send(self, to: str, subject: str, body: str) -> None:
        message = MIMEText(body, "html")
        message["From"] = self.from_addr
        message["To"] = to
        message["Subject"] = subject

        await aiosmtplib.send(
            message,
            hostname=self.host,
            port=self.port,
            username=self.user if self.user else None,
            password=self.password if self.password else None,
            start_tls=self.use_tls,
        )


def get_email_sender() -> EmailSender:
    if settings.EMAIL_BACKEND == "smtp" and settings.SMTP_HOST:
        return SmtpEmailSender(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            from_addr=settings.SMTP_FROM,
            use_tls=settings.SMTP_USE_TLS,
        )
    return ConsoleEmailSender()
