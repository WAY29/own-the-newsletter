from __future__ import annotations

import html
import re
from dataclasses import dataclass

try:
    import nh3
except ImportError:  # pragma: no cover - dependency is installed in normal runtime
    nh3 = None

try:
    from inscriptis import get_text
except ImportError:  # pragma: no cover - dependency is installed in normal runtime
    get_text = None


@dataclass(frozen=True)
class ProcessedBody:
    raw_html: str
    sanitized_html: str
    summary: str


SUMMARY_CHARS = 280

ALLOWED_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "code",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "blockquote": {"cite"},
}

LAYOUT_TAG_RE = re.compile(
    r"</?(?:div|span|table|tbody|td|th|thead|tr)(?:\s[^>]*)?>",
    flags=re.IGNORECASE,
)
CLASS_ATTRIBUTE_RE = re.compile(r"\sclass=(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", flags=re.IGNORECASE)


class BodyProcessor:
    def process(self, raw_html: str, summary_chars: int = SUMMARY_CHARS) -> ProcessedBody:
        raw = raw_html or ""
        sanitized = self.sanitize(raw)
        text = self.to_text(sanitized or raw)
        summary = self.summarize(text, summary_chars)
        return ProcessedBody(raw_html=raw, sanitized_html=sanitized, summary=summary)

    def sanitize(self, raw_html: str) -> str:
        if nh3 is None:
            without_scripts = re.sub(r"<script.*?</script>", "", raw_html, flags=re.IGNORECASE | re.DOTALL)
            without_classes = CLASS_ATTRIBUTE_RE.sub("", without_scripts)
            return LAYOUT_TAG_RE.sub("", without_classes)
        return nh3.clean(
            raw_html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            url_schemes={"http", "https", "mailto"},
        )

    def to_text(self, html_value: str) -> str:
        if get_text is not None:
            return get_text(html_value)
        stripped = re.sub(r"<[^>]+>", " ", html_value)
        return html.unescape(stripped)

    def summarize(self, text: str, summary_chars: int = SUMMARY_CHARS) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= summary_chars:
            return normalized
        return normalized[: max(0, summary_chars - 3)].rstrip() + "..."


def plain_text_to_html(text: str) -> str:
    escaped = html.escape(text or "")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", escaped) if part.strip()]
    if not paragraphs:
        return ""
    return "\n".join(f"<p>{paragraph.replace(chr(10), '<br>')}</p>" for paragraph in paragraphs)
