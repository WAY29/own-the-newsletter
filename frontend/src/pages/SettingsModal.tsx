import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  PUBLICATION_TARGETS,
  api,
  type AdminSettings,
  type PublicationSettings,
  type PublicationSettingsForm,
  type PublicationTarget
} from "../api";
import { Button, Field, Input, Modal, StatusBadge } from "../components/ui";

const FALLBACK_SETTINGS: AdminSettings = {
  default_proxy_url: "",
  default_sync_interval_minutes: 60
};

const FALLBACK_PUBLICATION: PublicationSettings = {
  active_target: PUBLICATION_TARGETS.backend,
  github_repository: "",
  github_branch: "main",
  github_directory: "feeds",
  github_public_url: "",
  github_token_present: false,
  last_publication_started_at: null,
  last_publication_finished_at: null,
  last_publication_status: null,
  last_publication_error: null,
  last_publication_feed_id: null,
  last_publication_feed_title: null
};

const DEFAULT_PROXY_HINT =
  "Optional. Saved for future feed sources that fetch remote RSS. Current IMAP feeds do not use this proxy.";
const GITHUB_REPOSITORY_HINT =
  "Use owner/repo or a github.com repository URL. Non-GitHub remotes are rejected.";
const GITHUB_BRANCH_HINT =
  "The branch must already exist. It will not be created automatically.";
const GITHUB_PUBLIC_URL_HINT =
  "Public site base URL. Directory is appended automatically unless the URL already includes it.";
const GITHUB_TOKEN_PRESENT_HINT =
  "Token configured. Leave blank to keep the existing token.";
const GITHUB_TOKEN_REQUIRED_HINT =
  "A token with repository write access is required to activate GitHub publishing.";

type SettingsTab = "defaults" | "publication";
type BusyState =
  | "loading"
  | "save-defaults"
  | "save-publication"
  | "activate-github"
  | "activate-backend"
  | "retry"
  | null;

function publicationFormFromSettings(settings: PublicationSettings): PublicationSettingsForm {
  return {
    github_repository: settings.github_repository,
    github_branch: settings.github_branch,
    github_directory: settings.github_directory,
    github_public_url: settings.github_public_url,
    github_token: ""
  };
}

function targetOptionClass(active: boolean) {
  return [
    "publication-target-option",
    active ? "publication-target-option-active" : ""
  ].filter(Boolean).join(" ");
}

export default function SettingsModal({
  open,
  onClose
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<SettingsTab>("defaults");
  const [publicationTarget, setPublicationTarget] = useState<PublicationTarget>(PUBLICATION_TARGETS.backend);
  const [form, setForm] = useState<AdminSettings>(FALLBACK_SETTINGS);
  const [publication, setPublication] = useState<PublicationSettings>(FALLBACK_PUBLICATION);
  const [publicationForm, setPublicationForm] = useState<PublicationSettingsForm>({
    github_repository: "",
    github_branch: "main",
    github_directory: "feeds",
    github_public_url: "",
    github_token: ""
  });
  const [busy, setBusy] = useState<BusyState>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const applyPublicationSettings = useCallback((
    settings: PublicationSettings,
    options: { syncTarget?: boolean } = {}
  ) => {
    setPublication(settings);
    if (options.syncTarget) {
      setPublicationTarget(settings.active_target);
    }
    setPublicationForm(publicationFormFromSettings(settings));
  }, []);

  useEffect(() => {
    let cancelled = false;

    if (!open) {
      setTab("defaults");
      setForm(FALLBACK_SETTINGS);
      applyPublicationSettings(FALLBACK_PUBLICATION, { syncTarget: true });
      setBusy(null);
      setError("");
      setMessage("");
      return;
    }

    setBusy("loading");
    setError("");
    setMessage("");
    Promise.all([api.getSettings(), api.getPublicationSettings()])
      .then(([settingsResult, publicationResult]) => {
        if (cancelled) return;
        setForm(settingsResult.settings);
        applyPublicationSettings(publicationResult.settings, { syncTarget: true });
        setBusy(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not load settings");
        setBusy(null);
      });

    return () => {
      cancelled = true;
    };
  }, [applyPublicationSettings, open]);

  function patch(update: Partial<AdminSettings>) {
    setForm((cur) => ({ ...cur, ...update }));
    setMessage("");
  }

  function patchPublication(update: Partial<PublicationSettingsForm>) {
    setPublicationForm((cur) => ({ ...cur, ...update }));
    setMessage("");
  }

  async function saveDefaults(event: FormEvent) {
    event.preventDefault();
    setBusy("save-defaults");
    setError("");
    setMessage("");
    try {
      const result = await api.updateSettings(form);
      setForm(result.settings);
      setMessage("Feed default settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function savePublicationSettings(): Promise<PublicationSettings> {
    const result = await api.updatePublicationSettings(publicationForm);
    applyPublicationSettings(result.settings);
    return result.settings;
  }

  async function savePublication(event: FormEvent) {
    event.preventDefault();
    setBusy("save-publication");
    setError("");
    setMessage("");
    try {
      await savePublicationSettings();
      setMessage("RSS publishing settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function activateGithub() {
    setBusy("activate-github");
    setError("");
    setMessage("");
    try {
      await savePublicationSettings();
      const result = await api.activateGithubPublication();
      applyPublicationSettings(result.settings, { syncTarget: true });
      setMessage("GitHub RSS publishing activated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "GitHub activation failed");
    } finally {
      setBusy(null);
    }
  }

  async function activateBackend() {
    setBusy("activate-backend");
    setError("");
    setMessage("");
    try {
      const result = await api.activateBackendPublication();
      applyPublicationSettings(result.settings, { syncTarget: true });
      setMessage("Backend RSS publishing activated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend activation failed");
    } finally {
      setBusy(null);
    }
  }

  async function retryPublication() {
    setBusy("retry");
    setError("");
    setMessage("");
    try {
      const result = await api.retryPublication();
      applyPublicationSettings(result.settings);
      const retryMessage = result.settings.last_publication_status === "failed"
        ? "Publication retry failed."
        : "Publication retry finished.";
      setMessage(retryMessage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Publication retry failed");
    } finally {
      setBusy(null);
    }
  }

  const isBusy = busy !== null;

  return (
    <Modal open={open} onClose={onClose} title="Settings">
      {busy === "loading" ? (
        <p style={{ color: "var(--text-tertiary)" }}>Loading settings...</p>
      ) : (
        <>
          <div className="settings-tabs" role="tablist" aria-label="Settings pages">
            <button
              type="button"
              className={`settings-tab ${tab === "defaults" ? "settings-tab-active" : ""}`}
              onClick={() => setTab("defaults")}
            >
              Feed defaults
            </button>
            <button
              type="button"
              className={`settings-tab ${tab === "publication" ? "settings-tab-active" : ""}`}
              onClick={() => setTab("publication")}
            >
              RSS Publishing
            </button>
          </div>

          {tab === "defaults" ? (
            <form onSubmit={saveDefaults}>
              <p className="settings-intro">
                These values are defaults for new feeds. Existing feeds keep their own settings.
              </p>

              <div className="form-grid">
                <Field
                  full
                  label="Default proxy URL"
                  hint={DEFAULT_PROXY_HINT}
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

              <div className="form-actions settings-actions">
                <div className="settings-actions-primary">
                  <Button disabled={isBusy}>
                    {busy === "save-defaults" ? "Saving..." : "Save settings"}
                  </Button>
                </div>
                <Button
                  className="settings-close-action"
                  variant="ghost"
                  type="button"
                  onClick={onClose}
                  disabled={isBusy}
                >
                  Close
                </Button>
              </div>
            </form>
          ) : (
            <form onSubmit={savePublication}>
              <p className="settings-intro">
                Choose one public RSS target. Backend is the default; GitHub writes static clean and raw feed files.
              </p>

              <PublicationOverview publication={publication} />

              <PublicationTargetSelector
                activeTarget={publication.active_target}
                selectedTarget={publicationTarget}
                onSelect={setPublicationTarget}
              />

              {publicationTarget === PUBLICATION_TARGETS.backend ? (
                <BackendTargetPanel activeTarget={publication.active_target} />
              ) : (
                <GithubTargetPanel
                  form={publicationForm}
                  tokenPresent={publication.github_token_present}
                  onPatch={patchPublication}
                />
              )}

              {error ? <div className="error-msg">{error}</div> : null}
              {message ? <div className="success-msg">{message}</div> : null}

              <PublicationActions
                activeTarget={publication.active_target}
                busy={busy}
                isBusy={isBusy}
                selectedTarget={publicationTarget}
                onActivateBackend={activateBackend}
                onActivateGithub={activateGithub}
                onClose={onClose}
                onRetry={retryPublication}
              />
            </form>
          )}
        </>
      )}
    </Modal>
  );
}

function PublicationTargetSelector({
  activeTarget,
  selectedTarget,
  onSelect
}: {
  activeTarget: PublicationTarget;
  selectedTarget: PublicationTarget;
  onSelect: (target: PublicationTarget) => void;
}) {
  return (
    <div className="publication-target-selector" aria-label="Public RSS target">
      <button
        type="button"
        aria-pressed={selectedTarget === PUBLICATION_TARGETS.backend}
        className={targetOptionClass(selectedTarget === PUBLICATION_TARGETS.backend)}
        onClick={() => onSelect(PUBLICATION_TARGETS.backend)}
      >
        <span>
          <strong>Backend</strong>
          <small>Use the app-hosted RSS endpoint.</small>
        </span>
        {activeTarget === PUBLICATION_TARGETS.backend ? <em>Current</em> : null}
      </button>
      <button
        type="button"
        aria-pressed={selectedTarget === PUBLICATION_TARGETS.github}
        className={targetOptionClass(selectedTarget === PUBLICATION_TARGETS.github)}
        onClick={() => onSelect(PUBLICATION_TARGETS.github)}
      >
        <span>
          <strong>GitHub</strong>
          <small>Publish static RSS files to a repository.</small>
        </span>
        {activeTarget === PUBLICATION_TARGETS.github ? <em>Current</em> : null}
      </button>
    </div>
  );
}

function BackendTargetPanel({ activeTarget }: { activeTarget: PublicationTarget }) {
  return (
    <div className="publication-target-panel">
      <div>
        <h3>Backend endpoint</h3>
        <p>
          RSS URLs are served by this app. No GitHub repository, token, or static hosting setup is required.
        </p>
      </div>
      {activeTarget === PUBLICATION_TARGETS.backend ? (
        <span className="publication-target-current">Current target</span>
      ) : null}
    </div>
  );
}

function GithubTargetPanel({
  form,
  tokenPresent,
  onPatch
}: {
  form: PublicationSettingsForm;
  tokenPresent: boolean;
  onPatch: (update: Partial<PublicationSettingsForm>) => void;
}) {
  const tokenHint = tokenPresent ? GITHUB_TOKEN_PRESENT_HINT : GITHUB_TOKEN_REQUIRED_HINT;
  const tokenPlaceholder = tokenPresent ? "Leave blank to keep existing token" : "GitHub token";

  return (
    <div className="publication-target-panel">
      <div className="form-grid">
        <Field
          full
          label="GitHub repository"
          hint={GITHUB_REPOSITORY_HINT}
        >
          <Input
            value={form.github_repository}
            onChange={(e) => onPatch({ github_repository: e.target.value })}
            placeholder="owner/repo"
          />
        </Field>
        <Field label="Branch" hint={GITHUB_BRANCH_HINT}>
          <Input
            value={form.github_branch}
            onChange={(e) => onPatch({ github_branch: e.target.value })}
            placeholder="main"
          />
        </Field>
        <Field label="Directory" hint="Repository-relative. Empty means repository root.">
          <Input
            value={form.github_directory}
            onChange={(e) => onPatch({ github_directory: e.target.value })}
            placeholder="feeds"
          />
        </Field>
        <Field
          full
          label="RSS_PUBLIC_URL"
          hint={GITHUB_PUBLIC_URL_HINT}
        >
          <Input
            value={form.github_public_url}
            onChange={(e) => onPatch({ github_public_url: e.target.value })}
            placeholder="https://example.com/feeds"
          />
        </Field>
        <Field
          full
          label="GitHub token"
          hint={tokenHint}
        >
          <Input
            type="password"
            value={form.github_token ?? ""}
            onChange={(e) => onPatch({ github_token: e.target.value })}
            placeholder={tokenPlaceholder}
          />
        </Field>
      </div>
    </div>
  );
}

function PublicationActions({
  activeTarget,
  busy,
  isBusy,
  selectedTarget,
  onActivateBackend,
  onActivateGithub,
  onClose,
  onRetry
}: {
  activeTarget: PublicationTarget;
  busy: BusyState;
  isBusy: boolean;
  selectedTarget: PublicationTarget;
  onActivateBackend: () => void;
  onActivateGithub: () => void;
  onClose: () => void;
  onRetry: () => void;
}) {
  return (
    <div className="form-actions settings-actions">
      <div className="settings-actions-primary">
        {selectedTarget === PUBLICATION_TARGETS.github ? (
          <GithubTargetActions
            activeTarget={activeTarget}
            busy={busy}
            isBusy={isBusy}
            onActivate={onActivateGithub}
            onRetry={onRetry}
          />
        ) : (
          <BackendTargetActions
            activeTarget={activeTarget}
            busy={busy}
            isBusy={isBusy}
            onActivate={onActivateBackend}
            onRetry={onRetry}
          />
        )}
      </div>
      <Button
        className="settings-close-action"
        variant="ghost"
        type="button"
        onClick={onClose}
        disabled={isBusy}
      >
        Close
      </Button>
    </div>
  );
}

function GithubTargetActions({
  activeTarget,
  busy,
  isBusy,
  onActivate,
  onRetry
}: {
  activeTarget: PublicationTarget;
  busy: BusyState;
  isBusy: boolean;
  onActivate: () => void;
  onRetry: () => void;
}) {
  return (
    <>
      <Button variant="ghost" type="submit" disabled={isBusy}>
        {busy === "save-publication" ? "Saving..." : "Save GitHub settings"}
      </Button>
      {activeTarget === PUBLICATION_TARGETS.github ? (
        <Button variant="ghost" type="button" onClick={onRetry} disabled={isBusy}>
          {busy === "retry" ? "Publishing..." : "Publish all / Retry"}
        </Button>
      ) : (
        <Button type="button" onClick={onActivate} disabled={isBusy}>
          {busy === "activate-github" ? "Activating..." : "Activate GitHub"}
        </Button>
      )}
    </>
  );
}

function BackendTargetActions({
  activeTarget,
  busy,
  isBusy,
  onActivate,
  onRetry
}: {
  activeTarget: PublicationTarget;
  busy: BusyState;
  isBusy: boolean;
  onActivate: () => void;
  onRetry: () => void;
}) {
  if (activeTarget !== PUBLICATION_TARGETS.backend) {
    return (
      <Button type="button" onClick={onActivate} disabled={isBusy}>
        {busy === "activate-backend" ? "Switching..." : "Switch to backend"}
      </Button>
    );
  }

  return (
    <Button variant="ghost" type="button" onClick={onRetry} disabled={isBusy}>
      {busy === "retry" ? "Publishing..." : "Publish all / Retry"}
    </Button>
  );
}

function PublicationOverview({ publication }: { publication: PublicationSettings }) {
  const latestTime = publication.last_publication_finished_at ?? publication.last_publication_started_at;
  const latestLabel = latestTime ? new Date(latestTime).toLocaleString() : "Never";
  const feedLabel = publication.last_publication_feed_title
    ? `Feed: ${publication.last_publication_feed_title}`
    : "All feeds";

  return (
    <div className="publication-overview">
      <div>
        <span className="publication-overview-label">Active target</span>
        <strong>
          {publication.active_target === PUBLICATION_TARGETS.github ? "GitHub static hosting" : "Backend endpoint"}
        </strong>
      </div>
      <div>
        <span className="publication-overview-label">Latest publication</span>
        <StatusBadge status={publication.last_publication_status} />
      </div>
      <div>
        <span className="publication-overview-label">Finished</span>
        <strong>{latestLabel}</strong>
      </div>
      <div>
        <span className="publication-overview-label">Scope</span>
        <strong>{feedLabel}</strong>
      </div>
      {publication.last_publication_error ? (
        <div className="publication-overview-error">
          {publication.last_publication_error}
        </div>
      ) : null}
    </div>
  );
}
