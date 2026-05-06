from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import json
import re
from typing import Any, Callable
from urllib.parse import quote, urlsplit

import requests

from .security import redact_sensitive


@dataclass(frozen=True)
class FeedUrls:
    feed_url: str
    raw_feed_url: str


class PublicationTarget(StrEnum):
    BACKEND = "backend"
    GITHUB = "github"


def coerce_publication_target(value: object) -> PublicationTarget:
    if isinstance(value, PublicationTarget):
        return value
    try:
        return PublicationTarget(str(value))
    except ValueError:
        return PublicationTarget.BACKEND


@dataclass(frozen=True)
class GitHubPublicationConfig:
    repository: str
    branch: str
    directory: str
    public_url: str
    token: str


@dataclass(frozen=True)
class GitHubFileChange:
    path: str
    content: str | None


class PublicationError(Exception):
    pass


_OWNER_RE = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
_REPO_RE = r"[A-Za-z0-9_.-]+"
_OWNER_REPO_RE = re.compile(rf"^(?P<owner>{_OWNER_RE})/(?P<repo>{_REPO_RE})(?:\.git)?$")
_SSH_GITHUB_RE = re.compile(rf"^git@github\.com:(?P<owner>{_OWNER_RE})/(?P<repo>{_REPO_RE})(?:\.git)?$")


def normalize_github_repository(value: str) -> str:
    repository = value.strip()
    if not repository:
        raise ValueError("GitHub repository is required")

    direct_match = _OWNER_REPO_RE.match(repository)
    if direct_match:
        return _format_owner_repo(direct_match.group("owner"), direct_match.group("repo"))

    ssh_match = _SSH_GITHUB_RE.match(repository)
    if ssh_match:
        return _format_owner_repo(ssh_match.group("owner"), ssh_match.group("repo"))

    parsed = urlsplit(repository)
    host = parsed.netloc.lower()
    if parsed.scheme in {"http", "https"} and host in {"github.com", "www.github.com"}:
        if parsed.query or parsed.fragment:
            raise ValueError("GitHub repository URL must not include query or fragment")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2:
            return _format_owner_repo(parts[0], parts[1])

    raise ValueError("GitHub repository must be owner/repo or a github.com repository URL")


def normalize_github_branch(value: str) -> str:
    branch = value.strip()
    if not branch:
        raise ValueError("GitHub branch is required")
    if branch.startswith("/") or branch.endswith("/") or "\\" in branch or ".." in branch:
        raise ValueError("GitHub branch must be an existing branch name")
    return branch


def normalize_github_token(value: str) -> str:
    token = value.strip()
    if not token:
        return ""
    if any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise ValueError("GitHub token must contain only printable ASCII characters")
    return token


def normalize_repository_directory(value: str) -> str:
    directory = value.strip()
    if not directory:
        return ""
    if "\\" in directory or directory.startswith("/"):
        raise ValueError("Publication directory must be repository-relative")
    directory = directory.rstrip("/")
    parts = directory.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Publication directory must not contain empty, current, or parent path segments")
    return "/".join(parts)


def normalize_public_url(value: str) -> str:
    public_url = value.strip()
    if not public_url:
        raise ValueError("RSS public URL is required")
    parsed = urlsplit(public_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("RSS public URL must be an http or https URL")
    if parsed.query or parsed.fragment:
        raise ValueError("RSS public URL must not include query or fragment")
    return public_url.rstrip("/")


def build_feed_urls(
    *,
    slug: str,
    public_origin: str,
    publication_settings: Mapping[str, object],
) -> FeedUrls:
    backend_base = public_origin.rstrip("/")
    active_target = coerce_publication_target(
        publication_settings.get("active_target", PublicationTarget.BACKEND)
    )
    if active_target == PublicationTarget.GITHUB:
        public_url = str(publication_settings.get("github_public_url") or "").strip()
        if public_url:
            base = github_public_feed_base(
                public_url,
                str(publication_settings.get("github_directory") or ""),
            )
            return FeedUrls(
                feed_url=f"{base}/{slug}.xml",
                raw_feed_url=f"{base}/{slug}.raw.xml",
            )
    return FeedUrls(
        feed_url=f"{backend_base}/f/{slug}.xml",
        raw_feed_url=f"{backend_base}/f/{slug}.xml?body=raw",
    )


def github_public_feed_base(public_url: str, directory: str) -> str:
    base = normalize_public_url(public_url)
    directory = normalize_repository_directory(directory)
    if not directory:
        return base
    if urlsplit(base).path.rstrip("/").endswith(f"/{directory}"):
        return base
    return f"{base}/{directory}"


def github_feed_paths(slug: str, directory: str) -> tuple[str, str]:
    base = normalize_repository_directory(directory)
    clean_name = f"{slug}.xml"
    raw_name = f"{slug}.raw.xml"
    if not base:
        return clean_name, raw_name
    return f"{base}/{clean_name}", f"{base}/{raw_name}"


class GitHubPublicationClient:
    def __init__(
        self,
        config: GitHubPublicationConfig,
        *,
        api_base_url: str = "https://api.github.com",
        transport: Callable[..., tuple[int, dict[str, Any]]] | None = None,
    ) -> None:
        self.config = config
        self.api_base_url = api_base_url.rstrip("/")
        self._transport = transport or self._default_transport

    def validate_write_access(self) -> None:
        repository = self._request("GET", self._repo_path())
        permissions = repository.get("permissions")
        if isinstance(permissions, dict):
            has_write = any(bool(permissions.get(key)) for key in ("push", "admin", "maintain"))
            if not has_write:
                raise PublicationError("GitHub token does not have repository write permission")
        self._request("GET", f"{self._repo_path()}/branches/{quote(self.config.branch, safe='')}")

    def upsert_file(self, path: str, content: str, message: str) -> None:
        sha = self._get_file_sha(path)
        body = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": self.config.branch,
        }
        if sha:
            body["sha"] = sha
        self._request("PUT", self._contents_path(path), json_body=body, expected_statuses={200, 201})

    def delete_file(self, path: str, message: str) -> None:
        sha = self._get_file_sha(path)
        if sha is None:
            return
        self._request(
            "DELETE",
            self._contents_path(path),
            json_body={"message": message, "sha": sha, "branch": self.config.branch},
            expected_statuses={200},
        )

    def commit_files(self, changes: list[GitHubFileChange], message: str) -> None:
        if not changes:
            return
        head_sha, base_tree_sha = self._get_branch_head()
        tree_response = self._request(
            "POST",
            f"{self._repo_path()}/git/trees",
            json_body={
                "base_tree": base_tree_sha,
                "tree": [_tree_entry(change) for change in changes],
            },
            expected_statuses={201},
        )
        tree_sha = _required_str(tree_response, "sha", "GitHub create tree response did not include a sha")
        commit_response = self._request(
            "POST",
            f"{self._repo_path()}/git/commits",
            json_body={"message": message, "tree": tree_sha, "parents": [head_sha]},
            expected_statuses={201},
        )
        commit_sha = _required_str(
            commit_response,
            "sha",
            "GitHub create commit response did not include a sha",
        )
        self._request(
            "PATCH",
            self._ref_path(),
            json_body={"sha": commit_sha, "force": False},
            expected_statuses={200},
        )

    def delete_files(self, paths: list[str], message: str) -> None:
        existing_paths = [path for path in paths if self._get_file_sha(path) is not None]
        self.commit_files([GitHubFileChange(path, None) for path in existing_paths], message)

    def _get_file_sha(self, path: str) -> str | None:
        response = self._request(
            "GET",
            f"{self._contents_path(path)}?ref={quote(self.config.branch, safe='')}",
            expected_statuses={200, 404},
        )
        if response.get("_status") == 404:
            return None
        sha = response.get("sha")
        if not isinstance(sha, str) or not sha:
            raise PublicationError(f"GitHub contents response did not include a file sha for {path}")
        return sha

    def _get_branch_head(self) -> tuple[str, str]:
        branch = self._request(
            "GET",
            f"{self._repo_path()}/branches/{quote(self.config.branch, safe='')}",
        )
        commit = branch.get("commit")
        if not isinstance(commit, dict):
            raise PublicationError("GitHub branch response did not include commit metadata")
        head_sha = _required_str(commit, "sha", "GitHub branch response did not include a head sha")
        commit_details = commit.get("commit")
        if not isinstance(commit_details, dict):
            raise PublicationError("GitHub branch response did not include commit details")
        tree = commit_details.get("tree")
        if not isinstance(tree, dict):
            raise PublicationError("GitHub branch response did not include tree metadata")
        tree_sha = _required_str(tree, "sha", "GitHub branch response did not include a tree sha")
        return head_sha, tree_sha

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> dict[str, Any]:
        expected = expected_statuses or {200}
        try:
            token = normalize_github_token(self.config.token)
            status, body = self._transport(method, path, token=token, json_body=json_body)
        except PublicationError:
            raise
        except Exception as exc:
            raise PublicationError(self._redact(str(exc))) from exc
        if status in expected:
            result = dict(body)
            result["_status"] = status
            return result
        raise PublicationError(self._format_error(status, body))

    def _default_transport(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        try:
            response = requests.request(
                method,
                f"{self.api_base_url}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "own-new-newsletter",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json=json_body,
                timeout=30,
            )
            return int(response.status_code), _json_body(response.text)
        except requests.RequestException as exc:
            raise PublicationError(self._redact(str(exc))) from exc

    def _format_error(self, status: int, body: dict[str, Any]) -> str:
        message = body.get("message") if isinstance(body.get("message"), str) else json.dumps(body, sort_keys=True)
        if status == 401:
            return self._redact("GitHub token was rejected")
        if status == 403:
            return self._redact(f"GitHub API rejected the request: {message}")
        if status == 404:
            return self._redact(f"GitHub repository, branch, or file was not found: {message}")
        return self._redact(f"GitHub API error status={status}: {message}")

    def _redact(self, message: str) -> str:
        redacted = message.replace(self.config.token, "***")
        return redact_sensitive(redacted)

    def _repo_path(self) -> str:
        return f"/repos/{self.config.repository}"

    def _contents_path(self, path: str) -> str:
        return f"{self._repo_path()}/contents/{quote(path, safe='/')}"

    def _ref_path(self) -> str:
        return f"{self._repo_path()}/git/refs/heads/{quote(self.config.branch, safe='/')}"


def _format_owner_repo(owner: str, repo: str) -> str:
    repo = repo.removesuffix(".git")
    match = _OWNER_REPO_RE.match(f"{owner}/{repo}")
    if not match:
        raise ValueError("GitHub repository must be owner/repo or a github.com repository URL")
    return f"{match.group('owner')}/{match.group('repo')}"


def _json_body(payload: str) -> dict[str, Any]:
    if not payload.strip():
        return {}
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {"message": payload}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _required_str(body: Mapping[str, Any], key: str, message: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise PublicationError(message)
    return value


def _tree_entry(change: GitHubFileChange) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": change.path,
        "mode": "100644",
        "type": "blob",
    }
    if change.content is None:
        entry["sha"] = None
    else:
        entry["content"] = change.content
    return entry
