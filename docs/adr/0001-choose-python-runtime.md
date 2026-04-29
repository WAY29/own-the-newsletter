# Choose Python Runtime

This project uses Python instead of the JS/Node runtime used by the reference project because its core job is local IMAP synchronization, email parsing, RSS file generation, and HTML-to-text processing rather than running a hosted SMTP service. Python gives a straightforward local deployment model and a suitable body-processing stack, with `inscriptis` for summary text extraction and `nh3` for sanitized HTML rendering.
