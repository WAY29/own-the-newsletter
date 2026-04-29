# Own New Newsletter

Own New Newsletter converts messages fetched from a user's IMAP mailbox into local RSS feeds for personal reading.

## Language

**Sender Filter**:
A rule that admits an email when source headers contain the configured text after both sides are lowercased.
_Avoid_: Recipient filter, exact address-only matching, plus-alias normalization

**IMAP Account**:
A configured mailbox connection used as the source for **Read-only Sync**.
_Avoid_: User account, newsletter account

**Verified IMAP Account**:
An **IMAP Account** that has passed host, TLS, login, and folder validation before being saved.
_Avoid_: Untested mailbox configuration

**Admin Panel**:
A password- or token-protected web interface for managing **IMAP Accounts** and **Feed Rules**.
_Avoid_: Static feed configuration, public user portal

**Manual Sync**:
An administrator-triggered **Read-only Sync** for one **Feed Rule** that imports new messages without rerunning the **Backfill Window**.
_Avoid_: User-facing refresh, mailbox mutation, group-wide sync

**Sync Lock**:
A per-**Feed Rule** guard that allows only one **Read-only Sync** to run at a time.
_Avoid_: Concurrent feed sync, queued duplicate sync

**Admin Token**:
A startup-configured secret used to create an authenticated **Admin Session**.
_Avoid_: Feed URL secret, user password, multi-user account

**Secret Key**:
A startup-provided encryption key used to protect stored **IMAP Account** credentials.
_Avoid_: Admin token, generated database secret

**Admin Session**:
An authenticated browser session that authorizes access to the **Admin Panel**.
_Avoid_: Bearer token storage

**Session Expiry**:
The configured expiration time for an **Admin Session**, defaulting to 30 days.
_Avoid_: Non-expiring admin session

**Public Origin**:
The externally visible origin that serves the **Admin Panel**, backend API, and **Feed Endpoints**.
_Avoid_: Cross-origin admin deployment

**Runtime Configuration**:
Startup settings provided through environment variables or `.env`, including server paths, ports, **Admin Token**, and **Secret Key**.
_Avoid_: Feed configuration file, CLI-only configuration

**Feed Rule**:
A per-feed configuration entry that combines one **IMAP Account**, one or more **Sync Folders**, and one **Sender Filter** to produce one local RSS feed.
_Avoid_: Account feed, folder feed

**Rule Edit**:
A change to a **Feed Rule** that affects only future synchronization and keeps existing **Feed Items**.
_Avoid_: Historical rebuild, implicit feed reset

**Mailbox Sync Group**:
An internal synchronization group that scans identical **IMAP Account** and **Sync Folders** once for multiple **Feed Rules**.
_Avoid_: Shared feed configuration, UI account grouping

**Independent Feed Rule**:
A **Feed Rule** whose matches do not exclude or affect matches for any other **Feed Rule**.
_Avoid_: Ordered rule, mutually exclusive rule

**Rule Preview**:
A temporary scan that shows recent emails matching a proposed **Feed Rule** before it is saved.
_Avoid_: Required first match, blind rule creation

**RSS Feed**:
A local subscription document containing the matched emails from one **Feed Rule**.
_Avoid_: Atom feed

**Feed Title**:
A human-readable title chosen in the **Admin Panel** for one **RSS Feed**.
_Avoid_: Sender address as title

**Local Feed File**:
An RSS XML file written to local storage for one **RSS Feed**.
_Avoid_: State database, mailbox archive

**Feed Publish**:
The act of rewriting a **Local Feed File** after new **Feed Items** are imported.
_Avoid_: Request-time feed generation, delayed batch publishing

**Feed Endpoint**:
An HTTP URL that serves a **Local Feed File** to a feed reader.
_Avoid_: Dynamic-only feed

**Random Feed URL**:
An unguessable **Feed Endpoint** URL used as the only access barrier for reading one **RSS Feed**.
_Avoid_: Feed access token, admin token, indexed public feed

**URL Namespace**:
The public path partition where `/admin` serves the **Admin Panel**, `/api` serves backend management APIs, and `/f/{random}.xml` serves **Random Feed URLs**.
_Avoid_: Mixed admin and feed routes

**Feed Item**:
An RSS item linking one **Imported Message** into one **RSS Feed**, rendering its summary in `description` and full body in `content:encoded`.
_Avoid_: Message storage, description-only body

**Item GUID**:
A stable RSS `guid` derived from the local **Feed Item** identity.
_Avoid_: Message-ID as guid, publish-time random guid

**Archived Feed Item**:
A **Feed Item** kept for history and deduplication but excluded from the published **RSS Feed** by **Feed Retention**.
_Avoid_: Deleted feed item, orphan message

**Item Title**:
The title of a **Feed Item**, taken from the email subject or `Untitled` when no subject exists.
_Avoid_: Sender-derived title

**Item Author**:
The author of a **Feed Item**, taken from the email `From` header.
_Avoid_: IMAP account as author

**Item Published Time**:
The publication time of a **Feed Item**, taken from the email `Date` header or the import time when the header is missing or invalid.
_Avoid_: Always-import-time, always-IMAP-received-time

**Feed Retention**:
The per-feed limit on how many recent **Feed Items** remain in the published **RSS Feed**.
_Avoid_: Unlimited feed history

**Feed Order**:
The ordering of **Feed Items** by descending **Item Published Time**.
_Avoid_: Import-order feed

**Item Summary**:
A configurable-length plain-text snippet derived from the normalized email body for a **Feed Item**, defaulting to 280 characters.
_Avoid_: Sender-provided summary, empty-by-default summary

**Body Mode**:
A subscription-level choice for rendering a **Feed Item** body as sanitized HTML by default or raw original HTML with `?body=raw`.
_Avoid_: Import mode, storage mode

**Remote Asset**:
An externally hosted image or media URL already referenced by an email body.
_Avoid_: Local attachment, inline CID asset

**Read-only Sync**:
An IMAP import pass that reads mailbox messages without changing their flags, folders, or existence.
_Avoid_: Mark-as-read sync, archive-after-import

**Sync Schedule**:
A configurable polling interval that triggers **Read-only Sync**.
_Avoid_: IMAP IDLE requirement, manual-only sync

**Backend Scheduler**:
The scheduler running inside the FastAPI backend process that triggers **Read-only Sync**.
_Avoid_: External cron requirement, separate worker by default

**Single Backend Instance**:
The first-version deployment constraint that only one FastAPI backend process may run against a database.
_Avoid_: Multi-instance sync

**Sync Status**:
The latest recorded sync result, timestamp, and error summary for an **IMAP Account** or **Feed Rule**.
_Avoid_: Log-only sync health

**Private Log**:
A log entry that records operational metadata without email bodies, passwords, full email addresses, or full **Random Feed URLs**.
_Avoid_: Full message log, secret-bearing URL log

**Backfill Window**:
The configured lookback period used when a **Feed Rule** imports existing mailbox messages for the first time.
_Avoid_: Full-history import by default, future-only import by default, admin-triggered rebuild

**Sync Folder**:
An IMAP folder selected for **Read-only Sync**, with `INBOX` as the default.
_Avoid_: All folders by default

**Message Identity**:
The local identity of an imported email, based primarily on IMAP account, **Sync Folder**, `UIDVALIDITY`, and `UID`.
_Avoid_: Message-ID-only identity, content-hash identity

**Sync Cursor**:
The per-**Sync Folder** high-water mark based on `UIDVALIDITY` and the latest processed `UID`.
_Avoid_: Repeated backfill scan

**Imported Message**:
A locally stored email body and metadata identified by one **Message Identity**.
_Avoid_: Per-feed email copy

**Orphan Message**:
An **Imported Message** that is no longer linked by any **Feed Item**.
_Avoid_: Deleted feed item

## Relationships

- The **Admin Panel** manages per-feed **IMAP Accounts** and **Feed Rules**
- The **Admin Panel** can trigger **Manual Sync** for a **Feed Rule**
- The **Admin Panel**, backend API, and **Feed Endpoints** share one **Public Origin** in production
- The **Public Origin** uses one **URL Namespace**
- **Runtime Configuration** does not contain **Feed Rules**
- An **Admin Token** creates an **Admin Session**
- A **Secret Key** encrypts stored **IMAP Account** credentials
- The **Admin Panel** requires an **Admin Session**
- An **Admin Session** has one **Session Expiry**
- Own New Newsletter can sync one or more **Feed Rules**
- A saved **IMAP Account** must be a **Verified IMAP Account**
- A **Feed Rule** has exactly one **IMAP Account**
- A **Feed Rule** has one or more **Sync Folders**
- Multiple **Feed Rules** with identical **IMAP Account** and **Sync Folders** can share one **Mailbox Sync Group**
- A **Sender Filter** is evaluated against email headers such as `From`, `Sender`, `Send`, `Reply-To`, and `Return-Path`
- A **Feed Rule** has exactly one **Sender Filter**
- A **Feed Rule** is an **Independent Feed Rule**
- A **Rule Edit** preserves existing **Feed Items**
- A proposed **Feed Rule** can be checked with one **Rule Preview**
- A **Feed Rule** produces exactly one **RSS Feed**
- A **Feed Publish** updates one **Local Feed File**
- An **RSS Feed** has exactly one **Feed Title**
- An **RSS Feed** is published as exactly one **Local Feed File**
- An **RSS Feed** can be exposed through one or more **Feed Endpoints**
- A **Feed Endpoint** is a **Random Feed URL**
- An **RSS Feed** contains zero or more **Feed Items**
- An **RSS Feed** applies one **Feed Retention** policy
- An **RSS Feed** uses one **Feed Order**
- A **Feed Item** has exactly one **Item GUID**
- A **Feed Item** has exactly one **Item Title**
- A **Feed Item** may have one **Item Author**
- A **Feed Item** has exactly one **Item Published Time**
- A **Feed Item** has exactly one **Item Summary**
- A **Feed Item** is rendered through exactly one **Body Mode** per subscription request
- A **Feed Item** may reference **Remote Assets** from the original email body
- A **Feed Item** can become an **Archived Feed Item**
- A **Backend Scheduler** runs in one **Single Backend Instance**
- A **Sync Lock** belongs to one **Feed Rule**
- A **Read-only Sync** leaves the source mailbox unchanged
- A **Read-only Sync** is triggered by the **Backend Scheduler** according to a **Sync Schedule**
- A **Read-only Sync** updates **Sync Status**
- A **Read-only Sync** emits **Private Logs**
- A **Read-only Sync** reads one or more **Sync Folders**
- A **Feed Rule** has one **Backfill Window** for its first import
- A **Message Identity** belongs to exactly one **Sync Folder**
- A **Sync Folder** has one **Sync Cursor** after initial backfill
- An **Imported Message** has exactly one **Message Identity**
- An **Imported Message** can produce **Feed Items** in one or more **RSS Feeds**
- A **Feed Item** links exactly one **Imported Message** to exactly one **RSS Feed**
- **Feed Retention** excludes old **Archived Feed Items** from the published **RSS Feed**
- An **Orphan Message** is eligible for cleanup when its owning feed is deleted

## Example dialogue

> **Dev:** "Does the **Sender Filter** mean the exact SMTP envelope sender?"
> **Domain expert:** "No - it checks source headers such as `From`, `Sender`, `Send`, `Reply-To`, and `Return-Path` with lowercase substring matching."
> **Dev:** "Can I filter by a display name instead of an email address?"
> **Domain expert:** "Yes - **Sender Filter** matching is lowercased containment against the raw source header values."
> **Dev:** "Do we add a new feed by editing the configuration file?"
> **Domain expert:** "No - use the **Admin Panel**; **Runtime Configuration** only contains startup-level settings and secrets."
> **Dev:** "Can an administrator test a feed without waiting for the schedule?"
> **Domain expert:** "Yes - use **Manual Sync** for that **Feed Rule**."
> **Dev:** "If that feed shares a **Mailbox Sync Group**, does manual sync update every feed in the group?"
> **Domain expert:** "No - **Manual Sync** only publishes the selected **Feed Rule**."
> **Dev:** "Does **Manual Sync** re-import historical mail?"
> **Domain expert:** "No - it imports new messages without rerunning the **Backfill Window**."
> **Dev:** "What if scheduled sync is already running for the same feed?"
> **Domain expert:** "The **Sync Lock** skips the duplicate trigger instead of running or queueing another sync."
> **Dev:** "Are the admin UI and FastAPI API deployed on different public origins?"
> **Domain expert:** "No - they can run as separate services, but production exposes them through one **Public Origin**."
> **Dev:** "Can feed URLs live under `/api`?"
> **Domain expert:** "No - the **URL Namespace** keeps admin APIs under `/api` and random feed URLs under `/f/{random}.xml`."
> **Dev:** "Can the RSS URL use the **Admin Token**?"
> **Domain expert:** "No - the **Admin Token** only creates an **Admin Session**; RSS is read through a **Random Feed URL** without an additional token parameter."
> **Dev:** "Can we use the **Admin Token** to encrypt IMAP passwords?"
> **Domain expert:** "No - use a separate **Secret Key** so login rotation and credential encryption remain separate."
> **Dev:** "Does admin login last forever on a trusted personal machine?"
> **Domain expert:** "No - each **Admin Session** has a **Session Expiry**, defaulting to 30 days."
> **Dev:** "Does an **IMAP Account** mean an app login?"
> **Domain expert:** "No - it is the mailbox connection that **Read-only Sync** reads from."
> **Dev:** "Can an unreachable mailbox configuration be saved for later?"
> **Domain expert:** "No - a saved **IMAP Account** must be a **Verified IMAP Account**."
> **Dev:** "If one IMAP mailbox receives newsletters for two aliases, do we make one combined feed?"
> **Domain expert:** "No - each **Feed Rule** maps one sender/source filter to one **RSS Feed**."
> **Dev:** "Must a new **Feed Rule** match existing mail before it can be saved?"
> **Domain expert:** "No - show a **Rule Preview**, but allow rules for future newsletters."
> **Dev:** "If the administrator edits the sender filter, do old items disappear?"
> **Domain expert:** "No - a **Rule Edit** keeps existing **Feed Items** and affects future sync only."
> **Dev:** "If one email matches two **Feed Rules**, does the first rule consume it?"
> **Domain expert:** "No - every **Independent Feed Rule** receives all of its matching emails."
> **Dev:** "If two feeds use the same mailbox credentials, do they share one account configuration?"
> **Domain expert:** "No - each **Feed Rule** carries its own **IMAP Account**, **Sync Folders**, and **Sender Filter**."
> **Dev:** "Does that mean we log into the same mailbox once for every feed?"
> **Domain expert:** "No - the UI stays feed-scoped, but the synchronizer may use a **Mailbox Sync Group** to scan identical mailbox sources once."
> **Dev:** "After importing an email, should we mark it as read?"
> **Domain expert:** "No - **Read-only Sync** must not modify the mailbox."
> **Dev:** "Does the app need to hold an IMAP IDLE connection open?"
> **Domain expert:** "No - **Read-only Sync** runs on a configurable **Sync Schedule**."
> **Dev:** "Do users need to configure cron for sync?"
> **Domain expert:** "No - the **Backend Scheduler** in the FastAPI process triggers sync."
> **Dev:** "Can we run two backend replicas for high availability?"
> **Domain expert:** "No - the first version assumes a **Single Backend Instance** to avoid duplicate synchronization."
> **Dev:** "If sync fails, is that only visible in logs?"
> **Domain expert:** "No - **Sync Status** records the latest result and error summary for the admin panel."
> **Dev:** "Can logs include message bodies or full feed URLs for debugging?"
> **Domain expert:** "No - logs are **Private Logs** with sensitive values omitted or redacted."
> **Dev:** "On first run, should we import every matching historical email?"
> **Domain expert:** "No - the **Backfill Window** decides how far back the first import looks."
> **Dev:** "Can the administrator rerun the **Backfill Window** from the UI?"
> **Domain expert:** "No - first version does not provide a rebuild or re-backfill operation."
> **Dev:** "Should we scan every IMAP folder so the user does not configure anything?"
> **Domain expert:** "No - default to `INBOX`, and let the user configure additional **Sync Folders** when needed."
> **Dev:** "Can we use `Message-ID` as the only imported-email key?"
> **Domain expert:** "No - use **Message Identity** from IMAP metadata first, with `Message-ID` only as auxiliary duplicate evidence."
> **Dev:** "After pruning old feed items, do we delete the imported message body?"
> **Domain expert:** "No - **Feed Retention** turns old entries into **Archived Feed Items** that stay linked to their **Imported Messages**."
> **Dev:** "If one email appears in two feeds, do we store two copies of the body?"
> **Domain expert:** "No - one **Imported Message** can produce **Feed Items** in multiple **RSS Feeds**."
> **Dev:** "When deleting one feed, do we delete shared message bodies used by another feed?"
> **Domain expert:** "No - delete that feed's **Feed Items** and clean up only **Orphan Messages**."
> **Dev:** "Should the RSS `description` contain the whole newsletter?"
> **Domain expert:** "No - a **Feed Item** uses `description` for the summary and `content:encoded` for the full body."
> **Dev:** "Can RSS `guid` use the email `Message-ID`?"
> **Domain expert:** "No - **Item GUID** is derived from the local **Feed Item** identity so it is stable per feed."
> **Dev:** "Should the feed title default to the sender address?"
> **Domain expert:** "No - the administrator chooses a **Feed Title**; each **Item Title** comes from the email subject."
> **Dev:** "Is the **IMAP Account** the RSS item author?"
> **Domain expert:** "No - **Item Author** comes from the email `From` header."
> **Dev:** "Should backfilled items all use the first sync time?"
> **Domain expert:** "No - **Item Published Time** comes from the email `Date` header when possible."
> **Dev:** "Should the feed show items in the order we imported them?"
> **Domain expert:** "No - **Feed Order** sorts by descending **Item Published Time**."
> **Dev:** "Do we keep every imported item forever in the RSS file?"
> **Domain expert:** "No - **Feed Retention** keeps the published feed bounded by a configurable item count."
> **Dev:** "Do we trust the sender's plain-text part as the summary?"
> **Domain expert:** "No - the **Item Summary** is generated from the normalized body so every item behaves consistently, defaulting to 280 characters."
> **Dev:** "Does choosing raw HTML change how we import the email?"
> **Domain expert:** "No - **Body Mode** is a subscription rendering choice; the default feed renders sanitized HTML, and `?body=raw` renders original HTML."
> **Dev:** "Do we store newsletter attachments as RSS enclosures?"
> **Domain expert:** "No - MVP keeps existing **Remote Assets** in the body and ignores attachments and `cid:` inline assets."
> **Dev:** "Is the **Local Feed File** also where we track imported IMAP UIDs?"
> **Domain expert:** "No - the **Local Feed File** is the published RSS XML, not the synchronization state."
> **Dev:** "Is the feed XML generated only when a feed reader requests it?"
> **Domain expert:** "No - **Feed Publish** rewrites the **Local Feed File** after imports."
> **Dev:** "Do feed readers subscribe directly to files only?"
> **Domain expert:** "No - **Local Feed Files** are also served through **Feed Endpoints** for normal RSS subscription URLs."

## Flagged ambiguities

- "筛选收件人" was corrected to **Sender Filter** based on source headers, not recipient-like delivery headers.
- "发件来源匹配" lowercases both sides and uses substring containment; plus aliases are not normalized.
- "用户提供IMAP相关凭据" is resolved as configuring a per-feed **IMAP Account** through the **Admin Panel**, not creating an application user account.
- "保存 IMAP 账号" means saving a **Verified IMAP Account**, not merely storing typed fields.
- "配置文件" is not the source of truth for RSS/feed configuration; **Runtime Configuration** comes from environment variables or `.env`.
- "配置备份/迁移" is file-level backup of SQLite, local feed files, and `.env`/Secret Key; UI import/export is out of first-version scope.
- "Cloudflare Worker 支持" is out of first-version scope and does not shape the initial architecture.
- "第一版 Admin Panel" includes feed CRUD, rule preview, sync status, random RSS URL display, and **Manual Sync**.
- "手动同步" affects the selected **Feed Rule**, not every feed in the same **Mailbox Sync Group**.
- "手动同步" imports new messages only; historical backfill is not rerun by default.
- "同步并发" is prevented per **Feed Rule** with a **Sync Lock**; duplicate triggers are skipped.
- "前后端独立服务" means separate internal services, not cross-origin production access.
- "URL 路径" is resolved as `/admin` for the **Admin Panel**, `/api` for management APIs, and `/f/{random}.xml` for **Random Feed URLs**.
- "管理员密码token" is resolved as **Admin Token** used for login, not as a feed-reading secret.
- "多管理员/用户管理" is out of first-version scope; there is one **Admin Token**.
- "IMAP 密码加密" uses a separate **Secret Key**, not the **Admin Token**.
- "RSS feed的访问不需要token" is resolved as **Random Feed URL** access without an additional feed token.
- "RSS订阅" is intentionally **RSS Feed** for this project; the reference project's Atom feed format is not the default terminology here.
- Current MVP scope: **Feed Rules** support sender/source-based filtering.
- "发件来源规则" is feed-scoped; each **Feed Rule** carries its own mailbox credentials, **Sync Folders**, and **Sender Filter**.
- "编辑 Feed Rule" preserves existing **Feed Items** and does not rebuild history.
- "启用/禁用 Feed" is out of first-version scope; feed lifecycle is create, edit, delete, and sync.
- "重复邮箱" is optimized internally with **Mailbox Sync Groups**, without making shared account configuration visible in the product model.
- "多个 Feed 之间相互独立" means **Independent Feed Rules**; matching one feed does not remove the email from another feed.
- "规则预览" helps validate **Sender Filter** behavior but does not require an existing matched email.
- "已处理" is local processing state only; it must not imply mailbox flags, folder moves, or deletion.
- "收到" does not imply realtime push; imports happen on the configured **Sync Schedule**.
- "后台同步" is owned by the **Backend Scheduler** in the FastAPI process for the first version.
- "部署多个后端实例" is out of first-version scope; use one **Single Backend Instance** per database.
- "同步失败" is visible as **Sync Status**, not only as process logs.
- "日志" means **Private Logs**; do not log email bodies, passwords, full email addresses, or full **Random Feed URLs**.
- "IMAP收到的邮件" was resolved as messages in configured **Sync Folders**, not every folder in the account.
- "首次导入" is bounded by a **Backfill Window**, not by the mailbox's full history.
- "重建 Feed" or "重新回溯" is out of first-version Admin Panel scope.
- "同一封邮件" is resolved through **Message Identity**, not by trusting `Message-ID` alone.
- "后续同步" uses **Sync Cursors**, not repeated backfill-window scans.
- "多 Feed 命中" stores one **Imported Message** and relates it to multiple **Feed Items**, not duplicate message bodies.
- "删除 Feed" removes feed associations first; only **Orphan Messages** are removed from local message storage.
- "保留策略淘汰" archives old **Feed Items** instead of deleting their records.
- "正文" in an RSS item means full body in `content:encoded`, not a long `description`.
- "**Feed Item** is the per-feed RSS entry, not the canonical stored email body."
- "RSS guid" is **Item GUID** from local **Feed Item** identity, not email `Message-ID`.
- "标题" is split into administrator-chosen **Feed Title** and email-subject **Item Title**.
- "作者" is **Item Author** from the email `From` header, not the mailbox being synced.
- "发布时间" is **Item Published Time** from the email `Date` header, falling back to import time only when needed.
- "排序" is **Feed Order** by descending **Item Published Time**, not import order.
- "历史" in an RSS feed is bounded by **Feed Retention**, not unlimited mailbox history.
- "摘要" is resolved as an **Item Summary** generated from the normalized body.
- "清洗还是原样" is resolved as **Body Mode**, controlled by the subscription URL rather than by changing mailbox import behavior.
- `?body=raw` is the only first-version URL parameter for raw **Body Mode**; clean sanitized output is the default.
- "正文里的图片" means existing **Remote Assets** only; local attachment and `cid:` asset import are out of MVP scope.
- "放到本地文件里" is resolved as writing **Local Feed Files**, not using RSS XML as the import state store.
- "RSS 文件刷新" happens through **Feed Publish** after import, not request-time generation.
- "RSS 访问" is resolved as both local XML output and an HTTP **Feed Endpoint**, not dynamic-only generation.
