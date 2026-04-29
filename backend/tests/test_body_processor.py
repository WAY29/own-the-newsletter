from app.body_processor import BodyProcessor, plain_text_to_html


def test_body_processor_sanitizes_scripts_preserves_remote_images_and_summarizes() -> None:
    html = """
    <article>
      <script>alert("x")</script>
      <h1>Hello</h1>
      <p>Long newsletter body with <strong>markup</strong>.</p>
      <img src="https://cdn.example.test/image.png" alt="hero">
    </article>
    """

    processed = BodyProcessor().process(html, summary_chars=34)

    assert "script" not in processed.sanitized_html.lower()
    assert "https://cdn.example.test/image.png" in processed.sanitized_html
    assert processed.summary == "Hello Long newsletter body with..."


def test_plain_text_to_html_escapes_and_preserves_paragraphs() -> None:
    assert plain_text_to_html("One <two>\n\nThree") == "<p>One &lt;two&gt;</p>\n<p>Three</p>"
