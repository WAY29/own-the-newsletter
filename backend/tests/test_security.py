from app.security import redact_sensitive


def test_redact_sensitive_hides_github_tokens_and_random_feed_urls() -> None:
    text = (
        "token=ghp_secret-token "
        "backend=https://backend.example.test/f/abcdefghijklmnopqrstuvwxyz.xml "
        "raw=https://cdn.example.test/feeds/abcdefghijklmnopqrstuvwxyz.raw.xml"
    )

    redacted = redact_sensitive(text)

    assert "ghp_secret-token" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "***" in redacted
