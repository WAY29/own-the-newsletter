from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from pathlib import Path
import sqlite3
from typing import Any

from .publication import (
    GitHubFileChange,
    GitHubPublicationClient,
    GitHubPublicationConfig,
    PublicationError,
    build_feed_urls,
    github_feed_paths,
    normalize_github_branch,
    normalize_github_repository,
    normalize_github_token,
    normalize_public_url,
    normalize_repository_directory,
)
from .rss_renderer import RssFeed, RssItem, RssRenderer
from .security import CredentialCipher, redact_sensitive
from .store import MessageStore

logger = logging.getLogger(__name__)
GitHubClientFactory = Callable[[GitHubPublicationConfig], Any]


class FeedPublisher:
    def __init__(
        self,
        store: MessageStore,
        feeds_dir: Path,
        public_origin: str,
        *,
        cipher: CredentialCipher | None = None,
        github_client_factory: GitHubClientFactory | None = None,
    ) -> None:
        self.store = store
        self.feeds_dir = feeds_dir
        self.public_origin = public_origin.rstrip("/")
        self.cipher = cipher
        self.github_client_factory = github_client_factory or GitHubPublicationClient
        self.renderer = RssRenderer()
        self.feeds_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, feed: sqlite3.Row) -> None:
        settings = self.store.get_publication_settings(include_token_encrypted=True)
        self._write_feed_files(feed, settings)
        if settings["active_target"] == "github":
            self.store.mark_publication_started(feed)
            try:
                self._publish_github_feed(feed, settings)
            except Exception as exc:
                error = _safe_publication_error(exc)
                self.store.mark_publication_finished(status="failed", error=error, feed=feed)
                logger.warning("RSS publication failed feed_id=%s error=%s", feed["id"], error)
                return
            self.store.mark_publication_finished(status="success", feed=feed)

    def publish_by_id(self, feed_id: int) -> None:
        feed = self.store.get_feed(feed_id)
        if feed is not None:
            self.publish(feed)

    def publish_all(
        self,
        *,
        strict_external: bool = False,
        publication_settings: Mapping[str, Any] | None = None,
    ) -> None:
        settings = dict(publication_settings or self.store.get_publication_settings(include_token_encrypted=True))
        self.store.mark_publication_started()
        try:
            github_client = None
            changes: list[GitHubFileChange] = []
            feed_titles: list[str] = []
            if settings["active_target"] == "github":
                github_client = self._github_client(settings)
                github_client.validate_write_access()
            for feed in self.store.list_feeds():
                self._write_feed_files(feed, settings)
                if github_client is not None:
                    changes.extend(self._github_feed_changes(feed, settings))
                    feed_titles.append(_commit_feed_title(feed))
            if github_client is not None:
                github_client.commit_files(changes, _publish_all_message(feed_titles))
        except Exception as exc:
            error = _safe_publication_error(exc)
            self.store.mark_publication_finished(status="failed", error=error)
            logger.warning("RSS publication failed error=%s", error)
            if strict_external:
                raise PublicationError(error) from exc
            return
        self.store.mark_publication_finished(status="success")

    def activate_github(self) -> dict[str, Any]:
        settings = self.store.get_publication_settings(include_token_encrypted=True)
        candidate = {**settings, "active_target": "github"}
        self.publish_all(strict_external=True, publication_settings=candidate)
        self.store.update_publication_settings({"active_target": "github"})
        return self.store.get_publication_settings()

    def activate_backend(self) -> dict[str, Any]:
        self.store.update_publication_settings({"active_target": "backend"})
        self.publish_all(publication_settings=self.store.get_publication_settings(include_token_encrypted=True))
        return self.store.get_publication_settings()

    def feed_path(self, slug: str, *, raw: bool = False) -> Path:
        suffix = ".raw.xml" if raw else ".xml"
        return self.feeds_dir / f"{slug}{suffix}"

    def delete_files(self, slug: str) -> None:
        for raw in (False, True):
            path = self.feed_path(slug, raw=raw)
            if path.exists():
                path.unlink()

    def delete_feed(self, feed: sqlite3.Row) -> None:
        self.delete_files(str(feed["random_slug"]))
        settings = self.store.get_publication_settings(include_token_encrypted=True)
        if settings["active_target"] != "github":
            return
        self.store.mark_publication_started(feed)
        try:
            client = self._github_client(settings)
            clean_path, raw_path = github_feed_paths(str(feed["random_slug"]), str(settings["github_directory"]))
            client.delete_files([clean_path, raw_path], f"Delete RSS feed: {_commit_feed_title(feed)}")
        except Exception as exc:
            error = _safe_publication_error(exc)
            self.store.mark_publication_finished(status="failed", error=error, feed=feed)
            logger.warning("RSS publication delete failed feed_id=%s error=%s", feed["id"], error)
            return
        self.store.mark_publication_finished(status="success", feed=feed)

    def _write_feed_files(self, feed: sqlite3.Row, publication_settings: Mapping[str, Any]) -> None:
        self._write(feed, raw=False, publication_settings=publication_settings)
        self._write(feed, raw=True, publication_settings=publication_settings)

    def _write(self, feed: sqlite3.Row, *, raw: bool, publication_settings: Mapping[str, Any]) -> None:
        slug = str(feed["random_slug"])
        urls = build_feed_urls(
            slug=slug,
            public_origin=self.public_origin,
            publication_settings=publication_settings,
        )
        feed_url = urls.feed_url
        items = [
            RssItem(
                title=row["subject"],
                author=row["author"] or "",
                link=f"{feed_url}#item-{row['feed_item_id']}",
                guid=row["guid"],
                published_at=row["published_at"],
                description=row["summary"],
                body_html=row["raw_html"] if raw else row["sanitized_html"],
            )
            for row in self.store.list_feed_items(int(feed["id"]))
        ]
        rss = self.renderer.render(
            RssFeed(
                title=feed["title"],
                link=feed_url,
                description=f"Messages from sources matching {feed['sender']}",
                items=items,
            )
        )
        self.feed_path(slug, raw=raw).write_text(rss, encoding="utf-8")

    def _publish_github_feed(
        self,
        feed: sqlite3.Row,
        settings: Mapping[str, Any],
        *,
        github_client: Any | None = None,
    ) -> None:
        client = github_client or self._github_client(settings)
        client.commit_files(
            self._github_feed_changes(feed, settings),
            f"Publish RSS feed: {_commit_feed_title(feed)}",
        )

    def _github_feed_changes(
        self,
        feed: sqlite3.Row,
        settings: Mapping[str, Any],
    ) -> list[GitHubFileChange]:
        slug = str(feed["random_slug"])
        clean_path, raw_path = github_feed_paths(slug, str(settings["github_directory"]))
        return [
            GitHubFileChange(clean_path, self.feed_path(slug).read_text(encoding="utf-8")),
            GitHubFileChange(raw_path, self.feed_path(slug, raw=True).read_text(encoding="utf-8")),
        ]

    def _github_client(self, settings: Mapping[str, Any]) -> Any:
        if self.cipher is None:
            raise PublicationError("GitHub publication token cannot be decrypted in this runtime")
        token_encrypted = str(settings.get("github_token_encrypted") or "")
        if not token_encrypted:
            raise PublicationError("GitHub token is required before activation")
        token = normalize_github_token(self.cipher.decrypt(token_encrypted))
        if not token:
            raise PublicationError("GitHub token is required before activation")
        config = GitHubPublicationConfig(
            repository=normalize_github_repository(str(settings.get("github_repository") or "")),
            branch=normalize_github_branch(str(settings.get("github_branch") or "")),
            directory=normalize_repository_directory(str(settings.get("github_directory") or "")),
            public_url=normalize_public_url(str(settings.get("github_public_url") or "")),
            token=token,
        )
        return self.github_client_factory(config)


def _safe_publication_error(exc: Exception) -> str:
    return redact_sensitive(str(exc))


def _publish_all_message(feed_titles: list[str]) -> str:
    if not feed_titles:
        return "Publish RSS feeds: no feeds"
    if len(feed_titles) == 1:
        return f"Publish RSS feed: {feed_titles[0]}"
    return "Publish RSS feeds: " + ", ".join(feed_titles)


def _commit_feed_title(feed: Mapping[str, Any]) -> str:
    title = " ".join(str(feed["title"]).split())
    return title or "Untitled feed"
