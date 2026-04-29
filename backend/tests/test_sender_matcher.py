from app.sender_matcher import extract_source_values, matches_source


def test_matches_source_headers_case_insensitive_contains() -> None:
    headers = {
        "From": "Daily Digest <NEWSLETTER@Example.com>",
        "Sender": "bounce@example.com",
        "Reply-To": "Replies <reply@example.com>",
        "Return-Path": "<return@example.com>",
    }

    assert matches_source(headers, "newsletter@example.com")
    assert matches_source(headers, "daily digest")
    assert matches_source(headers, "BOUNCE@example.com")
    assert matches_source(headers, "return@example.com")
    assert not matches_source(headers, "other@example.com")


def test_extract_source_values_ignores_recipient_headers() -> None:
    headers = {
        "From": "Sender <sender@example.com>",
        "To": "target@example.com",
    }

    assert extract_source_values(headers) == ["sender <sender@example.com>"]
