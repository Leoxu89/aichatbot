"""Email-based approval gate.

Emails you the draft caption + selected photos with a unique token, then polls
your inbox (IMAP) for a reply containing "APPROVE <token>" or "REJECT <token>".
This works even when you're away from the computer.
"""

from __future__ import annotations

import email
import imaplib
import smtplib
import time
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from .config import Config
from .content_generator import GeneratedContent


@dataclass
class ApprovalRequest:
    token: str
    property_name: str
    photos: list[Path]
    content: GeneratedContent
    platforms: list[str]


def request_approval(cfg: Config, req: ApprovalRequest) -> bool:
    """Send the approval email and block until a reply arrives or it times out.

    Returns True if approved, False if rejected or timed out.
    """
    _send_email(cfg, req)
    print(f"[approval] Sent draft to {cfg.approval.get('recipient')}. Waiting for your reply...")
    return _poll_for_reply(cfg, req.token)


def _send_email(cfg: Config, req: ApprovalRequest) -> None:
    s = cfg.secrets
    recipient = cfg.approval.get("recipient")
    if not (s.smtp_host and s.smtp_username and recipient):
        raise RuntimeError("Email approval needs SMTP_* settings and approval.recipient configured.")

    msg = EmailMessage()
    msg["Subject"] = f"[Approve?] {req.property_name} — {', '.join(req.platforms)}  [{req.token}]"
    msg["From"] = s.smtp_username
    msg["To"] = recipient

    body = _email_body(req)
    msg.set_content(body)

    for photo in req.photos:
        try:
            data = photo.read_bytes()
        except OSError:
            continue
        import mimetypes

        ctype, _ = mimetypes.guess_type(photo.name)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=photo.name)

    with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
        server.starttls()
        server.login(s.smtp_username, s.smtp_password)
        server.send_message(msg)


def _email_body(req: ApprovalRequest) -> str:
    ig = req.content.caption_for("instagram")
    fb = req.content.caption_for("facebook")
    photos = "\n".join(f"  - {p.name}" for p in req.photos)
    return f"""A new social post is ready for your approval.

Property: {req.property_name}
Platforms: {', '.join(req.platforms)}
Photos:
{photos}

--- Instagram caption ---
{ig}

--- Facebook caption ---
{fb}

==============================
TO APPROVE: reply to this email with the word  APPROVE {req.token}
TO REJECT:  reply with the word                REJECT {req.token}
==============================
"""


def _poll_for_reply(cfg: Config, token: str) -> bool:
    s = cfg.secrets
    if not (s.imap_host and s.imap_username):
        raise RuntimeError("Email approval needs IMAP_* settings to read your reply.")

    timeout = int(cfg.approval.get("timeout_minutes", 720)) * 60
    interval = int(cfg.approval.get("poll_interval_seconds", 60))
    deadline = time.time() + timeout
    approve_marker = f"APPROVE {token}".lower()
    reject_marker = f"REJECT {token}".lower()

    while time.time() < deadline:
        decision = _check_inbox(s, approve_marker, reject_marker)
        if decision is not None:
            return decision
        time.sleep(interval)

    print("[approval] Timed out waiting for a reply; not posting.")
    return False


def _check_inbox(secrets, approve_marker: str, reject_marker: str) -> bool | None:
    """Scan unread messages for the approval/rejection marker. None = undecided."""
    try:
        conn = imaplib.IMAP4_SSL(secrets.imap_host, secrets.imap_port)
        conn.login(secrets.imap_username, secrets.imap_password)
        conn.select("INBOX")
        _, ids = conn.search(None, "UNSEEN")
        for msg_id in ids[0].split():
            _, data = conn.fetch(msg_id, "(RFC822)")
            raw = data[0][1]
            text = _extract_text(email.message_from_bytes(raw)).lower()
            if approve_marker in text:
                conn.logout()
                return True
            if reject_marker in text:
                conn.logout()
                return False
        conn.logout()
    except Exception as exc:  # noqa: BLE001 - transient mail errors shouldn't crash the run
        print(f"[approval] inbox check failed (will retry): {exc}")
    return None


def _extract_text(message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="replace")
        return ""
    payload = message.get_payload(decode=True)
    return payload.decode(errors="replace") if payload else ""


def new_token() -> str:
    return uuid.uuid4().hex[:8]
