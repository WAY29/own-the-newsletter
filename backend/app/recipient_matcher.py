from __future__ import annotations

from collections.abc import Iterable, Mapping
from email.message import Message
from email.utils import getaddresses

RECIPIENT_HEADERS = ("to", "cc", "delivered-to", "x-original-to")


def normalize_address(value: str) -> str:
    return value.strip().strip("<>").lower()


def extract_recipient_addresses(headers: Mapping[str, str | Iterable[str]]) -> set[str]:
    values: list[str] = []
    lowered = {key.lower(): value for key, value in headers.items()}
    for header in RECIPIENT_HEADERS:
        raw_value = lowered.get(header)
        if raw_value is None:
            continue
        if isinstance(raw_value, str):
            values.append(raw_value)
        else:
            values.extend(raw_value)

    addresses: set[str] = set()
    for display_name, address in getaddresses(values):
        candidate = address or display_name
        normalized = normalize_address(candidate)
        if normalized:
            addresses.add(normalized)
    return addresses


def message_recipient_headers(message: Message) -> dict[str, list[str]]:
    return {name: message.get_all(name, []) for name in RECIPIENT_HEADERS}


def matches_recipient(headers: Mapping[str, str | Iterable[str]], target_address: str) -> bool:
    return normalize_address(target_address) in extract_recipient_addresses(headers)

