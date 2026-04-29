import { useEffect, useState, useCallback } from "react";
import { api, type Feed, type FeedListPagination, type FeedSortBy, type FeedSortDir } from "../api";
import { Button, StatusBadge } from "../components/ui";
import {
  PlusIcon, PencilIcon, CopyIcon, TrashIcon, CheckIcon, RefreshIcon,
  SortAscIcon, SortDescIcon,
  ChevronLeftIcon, ChevronRightIcon, ChevronsLeftIcon, ChevronsRightIcon
} from "../components/icons";
import FeedEditorModal from "./FeedEditorPage";

function feedUrlForCurrentOrigin(feed: Feed): string {
  return new URL(`/f/${encodeURIComponent(feed.random_slug)}.xml`, window.location.origin).toString();
}

const PAGE_SIZE = 25;

const SORT_COLUMNS: Array<{ key: FeedSortBy; label: string }> = [
  { key: "title", label: "Title" },
  { key: "item_count", label: "Items" },
  { key: "last_sync", label: "Last Sync" },
  { key: "created_at", label: "Created" },
  { key: "updated_at", label: "Updated" },
];

const DEFAULT_PAGINATION: FeedListPagination = {
  page: 1,
  page_size: PAGE_SIZE,
  total: 0,
  total_pages: 1,
  has_next: false,
  has_previous: false
};

function buildPageNumbers(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 1) return [];
  const pages: (number | "ellipsis")[] = [];
  const delta = 3;
  let left = Math.max(2, current - delta);
  let right = Math.min(total - 1, current + delta);

  // Always show page 1
  pages.push(1);

  if (left > 2) pages.push("ellipsis");

  for (let i = left; i <= right; i++) {
    pages.push(i);
  }

  if (right < total - 1) pages.push("ellipsis");

  // Always show last page
  if (total > 1) pages.push(total);

  return pages;
}

export default function FeedsPage({ onLogout }: { onLogout: () => void }) {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [pagination, setPagination] = useState<FeedListPagination>(DEFAULT_PAGINATION);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<FeedSortBy>("created_at");
  const [sortDir, setSortDir] = useState<FeedSortDir>("desc");
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [toast, setToast] = useState("");
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingFeedId, setEditingFeedId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await api.listFeeds({ page, page_size: PAGE_SIZE, sort_by: sortBy, sort_dir: sortDir });
      if (result.pagination.total > 0 && result.pagination.page > result.pagination.total_pages) {
        setPage(result.pagination.total_pages);
        return;
      }
      setFeeds(result.feeds);
      setPagination(result.pagination);
      setListError("");
    } catch {
      setListError("Failed to load feeds.");
    } finally {
      setLoading(false);
    }
  }, [page, sortBy, sortDir]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  async function handleSync(feed: Feed) {
    setSyncingId(feed.id);
    try {
      const result = await api.syncFeed(feed.id);
      showToast(`Sync ${result.status}: ${result.imported_count} imported`);
      await refresh();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncingId(null);
    }
  }

  async function handleDelete(feed: Feed) {
    if (!confirm(`Delete "${feed.title}"?`)) return;
    try {
      await api.deleteFeed(feed.id);
      showToast(`Deleted ${feed.title}`);
      if (feeds.length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      } else {
        await refresh();
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function handleCopy(feed: Feed) {
    try {
      await navigator.clipboard.writeText(feedUrlForCurrentOrigin(feed));
      setCopiedId(feed.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      showToast("Failed to copy URL");
    }
  }

  function openEditor(feedId: number | null = null) {
    setEditingFeedId(feedId);
    setEditorOpen(true);
  }

  function closeEditor() {
    setEditorOpen(false);
    setEditingFeedId(null);
  }

  function handleEditorSaved() {
    closeEditor();
    if (page === 1) {
      refresh();
    } else {
      setPage(1);
    }
    showToast(editingFeedId ? "Feed updated" : "Feed created");
  }

  function handleSort(column: FeedSortBy) {
    if (sortBy === column) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(column);
      setSortDir("desc");
    }
    setPage(1);
  }

  function formatSyncTooltip(feed: Feed): string {
    const parts: string[] = [];
    if (feed.sync_status.last_sync_finished_at) {
      parts.push(`Last sync: ${new Date(feed.sync_status.last_sync_finished_at).toLocaleString()}`);
    }
    if (feed.sync_status.last_sync_imported_count > 0) {
      parts.push(`Imported: ${feed.sync_status.last_sync_imported_count}`);
    }
    if (feed.sync_status.last_sync_skipped_count > 0) {
      parts.push(`Skipped: ${feed.sync_status.last_sync_skipped_count}`);
    }
    if (feed.sync_status.last_sync_error) {
      parts.push(`Error: ${feed.sync_status.last_sync_error}`);
    }
    return parts.length > 0 ? parts.join("\n") : "Never synced";
  }

  function renderSortIcon(column: FeedSortBy) {
    if (sortBy !== column) {
      return <span className="sort-icon sort-icon-inactive"><SortDescIcon /></span>;
    }
    return (
      <span className="sort-icon sort-icon-active">
        {sortDir === "asc" ? <SortAscIcon /> : <SortDescIcon />}
      </span>
    );
  }

  if (loading) {
    return (
      <div className="app-content">
        <p style={{ color: "var(--text-tertiary)", padding: "32px 0" }}>Loading feeds...</p>
      </div>
    );
  }

  const rangeStart = pagination.total === 0 || feeds.length === 0 ? 0 : (pagination.page - 1) * pagination.page_size + 1;
  const rangeEnd = feeds.length === 0 ? 0 : Math.min(pagination.total, rangeStart + feeds.length - 1);
  const pageNumbers = buildPageNumbers(pagination.page, pagination.total_pages);

  return (
    <div className="app-content">
      <div className="page-header">
        <div>
          <h1>Feeds</h1>
          <div className="page-header-sub">
            {pagination.total} configured feed rule{pagination.total === 1 ? "" : "s"}
          </div>
        </div>
        <Button onClick={() => openEditor()}>
          <PlusIcon /> Add feed
        </Button>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {listError ? <div className="feed-list-error error-msg">{listError}</div> : null}
        {feeds.length === 0 ? (
          <div className="empty-state">
            <h3>{pagination.total === 0 ? "No feeds yet" : "No feeds on this page"}</h3>
            <p>
              {pagination.total === 0
                ? "Create a feed rule with IMAP settings and a recipient filter to get started."
                : "Try the previous page or adjust the list controls."}
            </p>
          </div>
        ) : (
          <div className="feed-table-wrap">
            <table className="feed-table">
              <thead>
                <tr>
                  {SORT_COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      className={`feed-th ${sortBy === col.key ? "feed-th-active" : ""}`}
                      onClick={() => handleSort(col.key)}
                    >
                      <span className="feed-th-inner">
                        {col.label}
                        {renderSortIcon(col.key)}
                      </span>
                    </th>
                  ))}
                  <th className="feed-th feed-th-status">Status</th>
                  <th className="feed-th feed-th-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {feeds.map((feed) => (
                  <tr key={feed.id} className="feed-tr">
                    <td className="feed-td feed-td-title">
                      <div className="feed-cell-title">{feed.title}</div>
                      <div className="feed-cell-meta">
                        <span>{feed.recipient}</span>
                        {feed.folders.length > 0 && <span>{feed.folders.join(", ")}</span>}
                      </div>
                    </td>
                    <td className="feed-td feed-td-items">{feed.item_count}</td>
                    <td className="feed-td feed-td-sync">
                      {feed.sync_status.last_sync_finished_at
                        ? new Date(feed.sync_status.last_sync_finished_at).toLocaleString()
                        : "—"}
                    </td>
                    <td className="feed-td feed-td-date">
                      {new Date(feed.created_at).toLocaleDateString()}
                    </td>
                    <td className="feed-td feed-td-date">
                      {new Date(feed.updated_at).toLocaleDateString()}
                    </td>
                    <td className="feed-td feed-td-status">
                      <StatusBadge status={feed.sync_status.last_sync_status} tooltip={formatSyncTooltip(feed)} />
                    </td>
                    <td className="feed-td feed-td-actions">
                      <div className="feed-row-actions">
                        <Button
                          variant="icon"
                          title="Manually trigger a sync for this feed"
                          disabled={syncingId === feed.id}
                          onClick={() => handleSync(feed)}
                        >
                          <RefreshIcon style={syncingId === feed.id ? { animation: "spin 1s linear infinite" } : undefined} />
                        </Button>
                        <Button variant="icon" title="Edit feed settings" onClick={() => openEditor(feed.id)}>
                          <PencilIcon />
                        </Button>
                        <Button variant="icon" title="Copy RSS feed URL to clipboard" onClick={() => handleCopy(feed)}>
                          {copiedId === feed.id ? <CheckIcon style={{ color: "var(--emerald)" }} /> : <CopyIcon />}
                        </Button>
                        <Button variant="icon" title="Delete this feed" onClick={() => handleDelete(feed)}>
                          <TrashIcon style={{ color: "var(--danger)" }} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
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
                title="First page"
                aria-label="First page"
              >
                <ChevronsLeftIcon />
              </button>
              <button
                className="page-btn page-btn-nav"
                disabled={!pagination.has_previous}
                onClick={() => setPage((c) => Math.max(1, c - 1))}
                title="Previous page"
                aria-label="Previous page"
              >
                <ChevronLeftIcon />
              </button>
              {pageNumbers.map((p, i) =>
                p === "ellipsis" ? (
                  <span key={`e${i}`} className="page-ellipsis">...</span>
                ) : (
                  <button
                    key={p}
                    className={`page-btn page-btn-num ${p === pagination.page ? "page-btn-current" : ""}`}
                    onClick={() => setPage(p)}
                    aria-current={p === pagination.page ? "page" : undefined}
                  >
                    {p}
                  </button>
                )
              )}
              <button
                className="page-btn page-btn-nav"
                disabled={!pagination.has_next}
                onClick={() => setPage((c) => c + 1)}
                title="Next page"
                aria-label="Next page"
              >
                <ChevronRightIcon />
              </button>
              <button
                className="page-btn page-btn-nav"
                disabled={!pagination.has_next}
                onClick={() => setPage(pagination.total_pages)}
                title="Last page"
                aria-label="Last page"
              >
                <ChevronsRightIcon />
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {toast ? <div className="toast">{toast}</div> : null}

      <FeedEditorModal
        open={editorOpen}
        feedId={editingFeedId}
        onClose={closeEditor}
        onSaved={handleEditorSaved}
      />
    </div>
  );
}
