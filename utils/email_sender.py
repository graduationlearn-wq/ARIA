"""
Email Sender — uses Python's built-in smtplib (no extra packages needed).

For SendGrid (recommended):
  SMTP_HOST=smtp.sendgrid.net
  SMTP_PORT=587
  SMTP_USER=apikey          ← literally the word "apikey"
  SMTP_PASSWORD=SG.xxxxx    ← your SendGrid API key

For Gmail (dev/testing):
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your@gmail.com
  SMTP_PASSWORD=xxxx xxxx xxxx xxxx   ← App Password (not your real password)
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

    # Use explicit from address if set (required for SendGrid), else fall back to smtp_user
    from_address = settings.email_from_address or settings.smtp_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{from_address}>"
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
            <a href="mailto:{from_address}?subject=Unsubscribe">Unsubscribe</a>
        </p>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            # Use from_address (not smtp_user) as envelope sender — critical for SendGrid
            # where smtp_user="apikey" but the verified sender is email_from_address.
            server.sendmail(from_address, to_address, msg.as_string())
        print(f"[Email] Sent to {to_address} — Subject: {subject}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send to {to_address}: {e}")
        return False
