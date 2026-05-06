import { FormEvent, useEffect, useState } from "react";
import { api, type AdminSettings } from "../api";
import { Button, Field, Input, Modal } from "../components/ui";

const FALLBACK_SETTINGS: AdminSettings = {
  default_proxy_url: "",
  default_sync_interval_minutes: 60
};

export default function SettingsModal({
  open,
  onClose
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [form, setForm] = useState<AdminSettings>(FALLBACK_SETTINGS);
  const [busy, setBusy] = useState<"loading" | "save" | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    if (!open) {
      setForm(FALLBACK_SETTINGS);
      setBusy(null);
      setError("");
      setMessage("");
      return;
    }

    setBusy("loading");
    setError("");
    setMessage("");
    api.getSettings().then((result) => {
      if (cancelled) return;
      setForm(result.settings);
      setBusy(null);
    }).catch((err) => {
      if (cancelled) return;
      setError(err instanceof Error ? err.message : "Could not load settings");
      setBusy(null);
    });

    return () => {
      cancelled = true;
    };
  }, [open]);

  function patch(update: Partial<AdminSettings>) {
    setForm((cur) => ({ ...cur, ...update }));
    setMessage("");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy("save");
    setError("");
    setMessage("");
    try {
      const result = await api.updateSettings(form);
      setForm(result.settings);
      setMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Settings">
      {busy === "loading" ? (
        <p style={{ color: "var(--text-tertiary)" }}>Loading settings...</p>
      ) : (
        <form onSubmit={save}>
          <p className="settings-intro">
            These values are defaults for new feeds. Existing feeds keep their own settings.
          </p>

          <div className="form-grid">
            <Field
              full
              label="Default proxy URL"
              hint="Optional. Saved for future feed sources that fetch remote RSS. Current IMAP feeds do not use this proxy."
            >
              <Input
                value={form.default_proxy_url}
                onChange={(e) => patch({ default_proxy_url: e.target.value })}
                placeholder="http://127.0.0.1:7890"
              />
            </Field>
            <Field
              label="Default sync interval (minutes)"
              hint="Used when creating new feeds. Set 0 to disable scheduled sync by default."
            >
              <Input
                type="number"
                min={0}
                max={10080}
                value={form.default_sync_interval_minutes}
                onChange={(e) => patch({ default_sync_interval_minutes: Number(e.target.value) })}
              />
            </Field>
          </div>

          {error ? <div className="error-msg">{error}</div> : null}
          {message ? <div className="success-msg">{message}</div> : null}

          <div className="form-actions">
            <Button variant="ghost" type="button" onClick={onClose} disabled={busy !== null}>
              Close
            </Button>
            <Button disabled={busy !== null}>
              {busy === "save" ? "Saving..." : "Save settings"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
