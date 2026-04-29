# Feed-Scoped IMAP Configuration

Each feed rule owns its IMAP credentials, sync folders, and recipient filter instead of referencing a shared account-level configuration. This keeps feeds independent and lets different feeds point at different folders or mailbox credentials, at the cost of possible duplicated credentials when multiple feeds use the same mailbox.
