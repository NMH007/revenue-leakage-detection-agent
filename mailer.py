"""
Send HTML email through Gmail's SMTP server using an App Password.

Gmail SMTP is free. We use SMTP over SSL (port 465). The App Password (NOT your
normal Google password) goes in .env as GMAIL_APP_PASSWORD. smtplib and email
are both part of Python's standard library -- nothing to install.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_html_email(subject, html, recipient=None):
    sender = config.GMAIL_ADDRESS
    # Google shows the app password in groups of 4 with spaces; strip them.
    password = (config.GMAIL_APP_PASSWORD or "").replace(" ", "")
    recipient = recipient or config.ALERT_RECIPIENT

    if not (sender and password and recipient):
        raise RuntimeError(
            "Gmail settings missing in .env "
            "(need GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ALERT_RECIPIENT)."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    # timeout is critical: some hosts (e.g. Hugging Face) block outbound SMTP,
    # and without a timeout the connect() hangs until the web worker is killed.
    # With a timeout it fails fast and raises a normal exception we can catch.
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=15) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Email sent to {recipient}")


if __name__ == "__main__":
    # Quick standalone test of just the email path.
    send_html_email(
        "Test from Revenue Leakage Agent",
        "<h2>It works!</h2><p>Your Gmail SMTP setup is correct.</p>",
    )
