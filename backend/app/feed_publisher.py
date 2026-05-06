from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from pathlib import Path
import sqlite3
from time import perf_counter
from typing import Any

from .activity_log import ActivityLogRecorder
from .publication import (
    GitHubFileChange,
    GitHubPublicationClient,
    GitHubPublicationConfig,
    PublicationError,
    PublicationTarget,
    build_feed_urls,
    coerce_publication_target,
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
        activity_log_recorder: ActivityLogRecorder | None = None,
    ) -> None:
        self.store = store
        self.feeds_dir = feeds_dir
        self.public_origin = public_origin.rstrip("/")
        self.cipher = cipher
        self.github_client_factory = github_client_factory or GitHubPublicationClient
        self.activity_log_recorder = activity_log_recorder or ActivityLogRecorder(store)
        self.renderer = RssRenderer()
        self.feeds_dir.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        feed: sqlite3.Row,
        *,
        trigger: str = "feed_change_publication",
        record_activity: bool = True,
    ) -> bool:
        settings = self.store.get_publication_settings(include_token_encrypted=True)
        target = coerce_publication_target(settings["active_target"])
        started = perf_counter()
        if record_activity:
            self.store.mark_publication_started(feed)
        try:
            self._write_feed_files(feed, settings)
            if target == PublicationTarget.GITHUB:
                self._publish_github_feed(feed, settings)
        except Exception as exc:
            error = _safe_publication_error(exc)
            if record_activity:
                self.store.mark_publication_finished(status="failed", error=error, feed=feed)
                self._record_publish(
                    trigger=trigger,
                    status="failed",
                    publication_target=target,
                    feed=feed,
                    feed_count=1,
                    file_count=2,
                    started=started,
                    error=error,
                )
            logger.warning("RSS publication failed feed_id=%s error=%s", feed["id"], error)
            return False
        if record_activity:
            self.store.mark_publication_finished(status="success", feed=feed)
            self._record_publish(
                trigger=trigger,
                status="success",
                publication_target=target,
                feed=feed,
                feed_count=1,
                file_count=2,
                started=started,
            )
        return True

    def publish_by_id(self, feed_id: int, *, trigger: str = "manual_sync") -> None:
        feed = self.store.get_feed(feed_id)
        if feed is not None:
            self.publish(feed, trigger=trigger)

    def publish_all(
        self,
        *,
        strict_external: bool = False,
        publication_settings: Mapping[str, Any] | None = None,
        trigger: str = "publication_retry",
        record_activity: bool = True,
    ) -> None:
        settings = dict(publication_settings or self.store.get_publication_settings(include_token_encrypted=True))
        target = coerce_publication_target(settings["active_target"])
        started = perf_counter()
        feeds = self.store.list_feeds()
        feed_count = len(feeds)
        file_count = feed_count * 2
        if record_activity:
            self.store.mark_publication_started()
        try:
            github_client = None
            changes: list[GitHubFileChange] = []
            feed_titles: list[str] = []
            if target == PublicationTarget.GITHUB:
                github_client = self._github_client(settings)
                github_client.validate_write_access()
            for feed in feeds:
                self._write_feed_files(feed, settings)
                if github_client is not None:
                    changes.extend(self._github_feed_changes(feed, settings))
                    feed_titles.append(_commit_feed_title(feed))
            if github_client is not None:
                file_count = len(changes)
                github_client.commit_files(changes, _publish_all_message(feed_titles))
        except Exception as exc:
            error = _safe_publication_error(exc)
            if record_activity:
                self.store.mark_publication_finished(status="failed", error=error)
                self._record_publish(
                    trigger=trigger,
                    status="failed",
                    publication_target=target,
                    feed_count=feed_count,
                    file_count=file_count,
                    started=started,
                    error=error,
                    metadata={"scope": "all_feeds"},
                )
            logger.warning("RSS publication failed error=%s", error)
            if strict_external:
                raise PublicationError(error) from exc
            return
        if record_activity:
            self.store.mark_publication_finished(status="success")
            self._record_publish(
                trigger=trigger,
                status="success",
                publication_target=target,
                feed_count=feed_count,
                file_count=file_count,
                started=started,
                metadata={"scope": "all_feeds"},
            )

    def activate_github(self) -> dict[str, Any]:
        settings = self.store.get_publication_settings(include_token_encrypted=True)
        candidate = {**settings, "active_target": PublicationTarget.GITHUB}
        self.publish_all(
            strict_external=True,
            publication_settings=candidate,
            trigger="publication_activation",
        )
        self.store.update_publication_settings({"active_target": PublicationTarget.GITHUB})
        return self.store.get_publication_settings()

    def activate_backend(self) -> dict[str, Any]:
        self.store.update_publication_settings({"active_target": PublicationTarget.BACKEND})
        self.publish_all(
            publication_settings=self.store.get_publication_settings(include_token_encrypted=True),
            trigger="publication_activation",
        )
        return self.store.get_publication_settings()

    def feed_path(self, slug: str, *, raw: bool = False) -> Path:
        suffix = ".raw.xml" if raw else ".xml"
        return self.feeds_dir / f"{slug}{suffix}"

    def delete_files(self, slug: str) -> int:
        deleted = 0
        for raw in (False, True):
            path = self.feed_path(slug, raw=raw)
            if path.exists():
                path.unlink()
                deleted += 1
        return deleted

    def delete_feed(self, feed: sqlite3.Row, *, trigger: str = "feed_change_publication") -> None:
        deleted_count = self.delete_files(str(feed["random_slug"]))
        settings = self.store.get_publication_settings(include_token_encrypted=True)
        target = coerce_publication_target(settings["active_target"])
        started = perf_counter()
        file_count = max(2, deleted_count)
        if target != PublicationTarget.GITHUB:
            self.store.mark_publication_started(feed)
            self.store.mark_publication_finished(status="success", feed=feed)
            self._record_publish(
                trigger=trigger,
                status="success",
                publication_target=target,
                feed=feed,
                feed_count=1,
                file_count=file_count,
                started=started,
                metadata={"action": "delete"},
            )
            return
        self.store.mark_publication_started(feed)
        try:
            client = self._github_client(settings)
            clean_path, raw_path = github_feed_paths(str(feed["random_slug"]), str(settings["github_directory"]))
            client.delete_files([clean_path, raw_path], f"Delete RSS feed: {_commit_feed_title(feed)}")
        except Exception as exc:
            error = _safe_publication_error(exc)
            self.store.mark_publication_finished(status="failed", error=error, feed=feed)
            self._record_publish(
                trigger=trigger,
                status="failed",
                publication_target=target,
                feed=feed,
                feed_count=1,
                file_count=2,
                started=started,
                error=error,
                metadata={"action": "delete"},
            )
            logger.warning("RSS publication delete failed feed_id=%s error=%s", feed["id"], error)
            return
        self.store.mark_publication_finished(status="success", feed=feed)
        self._record_publish(
            trigger=trigger,
            status="success",
            publication_target=target,
            feed=feed,
            feed_count=1,
            file_count=2,
            started=started,
            metadata={"action": "delete"},
        )

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

    def _record_publish(
        self,
        *,
        trigger: str,
        status: str,
        publication_target: PublicationTarget,
        feed_count: int,
        file_count: int,
        started: float,
        feed: sqlite3.Row | None = None,
        error: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.activity_log_recorder.record_publish(
            trigger=trigger,
            status=status,
            publication_target=publication_target,
            feed_id=int(feed["id"]) if feed is not None else None,
            feed_title=str(feed["title"]) if feed is not None else None,
            feed_count=feed_count,
            file_count=file_count,
            duration_ms=int((perf_counter() - started) * 1000),
            error=error,
            metadata=metadata,
        )


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
