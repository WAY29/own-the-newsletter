import base64

import pytest

import app.publication as publication
from app.publication import (
    GitHubFileChange,
    GitHubPublicationClient,
    GitHubPublicationConfig,
    PublicationError,
)


class FakeGitHubTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, method, path, *, token, json_body=None):
        self.requests.append(
            {
                "method": method,
                "path": path,
                "token": token,
                "json": json_body,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected GitHub API request")
        return self.responses.pop(0)


def config() -> GitHubPublicationConfig:
    return GitHubPublicationConfig(
        repository="owner/repo",
        branch="pages",
        directory="feeds",
        public_url="https://cdn.example.test/rss",
        token="ghp_secret-token",
    )


def test_github_client_validates_repository_write_access_and_branch() -> None:
    transport = FakeGitHubTransport(
        [
            (200, {"permissions": {"push": True}}),
            (200, {"name": "pages"}),
        ]
    )
    client = GitHubPublicationClient(config(), transport=transport)

    client.validate_write_access()

    assert [request["method"] for request in transport.requests] == ["GET", "GET"]
    assert transport.requests[0]["path"] == "/repos/owner/repo"
    assert transport.requests[1]["path"] == "/repos/owner/repo/branches/pages"


def test_github_client_rejects_tokens_without_write_permission() -> None:
    transport = FakeGitHubTransport([(200, {"permissions": {"push": False, "admin": False, "maintain": False}})])
    client = GitHubPublicationClient(config(), transport=transport)

    with pytest.raises(PublicationError, match="write permission"):
        client.validate_write_access()


def test_github_client_upserts_new_file_with_base64_content() -> None:
    transport = FakeGitHubTransport(
        [
            (404, {"message": "Not Found"}),
            (201, {"content": {"path": "feeds/random.xml"}}),
        ]
    )
    client = GitHubPublicationClient(config(), transport=transport)

    client.upsert_file("feeds/random.xml", "<rss>clean</rss>", "Publish feed")

    assert transport.requests[0] == {
        "method": "GET",
        "path": "/repos/owner/repo/contents/feeds/random.xml?ref=pages",
        "token": "ghp_secret-token",
        "json": None,
    }
    put_body = transport.requests[1]["json"]
    assert transport.requests[1]["method"] == "PUT"
    assert transport.requests[1]["path"] == "/repos/owner/repo/contents/feeds/random.xml"
    assert put_body["branch"] == "pages"
    assert put_body["message"] == "Publish feed"
    assert base64.b64decode(put_body["content"]).decode("utf-8") == "<rss>clean</rss>"
    assert "sha" not in put_body


def test_github_client_updates_existing_file_with_sha() -> None:
    transport = FakeGitHubTransport(
        [
            (200, {"sha": "abc123"}),
            (200, {"content": {"path": "feeds/random.xml"}}),
        ]
    )
    client = GitHubPublicationClient(config(), transport=transport)

    client.upsert_file("feeds/random.xml", "<rss>clean</rss>", "Publish feed")

    assert transport.requests[1]["json"]["sha"] == "abc123"


def test_github_client_deletes_existing_file_and_ignores_missing_file() -> None:
    transport = FakeGitHubTransport(
        [
            (200, {"sha": "abc123"}),
            (200, {"content": None}),
            (404, {"message": "Not Found"}),
        ]
    )
    client = GitHubPublicationClient(config(), transport=transport)

    client.delete_file("feeds/random.xml", "Delete feed")
    client.delete_file("feeds/random.raw.xml", "Delete feed")

    assert transport.requests[1]["method"] == "DELETE"
    assert transport.requests[1]["path"] == "/repos/owner/repo/contents/feeds/random.xml"
    assert transport.requests[1]["json"]["sha"] == "abc123"
    assert len(transport.requests) == 3


def test_github_client_commits_multiple_file_changes_once() -> None:
    transport = FakeGitHubTransport(
        [
            (200, {"commit": {"sha": "head-commit", "commit": {"tree": {"sha": "base-tree"}}}}),
            (201, {"sha": "new-tree"}),
            (201, {"sha": "new-commit"}),
            (200, {"ref": "refs/heads/pages"}),
        ]
    )
    client = GitHubPublicationClient(config(), transport=transport)

    client.commit_files(
        [
            GitHubFileChange("feeds/a.xml", "<rss>A</rss>"),
            GitHubFileChange("feeds/a.raw.xml", "<rss>Raw A</rss>"),
        ],
        "Publish RSS feed: A",
    )

    assert [request["method"] for request in transport.requests] == ["GET", "POST", "POST", "PATCH"]
    assert transport.requests[0]["path"] == "/repos/owner/repo/branches/pages"
    tree_body = transport.requests[1]["json"]
    assert transport.requests[1]["path"] == "/repos/owner/repo/git/trees"
    assert tree_body["base_tree"] == "base-tree"
    assert tree_body["tree"] == [
        {
            "path": "feeds/a.xml",
            "mode": "100644",
            "type": "blob",
            "content": "<rss>A</rss>",
        },
        {
            "path": "feeds/a.raw.xml",
            "mode": "100644",
            "type": "blob",
            "content": "<rss>Raw A</rss>",
        },
    ]
    commit_body = transport.requests[2]["json"]
    assert transport.requests[2]["path"] == "/repos/owner/repo/git/commits"
    assert commit_body == {
        "message": "Publish RSS feed: A",
        "tree": "new-tree",
        "parents": ["head-commit"],
    }
    assert transport.requests[3]["path"] == "/repos/owner/repo/git/refs/heads/pages"
    assert transport.requests[3]["json"] == {"sha": "new-commit", "force": False}


def test_github_client_commits_deletions_once() -> None:
    transport = FakeGitHubTransport(
        [
            (200, {"sha": "a-sha"}),
            (200, {"sha": "raw-sha"}),
            (200, {"commit": {"sha": "head-commit", "commit": {"tree": {"sha": "base-tree"}}}}),
            (201, {"sha": "new-tree"}),
            (201, {"sha": "new-commit"}),
            (200, {"ref": "refs/heads/pages"}),
        ]
    )
    client = GitHubPublicationClient(config(), transport=transport)

    client.delete_files(["feeds/a.xml", "feeds/a.raw.xml"], "Delete RSS feed: A")

    assert len(transport.requests) == 6
    assert transport.requests[0]["path"] == "/repos/owner/repo/contents/feeds/a.xml?ref=pages"
    assert transport.requests[1]["path"] == "/repos/owner/repo/contents/feeds/a.raw.xml?ref=pages"
    assert transport.requests[3]["json"]["tree"] == [
        {
            "path": "feeds/a.xml",
            "mode": "100644",
            "type": "blob",
            "sha": None,
        },
        {
            "path": "feeds/a.raw.xml",
            "mode": "100644",
            "type": "blob",
            "sha": None,
        },
    ]


def test_github_client_delete_files_ignores_missing_files() -> None:
    transport = FakeGitHubTransport(
        [
            (404, {"message": "Not Found"}),
            (404, {"message": "Not Found"}),
        ]
    )
    client = GitHubPublicationClient(config(), transport=transport)

    client.delete_files(["feeds/a.xml", "feeds/a.raw.xml"], "Delete RSS feed: A")

    assert len(transport.requests) == 2


def test_github_default_transport_uses_requests(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        status_code = 201
        text = '{"sha": "new-tree"}'

    def fake_request(method, url, *, headers, json, timeout):
        calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse()

    monkeypatch.setattr(publication.requests, "request", fake_request)
    client = GitHubPublicationClient(config(), api_base_url="https://api.example.test")

    status, body = client._default_transport(
        "POST",
        "/repos/owner/repo/git/trees",
        token="ghp_secret-token",
        json_body={"tree": []},
    )

    assert status == 201
    assert body == {"sha": "new-tree"}
    assert calls == [
        {
            "method": "POST",
            "url": "https://api.example.test/repos/owner/repo/git/trees",
            "headers": {
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer ghp_secret-token",
                "Content-Type": "application/json",
                "User-Agent": "own-new-newsletter",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            "json": {"tree": []},
            "timeout": 30,
        }
    ]


def test_github_client_redacts_token_from_errors() -> None:
    transport = FakeGitHubTransport([(403, {"message": "Bad token ghp_secret-token"})])
    client = GitHubPublicationClient(config(), transport=transport)

    with pytest.raises(PublicationError) as exc_info:
        client.validate_write_access()

    message = str(exc_info.value)
    assert "ghp_secret-token" not in message
    assert "***" in message


def test_github_client_rejects_non_ascii_token_before_transport() -> None:
    transport = FakeGitHubTransport([(200, {"permissions": {"push": True}})])
    bad_config = GitHubPublicationConfig(
        repository="owner/repo",
        branch="pages",
        directory="feeds",
        public_url="https://cdn.example.test/rss",
        token="ghp_secret◊token",
    )
    client = GitHubPublicationClient(bad_config, transport=transport)

    with pytest.raises(PublicationError, match="printable ASCII"):
        client.validate_write_access()

    assert transport.requests == []
