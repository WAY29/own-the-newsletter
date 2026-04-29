# Own New Newsletter PRD

## Problem Statement

用户想把 newsletter 从邮箱阅读流里抽出来，用 RSS 阅读器统一阅读。参考项目 `kill-the-newsletter` 通过托管邮件服务生成收件地址，但本项目不想部署 SMTP/邮件服务，而是读取用户已有 IMAP 邮箱，把匹配指定收件人的邮件转换成本地 RSS feed。

用户需要一个个人自托管工具，能在个人电脑或服务器上运行，通过 Web 管理面板配置每个 feed 的 IMAP 凭据、收件人规则、同步文件夹、保留数量和同步设置，并把生成的 RSS 通过随机 URL 暴露给 feed reader。

## Solution

第一版实现一个 Docker Compose 部署的个人 RSS 转换服务。后端使用 Python + FastAPI，负责管理员认证、feed 配置 API、IMAP 同步、邮件解析、正文清洗、RSS 文件生成和 RSS endpoint。前端使用 React + Vite + shadcn/ui，作为独立 Admin Panel 访问后端 API。生产环境通过 Nginx 暴露同源 URL：`/admin` 给管理面板，`/api` 给管理 API，`/f/{random}.xml` 给 RSS feed。

每个 Feed Rule 自带 IMAP 凭据、同步文件夹和收件人过滤规则。同步过程只读 IMAP，不标记已读、不移动、不删除邮件。匹配到的邮件会存为 Imported Message，并通过 Feed Item 关联到对应 RSS Feed。RSS 默认输出清洗后的 HTML 正文，`?body=raw` 输出原始 HTML。RSS item 的 `description` 放摘要，`content:encoded` 放正文。

## User Stories

1. As an administrator, I want to log in with a configured admin token, so that only I can manage feeds.
2. As an administrator, I want my browser session to persist for 30 days, so that I do not need to log in every time.
3. As an administrator, I want the admin session stored in an HttpOnly cookie, so that the token is not stored in frontend local storage.
4. As an administrator, I want to create a feed from the web UI, so that I do not need to edit configuration files.
5. As an administrator, I want to enter IMAP host, port, TLS mode, username, password, and folders per feed, so that each feed can read from the mailbox source I choose.
6. As an administrator, I want IMAP credentials validated before saving, so that broken mailbox settings do not enter the sync loop.
7. As an administrator, I want saved IMAP passwords encrypted in SQLite, so that the database file alone does not expose mailbox passwords.
8. As an administrator, I want the encryption key provided through runtime configuration, so that login token rotation does not affect credential decryption.
9. As an administrator, I want each feed to choose one or more IMAP folders, so that different feeds can read from `INBOX`, newsletter folders, or service-specific folders.
10. As an administrator, I want `INBOX` to be the default folder, so that common setup is fast.
11. As an administrator, I want to configure a recipient address per feed, so that only messages sent to that address appear in the RSS feed.
12. As an administrator, I want recipient matching to check `To`, `Cc`, `Delivered-To`, and `X-Original-To`, so that IMAP-based filtering works across common mailbox providers.
13. As an administrator, I want recipient matching to be case-insensitive exact address matching, so that capitalization does not break matching while plus aliases are not guessed.
14. As an administrator, I want a preview of recent matching emails before saving a feed, so that I can confirm the recipient rule works.
15. As an administrator, I want preview to allow zero matches, so that I can create feeds for newsletters that have not sent mail yet.
16. As an administrator, I want to choose a human-readable feed title, so that the RSS reader shows a useful subscription name.
17. As an administrator, I want feed edits to preserve existing items, so that changing future matching behavior does not erase history.
18. As an administrator, I want the first import to use a configurable backfill window, so that I can control how much existing mail enters the feed.
19. As an administrator, I want manual sync for a feed, so that I can test or refresh it without waiting for the schedule.
20. As an administrator, I want manual sync to import only new messages, so that it does not rerun historical backfill.
21. As an administrator, I want duplicate sync triggers for the same feed to be skipped, so that scheduled and manual sync do not race.
22. As an administrator, I want sync status shown in the Admin Panel, so that I can see last run time, outcome, counts, and error summaries.
23. As an administrator, I want failed syncs to preserve clear error summaries, so that I can fix credentials, folders, or connectivity.
24. As an administrator, I want private logs that avoid sensitive values, so that logs do not leak message bodies, passwords, full emails, or full random feed URLs.
25. As an administrator, I want multiple feeds to be independent, so that one matching feed does not consume or exclude messages from another.
26. As an administrator, I want feeds with identical mailbox settings to share internal scanning work, so that the app does not repeatedly log into the same mailbox unnecessarily.
27. As an administrator, I want one imported message body stored once and linked to multiple feeds when needed, so that storage is not duplicated.
28. As an administrator, I want feed retention by configurable item count, so that RSS files stay bounded.
29. As an administrator, I want retained older feed items archived rather than deleted, so that history and deduplication remain stable.
30. As an administrator, I want deleting a feed to remove its feed associations and clean only orphaned messages, so that shared messages used by other feeds are not lost.
31. As an RSS reader user, I want each feed exposed as a random unguessable URL, so that I can subscribe without session auth or token parameters.
32. As an RSS reader user, I want RSS access not to require login, so that ordinary feed readers can fetch it.
33. As an RSS reader user, I want RSS items sorted by email publication date descending, so that newsletters appear in expected order.
34. As an RSS reader user, I want each item title to come from the email subject, so that entries match the original newsletter.
35. As an RSS reader user, I want missing subjects to show `Untitled`, so that every RSS item has a title.
36. As an RSS reader user, I want item author to come from the email `From` header, so that I can see the sender.
37. As an RSS reader user, I want item published time to use the email `Date` header when valid, so that backfilled emails keep their original timing.
38. As an RSS reader user, I want stable RSS `guid` values, so that edited or republished feeds do not create duplicate unread items.
39. As an RSS reader user, I want `description` to contain a summary, so that list views remain readable.
40. As an RSS reader user, I want `content:encoded` to contain the full body, so that I can read the whole newsletter in the feed reader.
41. As an RSS reader user, I want summaries generated from normalized body text, so that every item has a consistent preview.
42. As an RSS reader user, I want summaries to default to 280 characters, so that previews are concise.
43. As an RSS reader user, I want clean HTML by default, so that dangerous or noisy email markup is reduced.
44. As an RSS reader user, I want `?body=raw` to expose original HTML, so that I can opt into maximum fidelity when needed.
45. As an RSS reader user, I want remote image URLs preserved, so that newsletter images can still render when the feed reader allows them.
46. As a deployer, I want runtime configuration from environment variables or `.env`, so that Docker and local deployments are straightforward.
47. As a deployer, I want Docker Compose as the primary deployment path, so that backend, frontend, and proxy can run together.
48. As a deployer, I want Nginx to provide same-origin routing, so that cookies and routes work consistently under one public origin.
49. As a deployer, I want SQLite and local feed files to be backup targets, so that migration is possible without UI import/export.
50. As a developer, I want Cloudflare Worker support out of first-version scope, so that the first version can stay focused on FastAPI, Docker, SQLite, and local files.

## Implementation Decisions

- Build a Python FastAPI backend as the authoritative API, sync runtime, RSS endpoint host, and local feed publisher.
- Build a React + Vite + shadcn/ui Admin Panel as a separate frontend app.
- Use Nginx in Docker Compose to expose one production origin for `/admin`, `/api`, and `/f/{random}.xml`.
- Use environment variables and `.env` for runtime configuration, including admin token, secret key, ports, data paths, and public origin.
- Store feed configuration, sync state, imported messages, feed items, sessions, and metadata in SQLite.
- Write RSS XML as local feed files, while keeping application state in SQLite.
- Use random unguessable feed URLs as the only RSS access barrier.
- Do not use a separate RSS token parameter, admin session, or login for RSS fetches.
- Use one admin token model for first version; no multi-user account system.
- Use login-to-session-cookie flow for the Admin Panel.
- Store server-side admin sessions with 30-day default expiry.
- Encrypt stored IMAP credentials using a startup-provided secret key.
- Treat each Feed Rule as feed-scoped configuration containing IMAP settings, sync folders, recipient filter, backfill window, retention, schedule, and feed title.
- Validate IMAP host, TLS, login, and folders before saving a feed.
- Support rule preview by scanning recent messages and showing match count and sample subjects.
- Keep Feed Rules independent; matching one rule never prevents matching another.
- Internally group identical IMAP account plus folder settings into Mailbox Sync Groups to avoid repeated scans.
- Store one Imported Message per Message Identity and link it to one or more Feed Items.
- Base Message Identity primarily on IMAP account, sync folder, UIDVALIDITY, and UID.
- Use Sync Cursors per folder after initial backfill.
- Use Read-only Sync only; never mark read, move, archive, or delete mailbox messages.
- Use a Backend Scheduler inside the single FastAPI backend instance.
- First version supports only one backend instance per database.
- Add per-feed Sync Locks so duplicate manual or scheduled triggers are skipped.
- Manual Sync affects only the selected Feed Rule and imports new messages only.
- Feed edits preserve existing Feed Items and affect future sync only.
- First version does not provide rebuild or re-backfill operation.
- Feed Retention archives older Feed Items out of RSS output but keeps records linked to Imported Messages.
- Delete feed removes that feed's Feed Items and cleans only Orphan Messages.
- Feed Publish rewrites the Local Feed File after imports.
- RSS item `guid` is derived from local Feed Item identity.
- RSS item title comes from email subject, falling back to `Untitled`.
- RSS item author comes from email `From`.
- RSS item published time comes from email `Date`, falling back to import time.
- RSS feed order is descending Item Published Time.
- RSS `description` contains Item Summary.
- RSS `content:encoded` contains full body.
- Default Body Mode is sanitized HTML.
- Raw Body Mode is selected with `?body=raw`.
- Store both raw and sanitized body versions.
- Use `inscriptis` for body-to-text summary extraction.
- Use `nh3` for sanitized HTML rendering.
- Preserve existing remote assets in email HTML.
- Do not import attachments, RSS enclosures, or `cid:` inline assets in the first version.
- Logs are Private Logs and must omit bodies, passwords, full email addresses, and full random feed URLs.
- UI import/export is out of scope; backups are filesystem-level SQLite, local feed files, and `.env`/Secret Key.

Recommended deep modules:

- `RecipientMatcher`: parses recipient-like headers and applies exact case-insensitive matching.
- `ImapSource`: validates IMAP settings, lists folders, fetches messages, and exposes stable message identities.
- `SyncEngine`: coordinates backfill, cursors, sync locks, mailbox sync groups, matching, and status updates.
- `MessageStore`: owns SQLite persistence for feed rules, imported messages, feed items, archived items, sessions, and sync state.
- `BodyProcessor`: converts email body to raw body, sanitized body, text summary, and remote-asset-preserving output.
- `RssRenderer`: renders deterministic RSS XML from feed metadata and feed items.
- `FeedPublisher`: rewrites local feed files and exposes clean/raw body modes through feed endpoints.
- `AdminAuth`: owns admin-token login, session creation, expiry, cookie behavior, and logout.
- `AdminApi`: exposes feed CRUD, preview, manual sync, status, and random feed URL retrieval.
- `Scheduler`: runs periodic sync inside the single backend instance.
- `PrivateLogger`: redacts sensitive values consistently before logging.

## Testing Decisions

- Good tests should verify external behavior and stable contracts, not implementation details.
- Tests should focus on pure modules first, especially matching, body processing, RSS rendering, retention behavior, and sync orchestration.
- Recipient matching tests should cover `To`, `Cc`, `Delivered-To`, `X-Original-To`, display names, mixed case, exact matching, and no plus-alias normalization.
- Body processing tests should cover HTML input, text fallback, sanitization, raw mode preservation, summary length, HTML entity handling, and remote image preservation.
- RSS rendering tests should cover valid RSS XML, `description`, `content:encoded`, stable `guid`, item ordering, author, pubDate fallback, clean mode, and raw mode.
- Message store tests should cover one Imported Message linked to multiple Feed Items, archived Feed Items, retention visibility, feed deletion, and orphan cleanup.
- Sync engine tests should use fake IMAP sources to verify read-only behavior, initial backfill, cursor-based incremental sync, independent rules, Mailbox Sync Group matching, and duplicate trigger skipping.
- Admin auth tests should cover token login, bad token rejection, HttpOnly session cookie, session expiry, logout, and protected API access.
- Admin API tests should cover feed create, validation failure, edit preserving history, preview with zero matches, preview with matches, manual sync trigger, sync status, and random feed URL response.
- Feed endpoint tests should cover no admin session requirement, random URL lookup, missing feed 404, clean default body, raw body parameter, and no full URL logging.
- Scheduler tests should verify it triggers configured feeds and respects Single Backend Instance assumptions through process-level design.
- Deployment smoke tests should verify Docker Compose service wiring, Nginx route partitioning, backend health, frontend availability, and feed endpoint accessibility.
- Security regression tests should verify logs do not contain passwords, message bodies, full email addresses, or full random feed URLs.
- Existing prior art is limited because the current repo is documentation-only; tests should be introduced with the first implementation rather than retrofitted later.

## Out of Scope

- Cloudflare Worker support.
- SMTP service hosting.
- Email Routing support.
- Multi-admin users, roles, invitations, password reset, or user management.
- Feed enable/disable lifecycle.
- UI import/export for backup or migration.
- Rebuild feed or rerun backfill from the Admin Panel.
- IMAP mailbox mutation, including mark-as-read, move, archive, or delete.
- IMAP IDLE realtime sync.
- Multiple FastAPI backend instances against one database.
- Attachments, RSS enclosures, local image storage, and `cid:` inline asset import.
- Atom feed output.
- Dynamic-only feed generation without local feed files.
- Cross-origin production deployment.
- Full historical mailbox import by default.
- Full detailed debug logging of message content or secrets.
- Public indexing of RSS URLs.
- Plus-alias recipient normalization.

## Further Notes

The first version should optimize for a solid personal self-hosted workflow: one Docker Compose stack, one admin, feed-scoped configuration, predictable RSS output, and minimal mailbox side effects.

The highest-risk modules are IMAP synchronization, email parsing/body processing, and RSS correctness. These should be isolated early and tested before building a large UI surface around them.
