# Encrypt Stored IMAP Credentials

IMAP credentials entered through the admin panel are encrypted before being stored in SQLite using a startup-provided secret key. This is more complex than plaintext local storage, but it prevents the database file alone from exposing mailbox passwords and keeps the administrator login token separate from credential encryption.
