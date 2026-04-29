from __future__ import annotations

import logging

from .security import redact_sensitive

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.strip().upper(), logging.INFO)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger().setLevel(level)


def safe_log_text(value: object, *, max_length: int = 160) -> str:
    text = redact_sensitive(str(value)).replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}..."
