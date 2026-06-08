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

import re
import html as _html
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings


# Markdown-style link:  [visible text](https://url)
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def _links_to_plain(body: str) -> str:
    """For the plain-text part: render [text](url) as 'text: url' (URL stays usable)."""
    return _MD_LINK.sub(lambda m: f"{m.group(1)}: {m.group(2)}", body)


def _links_to_html(body: str) -> str:
    """For the HTML part: render [text](url) as a styled <a>, hiding the raw URL."""
    links: list[tuple[str, str]] = []

    def _stash(m: re.Match) -> str:
        links.append((m.group(1), m.group(2)))
        return f"\x00L{len(links) - 1}\x00"

    tmp = _MD_LINK.sub(_stash, body)
    tmp = _html.escape(tmp).replace("\n", "<br>")
    for i, (text, url) in enumerate(links):
        anchor = (
            f'<a href="{_html.escape(url, quote=True)}" '
            f'style="color:#1e3a8a;font-weight:600;text-decoration:none;">'
            f'{_html.escape(text)}</a>'
        )
        tmp = tmp.replace(f"\x00L{i}\x00", anchor)
    return tmp


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

    # Plain text version — markdown links become "text: url" so they stay usable
    msg.attach(MIMEText(_links_to_plain(body), "plain"))

    # HTML version — markdown links become hidden hyperlinks (raw URL not shown)
    html_body = _links_to_html(body)
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
