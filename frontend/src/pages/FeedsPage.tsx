import { useEffect, useState, useCallback } from "react";
import { api, type Feed, type FeedListPagination, type FeedSortBy, type FeedSortDir } from "../api";
import { Button, Select, StatusBadge } from "../components/ui";
import { PlusIcon, PencilIcon, CopyIcon, TrashIcon, CheckIcon, RefreshIcon } from "../components/icons";
import FeedEditorModal from "./FeedEditorPage";

const PAGE_SIZE_OPTIONS = [10, 25, 50];

const SORT_OPTIONS: Array<{ value: FeedSortBy; label: string }> = [
  { value: "created_at", label: "Created" },
  { value: "updated_at", label: "Updated" },
  { value: "title", label: "Title" },
  { value: "item_count", label: "Items" },
  { value: "last_sync", label: "Last sync" }
];

const DEFAULT_PAGINATION: FeedListPagination = {
  page: 1,
  page_size: PAGE_SIZE_OPTIONS[0],
  total: 0,
  total_pages: 1,
  has_next: false,
  has_previous: false
};

export default function FeedsPage({ onLogout }: { onLogout: () => void }) {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [pagination, setPagination] = useState<FeedListPagination>(DEFAULT_PAGINATION);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0]);
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
      const result = await api.listFeeds({ page, page_size: pageSize, sort_by: sortBy, sort_dir: sortDir });
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
  }, [page, pageSize, sortBy, sortDir]);

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
      await navigator.clipboard.writeText(feed.feed_url);
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

  if (loading) {
    return (
      <div className="app-content">
        <p style={{ color: "var(--text-tertiary)", padding: "32px 0" }}>Loading feeds...</p>
      </div>
    );
  }

  const rangeStart = pagination.total === 0 || feeds.length === 0 ? 0 : (pagination.page - 1) * pagination.page_size + 1;
  const rangeEnd = feeds.length === 0 ? 0 : Math.min(pagination.total, rangeStart + feeds.length - 1);

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
        {pagination.total > 0 ? (
          <div className="feed-toolbar">
            <div className="feed-toolbar-summary">
              Showing {rangeStart}-{rangeEnd} of {pagination.total}
            </div>
            <div className="feed-toolbar-controls">
              <label className="feed-control">
                <span>Sort</span>
                <Select
                  value={sortBy}
                  aria-label="Sort feeds"
                  onChange={(event) => {
                    setPage(1);
                    setSortBy(event.target.value as FeedSortBy);
                  }}
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </Select>
              </label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setPage(1);
                  setSortDir((current) => current === "asc" ? "desc" : "asc");
                }}
                title="Toggle sort direction"
              >
                {sortDir === "asc" ? "Ascending" : "Descending"}
              </Button>
              <label className="feed-control">
                <span>Rows</span>
                <Select
                  value={pageSize}
                  aria-label="Feeds per page"
                  onChange={(event) => {
                    setPage(1);
                    setPageSize(Number(event.target.value));
                  }}
                >
                  {PAGE_SIZE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </Select>
              </label>
            </div>
          </div>
        ) : null}
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
          <div className="feed-list">
            {feeds.map((feed) => (
              <div key={feed.id} className="feed-row">
                <div className="feed-row-info">
                  <div className="feed-row-title">{feed.title}</div>
                  <div className="feed-row-meta">
                    <span>{feed.recipient}</span>
                    <span>{feed.folders.join(", ")}</span>
                  </div>
                </div>
                <span className="feed-item-count" title="Feed items count">{feed.item_count} items</span>
                <StatusBadge status={feed.sync_status.last_sync_status} tooltip={formatSyncTooltip(feed)} />
                <div className="feed-row-actions">
                  <Button
                    variant="icon"
                    title="Manually trigger a sync for this feed"
                    disabled={syncingId === feed.id}
                    onClick={() => handleSync(feed)}
                  >
                    <RefreshIcon style={syncingId === feed.id ? { animation: "spin 1s linear infinite" } : undefined} />
                  </Button>
                  <Button
                    variant="icon"
                    title="Edit feed settings"
                    onClick={() => openEditor(feed.id)}
                  >
                    <PencilIcon />
                  </Button>
                  <Button
                    variant="icon"
                    title="Copy RSS feed URL to clipboard"
                    onClick={() => handleCopy(feed)}
                  >
                    {copiedId === feed.id ? (
                      <CheckIcon style={{ color: "var(--emerald)" }} />
                    ) : (
                      <CopyIcon />
                    )}
                  </Button>
                  <Button
                    variant="icon"
                    title="Delete this feed"
                    onClick={() => handleDelete(feed)}
                  >
                    <TrashIcon style={{ color: "var(--danger)" }} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
        {pagination.total > 0 ? (
          <div className="pagination-bar">
            <span>Page {pagination.page} of {pagination.total_pages}</span>
            <div className="pagination-actions">
              <Button
                variant="ghost"
                size="sm"
                disabled={!pagination.has_previous}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!pagination.has_next}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
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
