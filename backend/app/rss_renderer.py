from __future__ import annotations

from dataclasses import dataclass
from email.utils import format_datetime
import xml.etree.ElementTree as ET

from .timeutil import rss_datetime, utc_now


@dataclass(frozen=True)
class RssItem:
    title: str
    author: str
    link: str
    guid: str
    published_at: str
    description: str
    body_html: str


@dataclass(frozen=True)
class RssFeed:
    title: str
    link: str
    description: str
    items: list[RssItem]


class RssRenderer:
    def render(self, feed: RssFeed) -> str:
        ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")
        ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

        rss = ET.Element(
            "rss",
            {
                "version": "2.0",
            },
        )
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = feed.title
        ET.SubElement(channel, "link").text = feed.link
        ET.SubElement(channel, "description").text = feed.description
        ET.SubElement(channel, "lastBuildDate").text = format_datetime(utc_now(), usegmt=True)
        ET.SubElement(
            channel,
            "{http://www.w3.org/2005/Atom}link",
            {"href": feed.link, "rel": "self", "type": "application/rss+xml"},
        )

        for item in feed.items:
            node = ET.SubElement(channel, "item")
            ET.SubElement(node, "title").text = item.title or "Untitled"
            ET.SubElement(node, "link").text = item.link
            guid = ET.SubElement(node, "guid", {"isPermaLink": "false"})
            guid.text = item.guid
            ET.SubElement(node, "pubDate").text = rss_datetime(item.published_at)
            if item.author:
                ET.SubElement(node, "author").text = item.author
            ET.SubElement(node, "description").text = item.description
            ET.SubElement(node, "{http://purl.org/rss/1.0/modules/content/}encoded").text = item.body_html

        xml = ET.tostring(rss, encoding="unicode", short_empty_elements=False)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml
