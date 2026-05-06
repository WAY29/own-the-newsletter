import { useCallback, useEffect, useState } from "react";
import {
  api,
  type ActivityLogEntry,
  type ActivityLogParams,
  type ActivityOperation,
  type ActivityStatus,
  type ActivityTrigger,
  type Feed,
  type FeedListPagination
} from "../api";
import { Button, Select, StatusBadge } from "../components/ui";
import { ChevronLeftIcon, ChevronRightIcon, ChevronsLeftIcon, ChevronsRightIcon, RefreshIcon } from "../components/icons";

const PAGE_SIZE = 50;

const DEFAULT_PAGINATION: FeedListPagination = {
  page: 1,
  page_size: PAGE_SIZE,
  total: 0,
  total_pages: 1,
  has_next: false,
  has_previous: false
};

const OPERATION_OPTIONS: Array<{ value: ActivityOperation; label: string }> = [
  { value: "sync", label: "Sync" },
  { value: "publish", label: "Publish" },
];

const STATUS_OPTIONS: Array<{ value: ActivityStatus; label: string }> = [
  { value: "success", label: "Success" },
  { value: "failed", label: "Failed" },
  { value: "skipped", label: "Skipped" },
];

const TRIGGER_OPTIONS: Array<{ value: ActivityTrigger; label: string }> = [
  { value: "manual_sync", label: "Manual sync" },
  { value: "scheduled_sync", label: "Scheduled sync" },
  { value: "initial_sync", label: "Initial sync" },
  { value: "publication_retry", label: "Publication retry" },
  { value: "publication_activation", label: "Publication activation" },
  { value: "feed_change_publication", label: "Feed change" },
];

type Filters = {
  operation_type: ActivityOperation | "";
  status: ActivityStatus | "";
  trigger: ActivityTrigger | "";
  feed_id: number | "";
};

function buildPageNumbers(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 1) return [];
  const pages: (number | "ellipsis")[] = [1];
  const left = Math.max(2, current - 3);
  const right = Math.min(total - 1, current + 3);
  if (left > 2) pages.push("ellipsis");
  for (let i = left; i <= right; i++) pages.push(i);
  if (right < total - 1) pages.push("ellipsis");
  if (total > 1) pages.push(total);
  return pages;
}

export default function LogsPage() {
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [pagination, setPagination] = useState<FeedListPagination>(DEFAULT_PAGINATION);
  const [filters, setFilters] = useState<Filters>({
    operation_type: "",
    status: "",
    trigger: "",
    feed_id: "",
  });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(() => new Set());

  const refresh = useCallback(async () => {
    try {
      const params: ActivityLogParams = {
        page,
        page_size: PAGE_SIZE,
        ...filters,
      };
      const result = await api.listActivityLogs(params);
      if (result.pagination.total > 0 && result.pagination.page > result.pagination.total_pages) {
        setPage(result.pagination.total_pages);
        return;
      }
      setEntries(result.entries);
      setPagination(result.pagination);
      setListError("");
    } catch {
      setListError("Failed to load activity logs.");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    api.listFeeds({ page: 1, page_size: 100, sort_by: "title", sort_dir: "asc" })
      .then((result) => setFeeds(result.feeds))
      .catch(() => setFeeds([]));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = window.setInterval(() => {
      refresh();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [autoRefresh, refresh]);

  function patchFilter(update: Partial<Filters>) {
    setFilters((current) => ({ ...current, ...update }));
    setPage(1);
  }

  function clearFilters() {
    setFilters({ operation_type: "", status: "", trigger: "", feed_id: "" });
    setPage(1);
  }

  function toggleExpanded(id: number) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const rangeStart = pagination.total === 0 || entries.length === 0 ? 0 : (pagination.page - 1) * pagination.page_size + 1;
  const rangeEnd = entries.length === 0 ? 0 : Math.min(pagination.total, rangeStart + entries.length - 1);
  const pageNumbers = buildPageNumbers(pagination.page, pagination.total_pages);
  const hasFilters = Boolean(filters.operation_type || filters.status || filters.trigger || filters.feed_id);

  if (loading) {
    return (
      <div className="app-content">
        <p style={{ color: "var(--text-tertiary)", padding: "32px 0" }}>Loading logs...</p>
      </div>
    );
  }

  return (
    <div className="app-content logs-content">
      <div className="page-header">
        <div>
          <h1>Logs</h1>
          <div className="page-header-sub">
            Completed sync and publication history
          </div>
        </div>
        <div className="log-header-actions">
          <Button variant="ghost" onClick={() => setAutoRefresh((value) => !value)}>
            Auto-refresh {autoRefresh ? "on" : "off"}
          </Button>
          <Button onClick={refresh}>
            <RefreshIcon /> Refresh
          </Button>
        </div>
      </div>

      <div className="log-filters card">
        <label>
          <span>Operation</span>
          <Select
            value={filters.operation_type}
            onChange={(event) => patchFilter({ operation_type: event.target.value as ActivityOperation | "" })}
          >
            <option value="">All operations</option>
            {OPERATION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </Select>
        </label>
        <label>
          <span>Status</span>
          <Select
            value={filters.status}
            onChange={(event) => patchFilter({ status: event.target.value as ActivityStatus | "" })}
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </Select>
        </label>
        <label>
          <span>Trigger</span>
          <Select
            value={filters.trigger}
            onChange={(event) => patchFilter({ trigger: event.target.value as ActivityTrigger | "" })}
          >
            <option value="">All triggers</option>
            {TRIGGER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </Select>
        </label>
        <label>
          <span>Feed</span>
          <Select
            value={filters.feed_id}
            onChange={(event) => patchFilter({ feed_id: event.target.value ? Number(event.target.value) : "" })}
          >
            <option value="">All feeds</option>
            {feeds.map((feed) => (
              <option key={feed.id} value={feed.id}>{feed.title}</option>
            ))}
          </Select>
        </label>
        <Button variant="ghost" disabled={!hasFilters} onClick={clearFilters}>Clear</Button>
      </div>

      <div className="card log-card">
        {listError ? <div className="feed-list-error error-msg">{listError}</div> : null}
        {entries.length === 0 ? (
          <div className="empty-state">
            <h3>{pagination.total === 0 ? "No completed operations yet" : "No logs on this page"}</h3>
            <p>
              {pagination.total === 0
                ? "Completed sync and publication outcomes will appear here after work finishes."
                : "Try the previous page or adjust the filters."}
            </p>
          </div>
        ) : (
          <div className="log-table-wrap">
            <table className="log-table">
              <thead>
                <tr>
                  <th>Completed</th>
                  <th>Operation</th>
                  <th>Trigger</th>
                  <th>Feed</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Counts</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => {
                  const expanded = expandedIds.has(entry.id);
                  const hasDetail = Boolean(entry.error_detail && entry.error_detail !== entry.error_summary);
                  return (
                    <tr key={entry.id}>
                      <td className="log-time">{formatDateTime(entry.completed_at)}</td>
                      <td>{operationLabel(entry.operation_type)}</td>
                      <td>{triggerLabel(entry.trigger)}</td>
                      <td className="log-feed-cell">{feedLabel(entry)}</td>
                      <td><StatusBadge status={entry.status} /></td>
                      <td className="log-duration">{formatDuration(entry.duration_ms)}</td>
                      <td className="log-counts">{countsLabel(entry)}</td>
                      <td className="log-error-cell">
                        {entry.error_summary ? (
                          <>
                            <span>{entry.error_summary}</span>
                            {hasDetail ? (
                              <button className="log-detail-toggle" onClick={() => toggleExpanded(entry.id)}>
                                {expanded ? "Hide detail" : "Show detail"}
                              </button>
                            ) : null}
                            {expanded && entry.error_detail ? <pre>{entry.error_detail}</pre> : null}
                          </>
                        ) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {pagination.total > 0 ? (
          <div className="pagination-bar">
            <span className="pagination-summary">
              Showing {rangeStart}-{rangeEnd} of {pagination.total}
            </span>
            <div className="pagination-pages">
              <button
                className="page-btn page-btn-nav"
                disabled={!pagination.has_previous}
                onClick={() => setPage(1)}
                aria-label="First page"
              >
                <ChevronsLeftIcon />
              </button>
              <button
                className="page-btn page-btn-nav"
                disabled={!pagination.has_previous}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                aria-label="Previous page"
              >
                <ChevronLeftIcon />
              </button>
              {pageNumbers.map((item, index) =>
                item === "ellipsis" ? (
                  <span key={`ellipsis-${index}`} className="page-ellipsis">...</span>
                ) : (
                  <button
                    key={item}
                    className={`page-btn page-btn-num ${item === pagination.page ? "page-btn-current" : ""}`}
                    onClick={() => setPage(item)}
                    aria-current={item === pagination.page ? "page" : undefined}
                  >
                    {item}
                  </button>
                )
              )}
              <button
                className="page-btn page-btn-nav"
                disabled={!pagination.has_next}
                onClick={() => setPage((current) => current + 1)}
                aria-label="Next page"
              >
                <ChevronRightIcon />
              </button>
              <button
                className="page-btn page-btn-nav"
                disabled={!pagination.has_next}
                onClick={() => setPage(pagination.total_pages)}
                aria-label="Last page"
              >
                <ChevronsRightIcon />
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function operationLabel(value: ActivityOperation): string {
  return value === "sync" ? "Sync" : "Publish";
}

function triggerLabel(value: ActivityTrigger): string {
  return TRIGGER_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

function feedLabel(entry: ActivityLogEntry): string {
  if (entry.feed_title) return entry.feed_title;
  if (entry.feed_id) return `Feed #${entry.feed_id}`;
  if (entry.operation_type === "publish" && entry.feed_count !== null) return "All feeds";
  return "—";
}

function countsLabel(entry: ActivityLogEntry): string {
  if (entry.operation_type === "sync") {
    return `${entry.imported_count ?? 0} imported, ${entry.skipped_count ?? 0} skipped`;
  }
  const target = entry.publication_target ? `${entry.publication_target}, ` : "";
  return `${target}${entry.feed_count ?? 0} feeds, ${entry.file_count ?? 0} files`;
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString();
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)}s`;
}
