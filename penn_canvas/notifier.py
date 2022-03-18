from email.message import EmailMessage
from smtplib import SMTP_SSL

from .config import get_email_credentials


def send_email(command="", content=""):
    with SMTP_SSL("smtp.gmail.com", 465) as smtp:
        email_address, password = get_email_credentials()
        smtp.login(email_address, password)
        message = EmailMessage()
        message["Subject"] = f"Penn Canvas CLI ({command}) - ERROR notification"
        message["From"] = email_address
        message["To"] = email_address
        message.set_content(content)
        smtp.send_message(message)
