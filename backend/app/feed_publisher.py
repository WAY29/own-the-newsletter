from __future__ import annotations

from pathlib import Path
import sqlite3

from .rss_renderer import RssFeed, RssItem, RssRenderer
from .store import MessageStore


class FeedPublisher:
    def __init__(self, store: MessageStore, feeds_dir: Path, public_origin: str) -> None:
        self.store = store
        self.feeds_dir = feeds_dir
        self.public_origin = public_origin.rstrip("/")
        self.renderer = RssRenderer()
        self.feeds_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, feed: sqlite3.Row) -> None:
        self._write(feed, raw=False)
        self._write(feed, raw=True)

    def publish_by_id(self, feed_id: int) -> None:
        feed = self.store.get_feed(feed_id)
        if feed is not None:
            self.publish(feed)

    def feed_path(self, slug: str, *, raw: bool = False) -> Path:
        suffix = ".raw.xml" if raw else ".xml"
        return self.feeds_dir / f"{slug}{suffix}"

    def delete_files(self, slug: str) -> None:
        for raw in (False, True):
            path = self.feed_path(slug, raw=raw)
            if path.exists():
                path.unlink()

    def _write(self, feed: sqlite3.Row, *, raw: bool) -> None:
        slug = str(feed["random_slug"])
        feed_url = f"{self.public_origin}/f/{slug}.xml"
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
                description=f"Messages matching {feed['recipient']}",
                items=items,
            )
        )
        self.feed_path(slug, raw=raw).write_text(rss, encoding="utf-8")

