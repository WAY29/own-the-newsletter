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


def test_body_processor_unwraps_newsletter_layout_for_reader_output() -> None:
    html = """
    <div class="email-shell">
      <table class="outer">
        <tbody>
          <tr>
            <td class="content-card">
              <span class="eyebrow">TLDR</span>
              <h1 class="headline">TLDR 2026-04-29</h1>
              <p class="lede">Behind every seamless payment is a better system.</p>
              <ul class="stories">
                <li><strong>GoFundMe</strong> reimagines charitable giving.</li>
              </ul>
              <a class="cta" href="https://example.test/story">Read the stories</a>
              <img class="logo" src="https://cdn.example.test/logo.png" alt="Logo">
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    """

    processed = BodyProcessor().process(html)
    lower_html = processed.sanitized_html.lower()

    assert processed.raw_html == html
    assert "<div" not in lower_html
    assert "<span" not in lower_html
    assert "<table" not in lower_html
    assert "<tbody" not in lower_html
    assert "<tr" not in lower_html
    assert "<td" not in lower_html
    assert "class=" not in lower_html
    assert "<h1>TLDR 2026-04-29</h1>" in processed.sanitized_html
    assert "<p>Behind every seamless payment is a better system.</p>" in processed.sanitized_html
    assert "<ul>" in processed.sanitized_html
    assert "<li><strong>GoFundMe</strong> reimagines charitable giving.</li>" in processed.sanitized_html
    assert 'href="https://example.test/story"' in processed.sanitized_html
    assert 'src="https://cdn.example.test/logo.png"' in processed.sanitized_html


def test_plain_text_to_html_escapes_and_preserves_paragraphs() -> None:
    assert plain_text_to_html("One <two>\n\nThree") == "<p>One &lt;two&gt;</p>\n<p>Three</p>"
