
# RSS Publication Settings PRD

## Problem Statement

当前 Own New Newsletter 只能把 RSS 文件发布在当前后端服务下，复制 RSS URL 时前端还会用浏览器当前 origin 拼接地址。这对想借用 GitHub Pages 或 Cloudflare Pages 托管 RSS 文件的部署方式不够方便：管理员需要一个可在系统设置中配置的 RSS 发布目标，让同步后生成的 RSS 文件自动推送到 GitHub 仓库，并让前端复制正确的外部订阅 URL。

## Solution

在系统设置弹窗中新增 RSS Publishing 设置页。发布目标保持单活：默认发布到当前后端，管理员可以切换为 GitHub 静态发布目标。GitHub 目标配置包括 GitHub 仓库、token、分支、仓库相对目录和 `RSS_PUBLIC_URL`。

启用 GitHub 目标时，后端先验证仓库、已存在分支、token 写权限和目录路径，并首发当前所有 feed 文件；成功后才切换当前发布目标。之后每次 RSS 更新都会自动推送 clean/raw 两个静态文件到 GitHub。复制 RSS URL 时使用后端返回的当前发布目标 URL，而不是前端当前 origin。

## User Stories

1. As an administrator, I want to open RSS publishing settings from system settings, so that I can configure where RSS feeds are publicly served.
2. As an administrator, I want system settings to have separate setting pages, so that feed defaults and RSS publication settings are not mixed together.
3. As an administrator, I want the backend publication target to remain the default, so that existing deployments continue working without new configuration.
4. As an administrator, I want to select GitHub as the active publication target, so that generated RSS files can be served by GitHub Pages or Cloudflare Pages.
5. As an administrator, I want only one active publication target at a time, so that copied RSS URLs have one clear source of truth.
6. As an administrator, I want to enter a GitHub repository as a URL or `owner/repo`, so that setup is flexible but stored configuration is normalized.
7. As an administrator, I want non-GitHub remotes rejected, so that the first version stays focused and predictable.
8. As an administrator, I want to enter a GitHub token in the UI, so that I do not need to edit environment variables for publication setup.
9. As an administrator, I want the GitHub token encrypted at rest, so that the database does not expose repository write credentials.
10. As an administrator, I want the saved GitHub token to be write-only in the UI, so that it is not exposed back to the browser after save.
11. As an administrator, I want to see whether a GitHub token is configured, so that I know whether leaving the token field blank will keep the previous token.
12. As an administrator, I want to configure the GitHub branch, so that feed files can be written to the branch used by my static host.
13. As an administrator, I want the branch to be required to already exist, so that the app does not unexpectedly create repository branches.
14. As an administrator, I want to configure a repository-relative publication directory, so that RSS files do not have to live in the repository root.
15. As an administrator, I want the publication directory to default to `feeds`, so that the default keeps static RSS files grouped.
16. As an administrator, I want an empty publication directory to mean repository root, so that root-level static hosting remains possible.
17. As an administrator, I want invalid directories such as absolute paths or parent traversal rejected, so that publication cannot write outside the intended repo directory.
18. As an administrator, I want to configure `RSS_PUBLIC_URL`, so that copied subscription URLs point at the actual public static hosting base URL.
19. As an administrator, I want copied subscription URLs to append the publication directory to `RSS_PUBLIC_URL` unless the URL already includes it, so that repository paths and public paths stay aligned without duplicated directory segments.
20. As an administrator, I want `RSS_PUBLIC_URL` syntax validated, so that obvious URL mistakes are caught before activation.
21. As an administrator, I do not want activation blocked by CDN availability checks, so that GitHub Pages or Cloudflare Pages propagation delays do not cause false failures.
22. As an administrator, I want enabling GitHub publication to validate repository write readiness, so that misconfigured tokens, repos, branches, or directories fail early.
23. As an administrator, I want enabling GitHub publication to publish all current feeds before switching targets, so that copied URLs do not point to missing files.
24. As an administrator, I want GitHub publication to use the GitHub API, so that the backend does not need local git clones or token-bearing git remotes.
25. As an administrator, I want successful IMAP sync and failed GitHub publication to be reported separately, so that I know whether mailbox import or static delivery failed.
26. As an administrator, I want publication status visible in RSS publishing settings, so that I can diagnose RSS delivery without reading logs.
27. As an administrator, I want the publication overview to show the latest publication result and error, so that I know whether the external RSS target is healthy.
28. As an administrator, I want a Publish all or Retry action in RSS publishing settings, so that I can republish current feeds without rerunning IMAP sync.
29. As an administrator, I want publication retry to avoid changing sync status, so that sync history remains accurate.
30. As an administrator, I want future successful feed publishes to clear or update publication status, so that stale failures do not remain misleading.
31. As an RSS reader user, I want the copied clean RSS URL to use the active publication target, so that subscriptions fetch from the correct host.
32. As an RSS reader user, I want raw RSS subscriptions to work on static hosting, so that raw body mode remains available outside the backend.
33. As an RSS reader user, I want GitHub-hosted clean feeds to use `{slug}.xml`, so that static hosts can serve them directly.
34. As an RSS reader user, I want GitHub-hosted raw feeds to use `{slug}.raw.xml`, so that raw mode does not depend on backend query parameters.
35. As an RSS reader user, I want RSS item links and feed links to use the correct active public URL prefix, so that feed contents are internally consistent.
36. As an administrator, I want feed creation to publish the generated feed to the active publication target, so that newly created feeds are immediately subscribable.
37. As an administrator, I want feed edits to republish the affected feed to the active publication target, so that static RSS reflects metadata and item changes.
38. As an administrator, I want manual sync to publish updated feed files after successful import, so that GitHub-hosted RSS updates automatically.
39. As an administrator, I want scheduled sync to publish updated feed files after successful import, so that external RSS stays fresh without manual work.
40. As an administrator, I want deleting a feed to delete its GitHub static feed files when GitHub is active, so that stale random RSS URLs do not remain publicly reachable.
41. As an administrator, I want backend local feed files to continue being generated, so that the backend target remains available and publication has a local source artifact.
42. As an administrator, I want switching back to backend publication to stop GitHub pushes, so that the active target is the only target receiving new publication work.
43. As an administrator, I want publication failures to avoid exposing GitHub tokens in errors or logs, so that troubleshooting does not leak secrets.
44. As an administrator, I want private logs to redact publication credentials and full random feed URLs, so that RSS publication follows the existing privacy boundary.
45. As a deployer, I want GitHub Pages and Cloudflare Pages to be treated as static hosting targets, so that this feature does not require Cloudflare Worker runtime support.
46. As a developer, I want publication logic encapsulated behind a small target interface, so that backend and GitHub publication can be tested independently.
47. As a developer, I want GitHub API behavior hidden behind a dedicated client, so that repo validation, file upsert, and file deletion can be tested with fake HTTP responses.
48. As a developer, I want URL construction centralized, so that frontend copy buttons, API feed responses, and RSS feed links do not drift apart.

## Implementation Decisions

- Add Feed Publication Settings as a separate page under the existing system settings modal, while preserving current feed-default Settings behavior.
- Keep publication target single-active: `backend` is default; `github` is optional and external.
- Store global publication settings in backend-managed persistence, including active target, GitHub repository, branch, directory, public URL prefix, token presence, and status metadata.
- Encrypt GitHub publication tokens with the same secret-key mechanism already used for stored IMAP credentials.
- Never return the GitHub token from API responses; return only a token-present flag.
- Normalize GitHub repository input to `owner/repo`; accept common GitHub URL input but reject arbitrary git remotes.
- Validate GitHub branch existence instead of auto-creating branches.
- Validate publication directory as a repository-relative path; default to `feeds`; allow empty only as repository root.
- Validate `RSS_PUBLIC_URL` as an HTTP or HTTPS base URL and strip trailing slashes for URL construction.
- Build GitHub static feed URLs from `RSS_PUBLIC_URL`, the publication directory when non-empty, and the static file name; avoid appending the directory if `RSS_PUBLIC_URL` already ends with that same path.
- Do not attempt to verify public CDN availability during activation; activation proves GitHub write readiness and initial publication success.
- Use GitHub API for publication rather than `git` CLI.
- Add a deep `PublicationTarget` abstraction with operations for validating a target, publishing one feed, publishing all feeds, and deleting one feed's static files.
- Add a deep `GitHubPublicationClient` module that encapsulates GitHub API calls for branch lookup, file upsert, commit creation, and file deletion.
- Extend the current feed publisher so local RSS rendering remains the source of clean/raw XML output and external targets publish those generated artifacts.
- Preserve backend file generation even when GitHub is active.
- Use separate static files for body modes on GitHub: clean as `{slug}.xml`, raw as `{slug}.raw.xml`.
- Keep backend raw mode as `?body=raw` for existing backend endpoint behavior.
- Add publication status separate from sync status, including last started, last finished, status, error, and affected feed information where useful.
- Keep IMAP sync success independent from publication failure; a GitHub push failure must not mark mailbox sync as failed.
- Add a publication retry endpoint that republishes current feed files without running IMAP sync.
- Add RSS publication API contracts for reading settings, updating settings, activating GitHub publication, switching back to backend, and retrying publication.
- Update feed serialization so `feed_url` and `raw_feed_url` are generated from the active publication target.
- Update frontend copy behavior to use API-provided `feed_url` instead of building a URL from `window.location.origin`.
- Delete GitHub static feed files when a feed is deleted and GitHub is the active publication target.
- Keep publication overview in the RSS Publishing settings page instead of adding a feed-list publication status column in the first version.
- Keep existing Admin Session protection for all publication settings and retry APIs.

## Testing Decisions

- Good tests should verify externally visible behavior and stable contracts: API responses, persisted settings, generated URLs, GitHub API interactions, status separation, and file lifecycle.
- Tests should avoid asserting private helper structure.
- Add focused tests for publication settings validation: repository normalization, branch requirement, directory normalization, URL validation, token write-only behavior, and encrypted token persistence.
- Add tests for active target URL construction: backend clean/raw URLs, GitHub clean/raw URLs, trailing slash handling, directory-root handling, and API feed serialization.
- Add tests for GitHub publication client behavior using fake HTTP responses: branch lookup, create/update file, delete file, permission errors, missing repo, missing branch, and redacted error messages.
- Add tests for publication activation: invalid target does not switch active target, failed initial publish does not switch active target, successful initial publish switches target and records status.
- Add tests for feed lifecycle publication: create publishes, edit republishes, manual sync publishes after successful import, scheduled sync publishes after successful import, delete removes external static files.
- Add tests proving IMAP sync status and publication status are separated when external publication fails after successful import.
- Add tests for publication retry: it republishes existing feed files, does not fetch IMAP, does not alter sync cursors, and updates publication status.
- Add frontend behavior tests where feasible for settings tab switching, token-present display, validation/error rendering, retry action, and copy button using API-provided URLs.
- Reuse existing backend testing patterns for API settings, store persistence, feed publisher, sync engine, and scheduler behavior.
- Reuse existing fake-source patterns for sync tests and add fake publication targets to avoid real network calls.
- Avoid tests that require real GitHub credentials, real GitHub repositories, GitHub Pages propagation, or Cloudflare Pages availability.

## Out of Scope

- Multiple simultaneous publication targets.
- Arbitrary git remotes, SSH remotes, or local git repository publishing.
- Automatic GitHub branch creation.
- Public availability probing for GitHub Pages or Cloudflare Pages.
- Cloudflare Worker runtime support.
- Per-feed publication target selection.
- Feed-list publication status columns in the first version.
- UI import/export of publication settings.
- Multi-admin permissions or role-based control over publication settings.
- Atom output.
- Changing IMAP sync semantics, backfill semantics, retention behavior, or RSS item rendering beyond publication URL/link construction.

## Further Notes

This feature should be implemented with TDD around the deep modules first: publication settings validation, URL construction, GitHub API publication, and sync-vs-publication status separation. The highest-risk areas are token handling, avoiding accidental target activation before files exist, and preventing frontend/backend URL drift.
