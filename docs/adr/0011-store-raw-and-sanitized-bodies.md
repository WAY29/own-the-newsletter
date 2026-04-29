# Store Raw and Sanitized Bodies

Imported feed items store both the original HTML body and the sanitized HTML body. This makes feed publishing deterministic for the default clean mode and the optional `?body=raw` mode, at the cost of larger local storage and the need to treat the database as containing sensitive raw email content.
