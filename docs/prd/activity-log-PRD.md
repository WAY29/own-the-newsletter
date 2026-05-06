# Activity Log PRD

## Problem Statement

当前 Own New Newsletter 登录后默认进入 Feeds 页面，管理员可以看到每个 Feed Rule 的最新 Sync Status，也可以在 Feed Publication Settings 中看到最新 Publication Status，但缺少一个可回看历史操作的 Logs 页面。

这导致管理员排查问题时只能看到“最后一次状态”，无法方便地区分定时 sync、手动 sync、创建 feed 后的初次 sync、feed 变更触发的 publish、publication retry、publication activation、删除 feed 时的 publication delete 等历史行为。尤其是 sync 成功但 publish 失败时，单一状态或进程日志都不足以提供清晰、脱敏、可分页、可筛选的管理视图。

## Solution

在 Admin Panel 中新增 Logs 页面，并在登录态顶部导航中提供 Feeds / Logs 切换。登录后默认仍进入 Feeds 页面，管理员可以通过顶部导航进入 Logs 页面。

Logs 页面展示持久化的 Activity Log，而不是读取后端进程日志。Activity Log 只记录 completed operation，覆盖 Read-only Sync 和 publication 操作。Sync 和 publication 即使来自同一次用户或调度链路，也分别记录为独立条目，以保持 Sync Status 和 Publication Status 的语义分离。运行中的操作继续通过现有 Sync Status 和 Publication Status 展示，Logs 页面不承担实时任务面板职责。

Activity Log 遵守 Private Log 边界，不记录邮件正文、密码、完整邮箱地址、完整 Random Feed URL 或其他敏感值。第一版保留最近 1000 条记录，默认 newest-first、每页 50 条、不过滤展示。页面支持按 operation type、status、trigger、feed 筛选，支持手动刷新和可选 10 秒 auto-refresh。错误在列表中显示脱敏 summary，长错误可展开查看脱敏 detail。

## User Stories

1. As an administrator, I want to switch from Feeds to Logs in the authenticated Admin Panel, so that I can review sync and publication history without leaving the app.
2. As an administrator, I want Feeds to remain the default page after login, so that the existing feed-management workflow does not change.
3. As an administrator, I want Feeds and Logs to appear in the top navigation, so that page switching is visible without adding a bottom tab bar.
4. As an administrator, I want Logs to show Activity Log entries rather than raw backend process logs, so that the view is stable, structured, and safe for the Admin Panel.
5. As an administrator, I want Logs to include scheduled Read-only Sync operations, so that I can confirm background sync is running.
6. As an administrator, I want Logs to include manually triggered sync operations, so that I can see the result of actions I started from the UI.
7. As an administrator, I want Logs to include initial sync after creating a Feed Rule, so that I can distinguish first import behavior from later scheduled sync.
8. As an administrator, I want Logs to include Feed Publish operations, so that I can see when RSS files were regenerated or delivered.
9. As an administrator, I want Logs to include backend publication outcomes, so that local feed-file publication is visible even without GitHub.
10. As an administrator, I want Logs to include GitHub publication outcomes, so that external static delivery can be diagnosed.
11. As an administrator, I want Logs to include Publication Retry outcomes, so that retry attempts are visible separately from sync.
12. As an administrator, I want Logs to include Publication Activation outcomes, so that enabling an external publication target leaves a clear history.
13. As an administrator, I want Logs to include publication delete outcomes when a feed is deleted, so that stale-file cleanup can be audited.
14. As an administrator, I want sync and publish to be separate log entries, so that a successful sync and failed publish do not collapse into one misleading result.
15. As an administrator, I want each Activity Log entry to identify its operation type, so that I can distinguish sync from publish.
16. As an administrator, I want each Activity Log entry to identify its trigger, so that I know whether it was manual, scheduled, initial, retry, activation, or feed-change work.
17. As an administrator, I want each Activity Log entry to include the affected feed when applicable, so that I can troubleshoot a specific RSS Feed.
18. As an administrator, I want feed title context to remain visible after a Feed Rule is deleted, so that historical entries still explain which feed was affected.
19. As an administrator, I want publication entries that affect all feeds to show aggregate context, so that bulk publish attempts are understandable.
20. As an administrator, I want sync entries to show imported and skipped counts, so that I can tell whether the sync found useful messages.
21. As an administrator, I want publish entries to show feed and file counts, so that I can tell how much RSS output was published.
22. As an administrator, I want publish entries to show the active Publication Target, so that I know whether work was for backend or GitHub.
23. As an administrator, I want entries to show status, so that I can quickly scan for success, failed, or skipped operations.
24. As an administrator, I want entries to show completion time, so that I can correlate activity with expected schedules or manual actions.
25. As an administrator, I want entries to show duration, so that unusually slow sync or publish work is visible.
26. As an administrator, I want failed entries to show a redacted error summary, so that I can diagnose credentials, folders, connectivity, or publication issues.
27. As an administrator, I want long errors to be expandable, so that the table stays readable while still preserving useful details.
28. As an administrator, I want all error details to be redacted, so that troubleshooting does not leak passwords, message bodies, full email addresses, tokens, or full Random Feed URLs.
29. As an administrator, I want Logs to preserve the existing Private Log policy, so that adding a UI page does not weaken privacy boundaries.
30. As an administrator, I want Logs to avoid showing message subjects or bodies by default, so that the page remains operational rather than content-focused.
31. As an administrator, I want Logs to avoid exposing full IMAP usernames or source addresses, so that account details are not unnecessarily revealed.
32. As an administrator, I want Logs to avoid exposing full feed URLs or random slugs, so that RSS access barriers are not displayed in a diagnostic page.
33. As an administrator, I want Logs to default to newest-first ordering, so that the most relevant recent activity appears first.
34. As an administrator, I want Logs to be paginated, so that the page stays fast with long-running installations.
35. As an administrator, I want the default page size to be 50 entries, so that I can see enough context without loading too much data.
36. As an administrator, I want Activity Log retention to keep the most recent 1000 entries, so that SQLite does not grow indefinitely.
37. As an administrator, I want older Activity Log entries to be pruned automatically after new entries are recorded, so that retention does not require manual cleanup.
38. As an administrator, I want to filter by operation type, so that I can inspect only sync or only publish behavior.
39. As an administrator, I want to filter by status, so that I can focus on failed or skipped work.
40. As an administrator, I want to filter by trigger, so that I can compare manual actions against scheduled background work.
41. As an administrator, I want to filter by feed, so that I can isolate one Feed Rule's operational history.
42. As an administrator, I want the default Logs view to be unfiltered, so that I can see the full recent timeline immediately.
43. As an administrator, I want to manually refresh Logs, so that I control when the page reloads.
44. As an administrator, I want an optional auto-refresh toggle, so that I can watch for completed operations while testing a sync or publish workflow.
45. As an administrator, I want auto-refresh to use a 10-second interval, so that updates are timely without excessive polling.
46. As an administrator, I want auto-refresh to show completed entries only, so that Logs remains a completed-history view rather than a live job dashboard.
47. As an administrator, I want running syncs to remain visible through existing feed status indicators, so that Logs does not duplicate current-state UI.
48. As an administrator, I want running publication to remain visible through Publication Status, so that publication settings keep their existing health role.
49. As an administrator, I want failed sync status and failed publish status to remain separate, so that mailbox import and RSS delivery can be diagnosed independently.
50. As an administrator, I want sync success followed by publish failure to produce a success sync entry and a failed publish entry, so that the Activity Log mirrors the domain model.
51. As an administrator, I want scheduled grouped syncs to produce per-feed results where appropriate, so that each affected feed can be filtered and diagnosed.
52. As an administrator, I want skipped duplicate sync triggers to be logged after completion, so that lock contention or already-running sync attempts are visible historically.
53. As an administrator, I want missing or deleted feeds to be handled safely in log entries, so that background or late-arriving results do not break the Logs page.
54. As an administrator, I want Logs to exclude Rule Preview events in the first version, so that the page stays focused on sync and publication history.
55. As an administrator, I want Logs to exclude IMAP validation events in the first version, so that configuration probing does not add noise or privacy complexity.
56. As an administrator, I want Logs to exclude login and logout events in the first version, so that this feature does not become a full audit log.
57. As an administrator, I want Logs to exclude Settings saves in the first version, so that non-sync and non-publish admin operations remain out of scope.
58. As an administrator, I want Logs to exclude full-text search in the first version, so that the privacy and performance model stays simple.
59. As a deployer, I want the Activity Log to be stored with the existing application state, so that backup and restore follow the same SQLite-based workflow.
60. As a developer, I want Activity Log recording behind a small module interface, so that sync and publish code can record outcomes without duplicating schema details.
61. As a developer, I want Activity Log querying behind a stable read interface, so that frontend filters and pagination do not depend on persistence internals.
62. As a developer, I want Activity Log redaction centralized, so that all logged errors and metadata follow the same Private Log policy.
63. As a developer, I want Activity Log tests to use fake sync and publication flows, so that behavior is verified without IMAP, GitHub, or real network calls.
64. As a developer, I want API tests for filters and pagination, so that the Logs page has a stable backend contract.
65. As a developer, I want UI behavior to rely on API-provided log data, so that frontend navigation, filters, refresh, and expansion stay decoupled from sync implementation details.

## Implementation Decisions

- Add a new authenticated Logs page to the Admin Panel.
- Add authenticated top navigation for Feeds and Logs; Feeds remains the default authenticated route.
- Keep Settings and Logout in the existing header action area.
- Use a persistent Activity Log model rather than reading Python logging output, container stdout, or reverse-proxy logs.
- Store Activity Log entries in SQLite alongside existing application state.
- Record only completed operations; do not create running Activity Log entries.
- Continue using Sync Status and Publication Status for current or latest status display.
- Record sync operations and publication operations as separate Activity Log entries, even when one action causes both.
- Support operation type values for sync and publish in the first version.
- Support status values for success, failed, and skipped in the first version.
- Support Activity Trigger values for manual sync, scheduled sync, initial sync, publication retry, publication activation, and feed-change publication.
- Treat publication caused by feed create, feed edit, feed delete, and backend file rewrite after feed change as feed-change publication.
- Treat publication caused by a manual sync as manual sync publication when that distinction is available.
- Treat publication caused by a scheduled sync as scheduled sync publication when that distinction is available.
- Record feed id and feed title snapshot for feed-scoped operations.
- Preserve feed title snapshots after Feed Rule deletion.
- Allow activity entries without a single feed id for all-feed publication operations.
- Record publication target for publish entries.
- Record imported and skipped counts for sync entries.
- Record feed count and file count for publish entries.
- Record completed timestamp and duration for each entry.
- Record a redacted error summary and optional redacted error detail for failed entries.
- Apply the existing sensitive-value redaction policy before persisting Activity Log errors or metadata.
- Avoid persisting email bodies, raw subjects, passwords, tokens, complete email addresses, complete Random Feed URLs, or full random slugs in Activity Log entries.
- Enforce Activity Log Retention by keeping only the most recent 1000 entries after inserting a new entry.
- Add a backend ActivityLogRecorder deep module with a simple interface for recording completed sync and publish outcomes.
- Add a backend ActivityLogQuery deep module with a stable interface for pagination and filters.
- Keep Activity Log persistence details inside the store layer instead of spreading SQL across sync, publication, and API code.
- Extend sync orchestration to pass a precise trigger when sync is manual, scheduled, or initial.
- Extend sync completion handling to record one Activity Log entry per completed feed-level sync result.
- Extend duplicate sync skip handling to record a skipped Activity Log entry after the skip result is known.
- Extend publication flows to record completed publish outcomes for backend and GitHub targets.
- Extend publication retry and activation flows to record publish outcomes without changing Sync Status.
- Extend feed deletion publication handling to record deletion publication outcomes before or while preserving feed title context.
- Keep Rule Preview, feed validation, auth events, Settings saves, and general Admin API requests out of Activity Log scope.
- Add a protected API endpoint for listing Activity Log entries.
- The list API supports page and page-size parameters, with default page size 50.
- The list API supports filters for operation type, status, trigger, and feed.
- The list API returns pagination metadata suitable for frontend controls.
- The list API returns values already redacted for display.
- The list API defaults to newest-first ordering.
- The frontend Logs page loads the default unfiltered newest-first view.
- The frontend Logs page provides operation type, status, trigger, and feed filters.
- The frontend Logs page provides a manual refresh action.
- The frontend Logs page provides an auto-refresh toggle that polls every 10 seconds while enabled.
- The frontend Logs page displays time, operation, trigger, feed, status, duration, counts, and redacted error summary.
- The frontend Logs page supports expanding long redacted errors.
- The frontend does not implement full-text search in the first version.
- The frontend does not display raw process logs, request logs, or debug logs.
- The Activity Log API remains protected by the existing Admin Session model.
- No ADR is required for this feature because the decisions are product and persistence behavior that remain reversible without large architectural lock-in.

## Testing Decisions

- Good tests should verify externally visible behavior and stable contracts rather than internal helper structure.
- Tests should focus on Activity Log entries produced by real sync and publication workflows, API responses, filters, pagination, retention, redaction, and UI behavior.
- Add store-level tests for creating Activity Log entries, preserving feed title snapshots, querying newest-first, filtering, pagination, and retaining only the newest 1000 entries.
- Add ActivityLogRecorder tests for sync success, sync failure, sync skipped, publish success, publish failure, all-feed publication, and feed-scoped publication.
- Add redaction tests proving Activity Log entries do not persist passwords, tokens, full email addresses, full Random Feed URLs, full random slugs, or message bodies.
- Add sync engine tests proving manual sync writes manual sync entries with imported and skipped counts.
- Add sync engine tests proving scheduled sync writes scheduled sync entries.
- Add sync engine tests proving initial sync after feed creation writes initial sync entries.
- Add sync lock tests proving skipped duplicate sync attempts are recorded as skipped completed entries.
- Add publication tests proving backend publish writes publish entries with target and file counts.
- Add publication tests proving GitHub publish writes publish entries with target and file counts.
- Add publication workflow tests proving sync success plus publication failure creates separate success and failed Activity Log entries.
- Add publication retry tests proving retry writes publish entries and does not fetch IMAP or change Sync Status.
- Add publication activation tests proving activation publish attempts are logged and failed activation does not switch the active target.
- Add feed delete publication tests proving deleted feed title context remains available in Activity Log entries.
- Add API tests for authentication requirements on the Logs endpoint.
- Add API tests for default newest-first ordering and default page size.
- Add API tests for operation type, status, trigger, and feed filters.
- Add API tests for pagination metadata.
- Add API tests proving response data is redacted and does not expose sensitive values.
- Add frontend tests where the existing test harness supports them for top navigation, default Logs loading, filters, manual refresh, auto-refresh toggle, and error expansion.
- If no frontend test harness exists for this app, verify frontend behavior through the smallest reliable build and manual browser-level smoke path.
- Reuse existing backend test patterns for auth-protected APIs, settings persistence, sync engine behavior, feed publisher behavior, publication workflows, scheduler behavior, and security redaction.
- Use fake IMAP and fake publication clients in tests; do not require real IMAP accounts, GitHub repositories, network access, or scheduler wall-clock waiting.

## Out of Scope

- Reading or displaying raw backend process logs.
- Reading container stdout, reverse-proxy logs, or host log files.
- Showing running operations as incomplete Activity Log entries.
- Replacing Sync Status or Publication Status with Activity Log.
- Recording Rule Preview operations.
- Recording IMAP validation operations.
- Recording login, logout, session, or auth audit events.
- Recording Settings saves or general Admin API requests.
- Recording full admin audit history.
- Full-text search across log messages.
- Configurable Activity Log retention in the first version.
- Exporting Activity Log entries.
- Clearing Activity Log entries from the UI.
- Displaying message bodies, raw email subjects, complete email addresses, full Random Feed URLs, full random slugs, passwords, tokens, or credentials.
- Adding multi-admin attribution, users, roles, or permissions.
- Adding push-based live updates or WebSocket streaming.
- Changing IMAP sync semantics, backfill semantics, feed retention semantics, or publication target semantics.
- Adding a bottom navigation bar.

## Further Notes

The most important design boundary is that Logs is completed operational history, not a raw log viewer and not a live job monitor. Existing status fields remain the right place for running and latest-health information.

The implementation should start with TDD around the deep modules: ActivityLogRecorder, ActivityLogQuery, retention, and redaction. Once those contracts are stable, wire sync and publication flows into the recorder, then add the API and frontend page.

The highest-risk areas are trigger correctness, duplicate sync skip logging, sync-vs-publish separation, and preserving Private Log redaction before persistence.
