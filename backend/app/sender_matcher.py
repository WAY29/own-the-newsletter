from __future__ import annotations

from collections.abc import Iterable, Mapping
from email.message import Message

SOURCE_HEADERS = ("from", "sender", "send", "reply-to", "return-path")


def normalize_match_text(value: str) -> str:
    return value.strip().lower()


def extract_source_values(headers: Mapping[str, str | Iterable[str]]) -> list[str]:
    values: list[str] = []
    lowered = {key.lower(): value for key, value in headers.items()}
    for header in SOURCE_HEADERS:
        raw_value = lowered.get(header)
        if raw_value is None:
            continue
        if isinstance(raw_value, str):
            values.append(raw_value)
        else:
            values.extend(raw_value)

    return [normalized for value in values if (normalized := normalize_match_text(value))]


def message_source_headers(message: Message) -> dict[str, list[str]]:
    return {name: message.get_all(name, []) for name in SOURCE_HEADERS}


def matches_source(headers: Mapping[str, str | Iterable[str]], target_text: str) -> bool:
    target = normalize_match_text(target_text)
    return bool(target) and any(target in value for value in extract_source_values(headers))
