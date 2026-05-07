"""
Email Sender — uses Python's built-in smtplib (no extra packages needed).

For Gmail:
  1. Go to myaccount.google.com → Security → 2-Step Verification → App Passwords
  2. Generate a password for "Mail"
  3. Put that password in SMTP_PASSWORD in your .env file
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings


def send_email(to_address: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email. Returns True on success, False on failure.
    """
    if not settings.smtp_user or not settings.smtp_password:
        print("[Email] SMTP credentials not configured — skipping send.")
        print(f"[Email] Would have sent to: {to_address}")
        print(f"[Email] Subject: {subject}")
        print(f"[Email] Body:\n{body}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.smtp_user}>"
    msg["To"] = to_address

    # Plain text version
    msg.attach(MIMEText(body, "plain"))

    # Simple HTML version (same content, slightly formatted)
    html_body = body.replace("\n", "<br>")
    html = f"""
    <html><body style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #2c3e50;">
        {html_body}
        <br><br>
        <p style="font-size:11px;color:#aaa;">
            You're receiving this because you filled out a form expressing interest in BeyondSure.<br>
            <a href="mailto:{settings.smtp_user}?subject=Unsubscribe">Unsubscribe</a>
        </p>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_address, msg.as_string())
        print(f"[Email] Sent to {to_address} — Subject: {subject}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send to {to_address}: {e}")
        return False
