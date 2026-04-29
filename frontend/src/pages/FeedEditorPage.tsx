import { FormEvent, useEffect, useState } from "react";
import { api, Feed, FeedForm, PreviewResult } from "../api";
import { Button, Field, Input, Modal, Select, Textarea } from "../components/ui";

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

export default function FeedEditorModal({
  open,
  feedId,
  onClose,
  onSaved
}: {
  open: boolean;
  feedId: number | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = feedId !== null;

  const [form, setForm] = useState<FeedForm>(emptyForm);
  const [existingFeed, setExistingFeed] = useState<Feed | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "save" | "loading" | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      setForm(emptyForm);
      setExistingFeed(null);
      setPreview(null);
      setBusy(null);
      setError("");
      return;
    }
    if (!isEdit) return;
    setBusy("loading");
    api.getFeed(feedId).then((result) => {
      const feed = result.feed;
      setExistingFeed(feed);
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
      setBusy(null);
    }).catch(() => onClose());
  }, [open, feedId, isEdit, onClose]);

  function patch(update: Partial<FeedForm>) {
    setForm((cur) => ({ ...cur, ...update }));
  }

  async function runPreview() {
    setBusy("preview");
    setError("");
    setPreview(null);
    try {
      if (isEdit && !form.imap_password) {
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
      if (isEdit && existingFeed) {
        const update: Partial<FeedForm> = { ...form };
        if (!update.imap_password) delete update.imap_password;
        await api.updateFeed(existingFeed.id, update);
      } else {
        await api.createFeed(form);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setBusy(null);
    }
  }

  const title = isEdit ? "Edit feed" : "Create feed";

  return (
    <Modal open={open} onClose={onClose} title={title}>
      {busy === "loading" ? (
        <p style={{ color: "var(--text-tertiary)" }}>Loading feed...</p>
      ) : (
        <>
          <p style={{ fontSize: 13, color: "var(--text-tertiary)", marginBottom: 20 }}>
            IMAP settings are validated before saving.
            {isEdit ? " Leave password blank to keep the saved encrypted password." : ""}
          </p>

          <form onSubmit={save}>
            <div className="form-grid">
              <Field label="Feed title">
                <Input
                  value={form.title}
                  onChange={(e) => patch({ title: e.target.value })}
                  placeholder="My Newsletter"
                  required
                />
              </Field>
              <Field label="Recipient filter" hint="Case-insensitive exact match on To, Cc, Delivered-To, X-Original-To.">
                <Input
                  value={form.recipient}
                  onChange={(e) => patch({ recipient: e.target.value })}
                  placeholder="newsletter@example.com"
                  required
                />
              </Field>
              <Field label="IMAP host">
                <Input
                  value={form.imap_host}
                  onChange={(e) => patch({ imap_host: e.target.value })}
                  placeholder="imap.example.com"
                  required
                />
              </Field>
              <Field label="Port">
                <Input
                  type="number"
                  value={form.imap_port}
                  onChange={(e) => patch({ imap_port: Number(e.target.value) })}
                  required
                />
              </Field>
              <Field label="TLS">
                <Select
                  value={form.imap_tls}
                  onChange={(e) => patch({ imap_tls: e.target.value as FeedForm["imap_tls"] })}
                >
                  <option value="ssl">SSL</option>
                  <option value="starttls">STARTTLS</option>
                  <option value="none">None</option>
                </Select>
              </Field>
              <Field label="Username">
                <Input
                  value={form.imap_username}
                  onChange={(e) => patch({ imap_username: e.target.value })}
                  required
                />
              </Field>
              <Field label="Password" hint={isEdit ? "Leave blank to keep saved password." : "Encrypted before storage."}>
                <Input
                  type="password"
                  value={form.imap_password}
                  onChange={(e) => patch({ imap_password: e.target.value })}
                  required={!isEdit}
                />
              </Field>
              <Field label="Folders" hint="One folder per line. INBOX is the default.">
                <Textarea
                  value={form.folders.join("\n")}
                  onChange={(e) => patch({ folders: e.target.value.split(/\n+/).map((v) => v.trim()).filter(Boolean) })}
                />
              </Field>
              <Field label="Backfill days">
                <Input
                  type="number"
                  value={form.backfill_days}
                  onChange={(e) => patch({ backfill_days: Number(e.target.value) })}
                />
              </Field>
              <Field label="Retention count">
                <Input
                  type="number"
                  value={form.retention_count}
                  onChange={(e) => patch({ retention_count: Number(e.target.value) })}
                />
              </Field>
              <Field label="Sync interval (minutes)" hint="Set 0 to disable scheduled sync.">
                <Input
                  type="number"
                  value={form.sync_interval_minutes}
                  onChange={(e) => patch({ sync_interval_minutes: Number(e.target.value) })}
                />
              </Field>
            </div>

            {error ? <div className="error-msg">{error}</div> : null}

            {preview ? (
              <div className="preview-box">
                <strong>{preview.match_count} matching message{preview.match_count === 1 ? "" : "s"}</strong>
                <p>Scanned {preview.scanned_count} recent message{preview.scanned_count === 1 ? "" : "s"}.</p>
                {preview.samples.length > 0 ? (
                  <ul className="preview-list">
                    {preview.samples.map((s) => (
                      <li key={`${s.folder}-${s.uid}`}>
                        <span>{s.subject}</span>
                        <small>{s.author || "Unknown author"}</small>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ marginTop: 8 }}>Zero matches is fine — save the feed for future newsletters.</p>
                )}
              </div>
            ) : null}

            <div className="form-actions">
              <Button variant="ghost" type="button" onClick={runPreview} disabled={busy !== null}>
                {busy === "preview" ? "Previewing..." : "Preview matches"}
              </Button>
              <Button disabled={busy !== null}>
                {busy === "save" ? "Saving..." : isEdit ? "Save changes" : "Create feed"}
              </Button>
            </div>
          </form>
        </>
      )}
    </Modal>
  );
}
