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

import os
import re
import html as _html
import smtplib
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings

# Uploaded attachment files are stored as "t{template_id}__{original_name}" —
# strip that prefix so the recipient sees the clean original filename.
_UPLOAD_PREFIX = re.compile(r"^t\d+__")


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


def send_email(to_address: str, subject: str, body: str,
               attachments: list[str] | None = None,
               from_email: str | None = None,
               from_name: str | None = None,
               reply_to: str | None = None,
               signature_html: str | None = None) -> bool:
    """
    Send a plain-text + HTML email, optionally with file attachments
    (list of paths on disk). Returns True on success, False on failure.

    from_email / from_name make the message appear to come from the logged-in
    team member (so leads see who's actually writing). reply_to routes replies
    back to that person. The SMTP envelope sender stays the authenticated account
    (SPF/auth stay valid) — only the visible From/Reply-To change.
    """
    if not settings.smtp_user or not settings.smtp_password:
        print("[Email] SMTP credentials not configured — skipping send.")
        print(f"[Email] Would have sent to: {to_address}")
        print(f"[Email] From: {from_email or settings.email_from_address or settings.smtp_user}")
        print(f"[Email] Subject: {subject}")
        if attachments:
            print(f"[Email] Attachments: {[os.path.basename(p) for p in attachments]}")
        print(f"[Email] Body:\n{body}")
        return False

    # Authenticated account — used as the SMTP envelope sender (required for
    # SendGrid where smtp_user="apikey" but the verified sender differs).
    auth_from = settings.email_from_address or settings.smtp_user
    # Visible sender: the logged-in team member if given, else the configured account.
    visible_from = (from_email or "").strip() or auth_from
    display_name = (from_name or "").strip() or settings.email_from_name
    reply_addr = (reply_to or from_email or "").strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{display_name} <{visible_from}>"
    msg["To"] = to_address
    if reply_addr:
        msg["Reply-To"] = reply_addr

    # Plain text version — markdown links become "text: url" so they stay usable
    msg.attach(MIMEText(_links_to_plain(body), "plain"))

    # HTML version — markdown links become hidden hyperlinks (raw URL not shown)
    html_body = _links_to_html(body)
    # The sender's uploaded signature image is appended as raw HTML (not escaped).
    sig_block = f"<br><br>{signature_html}" if signature_html else ""
    html = f"""
    <html><body style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #2c3e50;">
        {html_body}
        {sig_block}
        <br><br>
        <p style="font-size:11px;color:#aaa;">
            You're receiving this because you filled out a form expressing interest in BeyondSure.<br>
            <a href="mailto:{reply_addr or visible_from}?subject=Unsubscribe">Unsubscribe</a>
        </p>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))

    # With attachments: wrap text/html alternative inside a mixed container.
    if attachments:
        outer = MIMEMultipart("mixed")
        for header in ("Subject", "From", "To", "Reply-To"):
            if header in msg:
                outer[header] = msg[header]
                del msg[header]
        outer.attach(msg)
        for path in attachments:
            try:
                with open(path, "rb") as f:
                    part = MIMEApplication(f.read())
            except OSError as e:
                print(f"[Email] Skipping unreadable attachment {path}: {e}")
                continue
            clean_name = _UPLOAD_PREFIX.sub("", os.path.basename(path))
            part.add_header("Content-Disposition", "attachment", filename=clean_name)
            outer.attach(part)
        msg = outer

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            # Envelope sender stays the authenticated account (not the visible From) —
            # critical for SendGrid (smtp_user="apikey") and keeps SPF/auth aligned.
            server.sendmail(auth_from, to_address, msg.as_string())
        print(f"[Email] Sent to {to_address} — Subject: {subject}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send to {to_address}: {e}")
        return False
