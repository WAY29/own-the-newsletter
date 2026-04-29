import xml.etree.ElementTree as ET

from app.rss_renderer import RssFeed, RssItem, RssRenderer


def test_rss_renderer_outputs_rss_with_content_encoded_and_stable_guid() -> None:
    xml = RssRenderer().render(
        RssFeed(
            title="Feed",
            link="https://example.test/f/random.xml",
            description="Description",
            items=[
                RssItem(
                    title="Item",
                    author="Author <author@example.test>",
                    link="https://example.test/f/random.xml#item-1",
                    guid="own-newsletter:item:1",
                    published_at="2026-04-29T00:00:00+00:00",
                    description="Summary",
                    body_html="<p>Full body</p>",
                )
            ],
        )
    )

    root = ET.fromstring(xml)
    item = root.find("./channel/item")

    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    assert item is not None
    assert item.findtext("guid") == "own-newsletter:item:1"
    assert item.findtext("description") == "Summary"
    assert item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") == "<p>Full body</p>"

