from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

from .body_processor import plain_text_to_html
from .recipient_matcher import message_recipient_headers
from .timeutil import iso_now, utc_now


@dataclass(frozen=True)
class ParsedEmail:
    subject: str
    author: str
    published_at: str
    message_id: str
    recipient_headers: dict[str, list[str]]
    raw_html: str


def parse_email(raw_bytes: bytes) -> ParsedEmail:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    subject = str(message.get("subject") or "").strip() or "Untitled"
    author = str(message.get("from") or "").strip()
    message_id = str(message.get("message-id") or "").strip()
    published_at = _published_at(message)
    raw_html = _extract_body_html(message)
    return ParsedEmail(
        subject=subject,
        author=author,
        published_at=published_at,
        message_id=message_id,
        recipient_headers=message_recipient_headers(message),
        raw_html=raw_html,
    )


def _published_at(message: EmailMessage) -> str:
    raw_date = message.get("date")
    if not raw_date:
        return iso_now()
    try:
        parsed = parsedate_to_datetime(str(raw_date))
    except (TypeError, ValueError, IndexError, OverflowError):
        return iso_now()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _extract_body_html(message: EmailMessage) -> str:
    html_part = _find_part(message, "text/html")
    if html_part is not None:
        return _decode_part(html_part)
    text_part = _find_part(message, "text/plain")
    if text_part is not None:
        return plain_text_to_html(_decode_part(text_part))
    if message.is_multipart():
        return ""
    content_type = message.get_content_type()
    if content_type == "text/html":
        return _decode_part(message)
    if content_type == "text/plain":
        return plain_text_to_html(_decode_part(message))
    return ""


def _find_part(message: EmailMessage, content_type: str) -> EmailMessage | None:
    if not message.is_multipart():
        return message if message.get_content_type() == content_type else None
    for part in message.walk():
        if part.is_multipart():
            continue
        disposition = (part.get_content_disposition() or "").lower()
        if disposition == "attachment":
            continue
        if part.get_content_type() == content_type:
            return part
    return None


def _decode_part(part: EmailMessage) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        content = part.get_content()
        return content if isinstance(content, str) else str(content)
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")

