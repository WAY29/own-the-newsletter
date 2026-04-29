# Single Backend Scheduler

The first version runs scheduled IMAP synchronization inside a single FastAPI backend instance. This keeps personal deployment simple and avoids a separate worker or cron requirement, but it means one database must not be served by multiple backend replicas until a lease or job-locking mechanism is introduced.
