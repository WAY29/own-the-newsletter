# GitHub Static Feed Publication

RSS publishing uses one active Publication Target at a time: the backend remains the default target, and GitHub can become the external static target only after repository validation and initial publication of the current feeds succeed. Static publication writes both clean and raw feed files because static hosts cannot select raw body mode through the backend-only `?body=raw` query parameter.

GitHub publication uses the GitHub API rather than `git` CLI so the backend container does not need to manage local clones, git identity, or token-bearing remote URLs. Publication failures are tracked separately from IMAP sync failures so imported messages and sync cursors are not reprocessed just to retry static delivery.
