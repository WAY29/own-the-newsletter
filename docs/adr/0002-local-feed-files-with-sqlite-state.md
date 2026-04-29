# Local Feed Files with SQLite State

RSS output is written as local XML files, while feed rules, imported message identities, item metadata, and synchronization state are stored in SQLite. This keeps the published feed easy to serve from a filesystem without turning RSS XML into the application's database or relying on mailbox mutation for deduplication.
