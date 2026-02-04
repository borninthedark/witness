import smtplib
import ssl
from email.message import EmailMessage

from fitness.config import settings


class Mailer:
    def __init__(self):
        self.enabled = settings.email_enabled
        self.host = settings.email_smtp_host
        self.port = settings.email_smtp_port
        self.user = settings.email_smtp_username
        self.passwd = settings.email_smtp_password
        self.use_ssl = settings.email_smtp_ssl
        self.use_starttls = settings.email_smtp_starttls

    def send(
        self,
        subject: str,
        body_text: str,
        from_addr: str | None = None,
        to_addr: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        if not self.enabled:
            return  # no-op in CI/dev if disabled

        msg = EmailMessage()
        from_addr = from_addr or settings.email_from_addr
        to_addr = to_addr or settings.email_to_addr
        msg["From"] = f"{settings.email_from_name} <{from_addr}>"
        msg["To"] = to_addr
        if reply_to:
            msg["Reply-To"] = reply_to
        msg["Subject"] = subject
        msg.set_content(body_text)

        if self.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.host, self.port, context=context) as smtp:
                if self.user:
                    smtp.login(self.user, self.passwd)
                smtp.send_message(msg)
            return

        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.use_starttls:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
            if self.user:
                smtp.login(self.user, self.passwd)
            smtp.send_message(msg)


mailer = Mailer()
