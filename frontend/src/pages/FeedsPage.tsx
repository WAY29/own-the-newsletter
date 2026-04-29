import { useEffect, useState, useCallback } from "react";
import { api, Feed } from "../api";
import { Button, StatusBadge } from "../components/ui";
import { PlusIcon, PencilIcon, CopyIcon, TrashIcon, CheckIcon, RefreshIcon } from "../components/icons";
import FeedEditorModal from "./FeedEditorPage";

function feedUrlForCurrentOrigin(feed: Feed): string {
  return new URL(`/f/${encodeURIComponent(feed.random_slug)}.xml`, window.location.origin).toString();
}

export default function FeedsPage({ onLogout }: { onLogout: () => void }) {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingFeedId, setEditingFeedId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await api.listFeeds();
      setFeeds(result.feeds);
    } catch {
      // auth failure handled by app shell
    } finally {
      setLoading(false);
    }
  }, []);

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
      await refresh();
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
    refresh();
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

  return (
    <div className="app-content">
      <div className="page-header">
        <div>
          <h1>Feeds</h1>
          <div className="page-header-sub">
            {feeds.length} configured feed rule{feeds.length === 1 ? "" : "s"}
          </div>
        </div>
        <Button onClick={() => openEditor()}>
          <PlusIcon /> Add feed
        </Button>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {feeds.length === 0 ? (
          <div className="empty-state">
            <h3>No feeds yet</h3>
            <p>Create a feed rule with IMAP settings and a recipient filter to get started.</p>
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
