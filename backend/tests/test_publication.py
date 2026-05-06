from app.publication import (
    PublicationTarget,
    build_feed_urls,
    github_feed_paths,
    normalize_github_repository,
    normalize_github_token,
    normalize_public_url,
    normalize_repository_directory,
)


def test_build_feed_urls_defaults_to_backend_endpoint() -> None:
    urls = build_feed_urls(
        slug="random-slug",
        public_origin="https://backend.example.test/",
        publication_settings={"active_target": PublicationTarget.BACKEND},
    )

    assert urls.feed_url == "https://backend.example.test/f/random-slug.xml"
    assert urls.raw_feed_url == "https://backend.example.test/f/random-slug.xml?body=raw"


def test_build_feed_urls_uses_github_directory_for_static_file_urls() -> None:
    urls = build_feed_urls(
        slug="random-slug",
        public_origin="https://backend.example.test",
        publication_settings={
            "active_target": PublicationTarget.GITHUB,
            "github_public_url": "https://cdn.example.test/rss/",
            "github_directory": "own",
        },
    )

    assert urls.feed_url == "https://cdn.example.test/rss/own/random-slug.xml"
    assert urls.raw_feed_url == "https://cdn.example.test/rss/own/random-slug.raw.xml"


def test_build_feed_urls_keeps_root_github_directory_at_public_url() -> None:
    urls = build_feed_urls(
        slug="random-slug",
        public_origin="https://backend.example.test",
        publication_settings={
            "active_target": PublicationTarget.GITHUB,
            "github_public_url": "https://cdn.example.test/rss/",
            "github_directory": "",
        },
    )

    assert urls.feed_url == "https://cdn.example.test/rss/random-slug.xml"
    assert urls.raw_feed_url == "https://cdn.example.test/rss/random-slug.raw.xml"


def test_build_feed_urls_does_not_duplicate_github_directory_already_in_public_url() -> None:
    urls = build_feed_urls(
        slug="random-slug",
        public_origin="https://backend.example.test",
        publication_settings={
            "active_target": PublicationTarget.GITHUB,
            "github_public_url": "https://cdn.example.test/rss/own/",
            "github_directory": "own",
        },
    )

    assert urls.feed_url == "https://cdn.example.test/rss/own/random-slug.xml"
    assert urls.raw_feed_url == "https://cdn.example.test/rss/own/random-slug.raw.xml"


def test_build_feed_urls_falls_back_to_backend_when_github_url_is_missing() -> None:
    urls = build_feed_urls(
        slug="random-slug",
        public_origin="https://backend.example.test",
        publication_settings={
            "active_target": PublicationTarget.GITHUB,
            "github_public_url": "",
        },
    )

    assert urls.feed_url == "https://backend.example.test/f/random-slug.xml"
    assert urls.raw_feed_url == "https://backend.example.test/f/random-slug.xml?body=raw"


def test_github_repository_normalization_accepts_owner_repo_and_urls() -> None:
    assert normalize_github_repository("owner/repo") == "owner/repo"
    assert normalize_github_repository("https://github.com/Owner/Repo.git") == "Owner/Repo"
    assert normalize_github_repository("git@github.com:owner/repo.git") == "owner/repo"


def test_github_repository_normalization_rejects_non_github_remotes() -> None:
    for value in (
        "https://gitlab.com/owner/repo",
        "ssh://git@example.test/owner/repo.git",
        "owner/repo/extra",
        "../repo",
    ):
        try:
            normalize_github_repository(value)
        except ValueError:
            continue
        raise AssertionError(f"expected {value!r} to be rejected")


def test_repository_directory_normalization_allows_root_and_relative_paths() -> None:
    assert normalize_repository_directory("") == ""
    assert normalize_repository_directory(" feeds/newsletters/ ") == "feeds/newsletters"
    assert github_feed_paths("random", "") == ("random.xml", "random.raw.xml")
    assert github_feed_paths("random", "feeds/newsletters") == (
        "feeds/newsletters/random.xml",
        "feeds/newsletters/random.raw.xml",
    )


def test_repository_directory_normalization_rejects_escape_paths() -> None:
    for value in ("/feeds", "../feeds", "feeds/../other", "feeds\\other"):
        try:
            normalize_repository_directory(value)
        except ValueError:
            continue
        raise AssertionError(f"expected {value!r} to be rejected")


def test_public_url_normalization_requires_http_base_url() -> None:
    assert normalize_public_url(" https://cdn.example.test/rss/ ") == "https://cdn.example.test/rss"

    for value in ("", "ftp://cdn.example.test/rss", "https://cdn.example.test/rss?x=1"):
        try:
            normalize_public_url(value)
        except ValueError:
            continue
        raise AssertionError(f"expected {value!r} to be rejected")


def test_github_token_normalization_requires_printable_ascii() -> None:
    assert normalize_github_token(" ghp_secret-token_123 ") == "ghp_secret-token_123"

    for value in ("ghp_secret token", "ghp_secret\ntoken", "ghp_secret◊token"):
        try:
            normalize_github_token(value)
        except ValueError as exc:
            assert "printable ASCII" in str(exc)
            continue
        raise AssertionError(f"expected {value!r} to be rejected")
