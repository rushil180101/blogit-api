from email.message import EmailMessage

import aiosmtplib

from config import settings


async def send_email(
    to: str,
    subject: str,
    plain_text: str,
) -> None:
    email_message = EmailMessage()
    email_message["From"] = settings.mail_from
    email_message["To"] = to
    email_message["Subject"] = subject
    email_message.set_content(plain_text)

    await aiosmtplib.send(
        email_message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username,
        password=settings.mail_password.get_secret_value(),
        start_tls=settings.mail_use_tls,
    )


async def send_password_reset_email(to: str, username: str, token: str) -> None:
    password_reset_url = f"{settings.reset_password_base_url}/api/users/reset-password"
    exp_time = settings.reset_token_expiration_in_minutes
    plain_text = (
        f"Hi {username}, to reset your password, make an api call as follows.\n"
        f"API url (POST call): {password_reset_url}\n"
        f'Data: {{"token": "{token}", "new_password": "<new-password>"}}\n'
        f"This token will expire in {exp_time} minutes."
    )
    await send_email(
        to=to,
        subject="Password reset",
        plain_text=plain_text,
    )
