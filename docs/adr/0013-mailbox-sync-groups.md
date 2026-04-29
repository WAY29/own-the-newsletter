# Mailbox Sync Groups

The product model stays feed-scoped, but the synchronizer groups feed rules that have identical IMAP account settings and sync folders so the mailbox is scanned once and then matched against multiple recipient filters. This preserves independent feed configuration while avoiding unnecessary repeated IMAP logins and folder scans.
