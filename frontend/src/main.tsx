import React, { FormEvent, startTransition, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, Feed, FeedForm, PreviewResult } from "./api";
import { Button, Card, Field, GhostButton, Input, Select, Textarea } from "./components/ui";
import "./styles.css";

const emptyForm: FeedForm = {
  title: "",
  recipient: "",
  imap_host: "",
  imap_port: 993,
  imap_tls: "ssl",
  imap_username: "",
  imap_password: "",
  folders: ["INBOX"],
  backfill_days: 30,
  retention_count: 50,
  sync_interval_minutes: 60
};

function App() {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    api
      .me()
      .then(() => {
        setAuthenticated(true);
        return refreshFeeds();
      })
      .catch(() => setAuthenticated(false))
      .finally(() => setLoading(false));
  }, []);

  async function refreshFeeds() {
    const result = await api.listFeeds();
    startTransition(() => setFeeds(result.feeds));
  }

  if (loading) {
    return <Shell message="Loading admin session..." />;
  }

  if (!authenticated) {
    return (
      <Shell>
        <Login
          onLogin={async (token) => {
            await api.login(token);
            setAuthenticated(true);
            await refreshFeeds();
          }}
        />
      </Shell>
    );
  }

  return (
    <Shell message={message}>
      <Dashboard
        feeds={feeds}
        onMessage={setMessage}
        onRefresh={refreshFeeds}
        onLogout={async () => {
          await api.logout();
          setAuthenticated(false);
          setFeeds([]);
        }}
      />
    </Shell>
  );
}

function Shell({ children, message }: { children?: React.ReactNode; message?: string }) {
  return (
    <main className="shell">
      <div className="hero">
        <div>
          <p className="eyebrow">IMAP to RSS, owned locally</p>
          <h1>Own New Newsletter</h1>
          <p className="lede">Pull newsletters out of your inbox and publish them as private, unguessable RSS feeds.</p>
        </div>
        {message ? <div className="toast">{message}</div> : null}
      </div>
      {children}
    </main>
  );
}

function Login({ onLogin }: { onLogin: (token: string) => Promise<void> }) {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="login-card">
      <form onSubmit={submit}>
        <Field label="Admin token" hint="Stored only as an HttpOnly session cookie after login.">
          <Input value={token} onChange={(event) => setToken(event.target.value)} type="password" autoFocus />
        </Field>
        {error ? <p className="error">{error}</p> : null}
        <Button disabled={busy}>{busy ? "Checking..." : "Enter admin panel"}</Button>
      </form>
    </Card>
  );
}

function Dashboard({
  feeds,
  onMessage,
  onRefresh,
  onLogout
}: {
  feeds: Feed[];
  onMessage: (message: string) => void;
  onRefresh: () => Promise<void>;
  onLogout: () => Promise<void>;
}) {
  const [editing, setEditing] = useState<Feed | null>(null);
  const [busyFeedId, setBusyFeedId] = useState<number | null>(null);

  return (
    <div className="dashboard">
      <div className="toolbar">
        <div>
          <h2>Feeds</h2>
          <p>{feeds.length} configured feed rule{feeds.length === 1 ? "" : "s"}</p>
        </div>
        <GhostButton onClick={onLogout}>Log out</GhostButton>
      </div>
      <div className="grid">
        <FeedEditor
          feed={editing}
          onCancel={() => setEditing(null)}
          onSaved={async (saved) => {
            setEditing(null);
            onMessage(`Saved ${saved.title}`);
            await onRefresh();
          }}
        />
        <section className="feed-list">
          {feeds.length === 0 ? (
            <Card className="empty-state">
              <h3>No feeds yet</h3>
              <p>Create a feed rule with IMAP settings and a recipient address. Preview can return zero matches.</p>
            </Card>
          ) : (
            feeds.map((feed) => (
              <Card key={feed.id} className="feed-card">
                <div className="feed-card-head">
                  <div>
                    <h3>{feed.title}</h3>
                    <p>{feed.recipient}</p>
                  </div>
                  <StatusBadge status={feed.sync_status.last_sync_status} />
                </div>
                <dl className="facts">
                  <div>
                    <dt>Mailbox</dt>
                    <dd>
                      {feed.imap_username} @ {feed.imap_host}:{feed.imap_port}
                    </dd>
                  </div>
                  <div>
                    <dt>Folders</dt>
                    <dd>{feed.folders.join(", ")}</dd>
                  </div>
                  <div>
                    <dt>Last sync</dt>
                    <dd>{feed.sync_status.last_sync_finished_at ?? "Never"}</dd>
                  </div>
                  <div>
                    <dt>Imported</dt>
                    <dd>{feed.sync_status.last_sync_imported_count}</dd>
                  </div>
                </dl>
                {feed.sync_status.last_sync_error ? <p className="error">{feed.sync_status.last_sync_error}</p> : null}
                <div className="copy-row">
                  <input readOnly value={feed.feed_url} onFocus={(event) => event.currentTarget.select()} />
                  <a href={feed.feed_url} target="_blank" rel="noreferrer">
                    Open
                  </a>
                </div>
                <div className="actions">
                  <Button
                    disabled={busyFeedId === feed.id}
                    onClick={async () => {
                      setBusyFeedId(feed.id);
                      try {
                        const result = await api.syncFeed(feed.id);
                        onMessage(`Sync ${result.status}: ${result.imported_count} imported`);
                        await onRefresh();
                      } catch (err) {
                        onMessage(err instanceof Error ? err.message : "Sync failed");
                      } finally {
                        setBusyFeedId(null);
                      }
                    }}
                  >
                    {busyFeedId === feed.id ? "Syncing..." : "Manual sync"}
                  </Button>
                  <GhostButton onClick={() => setEditing(feed)}>Edit</GhostButton>
                  <GhostButton
                    onClick={async () => {
                      if (!confirm(`Delete ${feed.title}?`)) return;
                      await api.deleteFeed(feed.id);
                      onMessage(`Deleted ${feed.title}`);
                      await onRefresh();
                    }}
                  >
                    Delete
                  </GhostButton>
                </div>
              </Card>
            ))
          )}
        </section>
      </div>
    </div>
  );
}

function FeedEditor({
  feed,
  onCancel,
  onSaved
}: {
  feed: Feed | null;
  onCancel: () => void;
  onSaved: (feed: Feed) => Promise<void>;
}) {
  const [form, setForm] = useState<FeedForm>(emptyForm);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "save" | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!feed) {
      setForm(emptyForm);
      setPreview(null);
      return;
    }
    setForm({
      title: feed.title,
      recipient: feed.recipient,
      imap_host: feed.imap_host,
      imap_port: feed.imap_port,
      imap_tls: feed.imap_tls,
      imap_username: feed.imap_username,
      imap_password: "",
      folders: feed.folders,
      backfill_days: feed.backfill_days,
      retention_count: feed.retention_count,
      sync_interval_minutes: feed.sync_interval_minutes
    });
    setPreview(null);
  }, [feed]);

  function patch(update: Partial<FeedForm>) {
    setForm((current) => ({ ...current, ...update }));
  }

  async function runPreview() {
    setBusy("preview");
    setError("");
    setPreview(null);
    try {
      if (feed && !form.imap_password) {
        throw new Error("Enter the IMAP password to preview edited settings.");
      }
      setPreview(await api.preview(form));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(null);
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy("save");
    setError("");
    try {
      if (feed) {
        const update: Partial<FeedForm> = { ...form };
        if (!update.imap_password) delete update.imap_password;
        const result = await api.updateFeed(feed.id, update);
        await onSaved(result.feed);
      } else {
        const result = await api.createFeed(form);
        await onSaved(result.feed);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="editor">
      <div className="editor-head">
        <div>
          <h2>{feed ? "Edit feed" : "Create feed"}</h2>
          <p>Settings are validated against IMAP before saving.</p>
        </div>
        {feed ? <GhostButton onClick={onCancel}>New feed</GhostButton> : null}
      </div>
      <form onSubmit={save}>
        <div className="form-grid">
          <Field label="Feed title">
            <Input value={form.title} onChange={(event) => patch({ title: event.target.value })} required />
          </Field>
          <Field label="Recipient filter" hint="Exact case-insensitive match against To, Cc, Delivered-To, X-Original-To.">
            <Input value={form.recipient} onChange={(event) => patch({ recipient: event.target.value })} required />
          </Field>
          <Field label="IMAP host">
            <Input value={form.imap_host} onChange={(event) => patch({ imap_host: event.target.value })} required />
          </Field>
          <Field label="Port">
            <Input
              type="number"
              value={form.imap_port}
              onChange={(event) => patch({ imap_port: Number(event.target.value) })}
              required
            />
          </Field>
          <Field label="TLS">
            <Select value={form.imap_tls} onChange={(event) => patch({ imap_tls: event.target.value as FeedForm["imap_tls"] })}>
              <option value="ssl">SSL</option>
              <option value="starttls">STARTTLS</option>
              <option value="none">None</option>
            </Select>
          </Field>
          <Field label="Username">
            <Input value={form.imap_username} onChange={(event) => patch({ imap_username: event.target.value })} required />
          </Field>
          <Field label="Password" hint={feed ? "Leave blank to keep the saved encrypted password." : "Encrypted before SQLite storage."}>
            <Input
              type="password"
              value={form.imap_password}
              onChange={(event) => patch({ imap_password: event.target.value })}
              required={!feed}
            />
          </Field>
          <Field label="Folders" hint="One folder per line. INBOX is the default.">
            <Textarea
              value={form.folders.join("\n")}
              onChange={(event) => patch({ folders: event.target.value.split(/\n+/).map((value) => value.trim()) })}
            />
          </Field>
          <Field label="Backfill days">
            <Input
              type="number"
              value={form.backfill_days}
              onChange={(event) => patch({ backfill_days: Number(event.target.value) })}
            />
          </Field>
          <Field label="Retention count">
            <Input
              type="number"
              value={form.retention_count}
              onChange={(event) => patch({ retention_count: Number(event.target.value) })}
            />
          </Field>
          <Field label="Sync interval minutes" hint="Set 0 to disable scheduled sync for this feed.">
            <Input
              type="number"
              value={form.sync_interval_minutes}
              onChange={(event) => patch({ sync_interval_minutes: Number(event.target.value) })}
            />
          </Field>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {preview ? <Preview result={preview} /> : null}
        <div className="actions">
          <GhostButton type="button" onClick={runPreview} disabled={busy !== null}>
            {busy === "preview" ? "Previewing..." : "Preview matches"}
          </GhostButton>
          <Button disabled={busy !== null}>{busy === "save" ? "Saving..." : feed ? "Save changes" : "Create feed"}</Button>
        </div>
      </form>
    </Card>
  );
}

function Preview({ result }: { result: PreviewResult }) {
  return (
    <div className="preview">
      <strong>{result.match_count} matching message{result.match_count === 1 ? "" : "s"}</strong>
      {result.samples.length > 0 ? (
        <ul>
          {result.samples.map((sample) => (
            <li key={`${sample.folder}-${sample.uid}`}>
              <span>{sample.subject}</span>
              <small>{sample.author || "Unknown author"}</small>
            </li>
          ))}
        </ul>
      ) : (
        <p>Zero matches is allowed. Save the feed if this recipient is intended for future newsletters.</p>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string | null }) {
  const label = status ?? "never";
  return <span className={`status ${label}`}>{label}</span>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

