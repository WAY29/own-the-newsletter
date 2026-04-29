from app.recipient_matcher import extract_recipient_addresses, matches_recipient


def test_matches_recipient_headers_case_insensitive_exact() -> None:
    headers = {
        "To": 'Newsletter <Daily+news@example.com>, "Other" <other@example.com>',
        "Cc": "copy@example.com",
        "Delivered-To": "DAILY+NEWS@example.com",
        "X-Original-To": "alias@example.com",
    }

    assert matches_recipient(headers, "daily+news@example.com")
    assert matches_recipient(headers, "ALIAS@example.com")
    assert not matches_recipient(headers, "daily@example.com")
    assert not matches_recipient(headers, "news@example.com")


def test_extract_recipient_addresses_ignores_non_recipient_headers() -> None:
    headers = {
        "From": "sender@example.com",
        "To": "target@example.com",
    }

    assert extract_recipient_addresses(headers) == {"target@example.com"}

