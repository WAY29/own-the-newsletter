export type SyncStatus = {
  first_sync_completed: boolean;
  last_sync_started_at: string | null;
  last_sync_finished_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  last_sync_imported_count: number;
  last_sync_skipped_count: number;
};

export type Feed = {
  id: number;
  title: string;
  recipient: string;
  imap_host: string;
  imap_port: number;
  imap_tls: "ssl" | "starttls" | "none";
  imap_username: string;
  folders: string[];
  random_slug: string;
  feed_url: string;
  raw_feed_url: string;
  backfill_days: number;
  retention_count: number;
  sync_interval_minutes: number;
  created_at: string;
  updated_at: string;
  sync_status: SyncStatus;
};

export type FeedForm = {
  title: string;
  recipient: string;
  imap_host: string;
  imap_port: number;
  imap_tls: "ssl" | "starttls" | "none";
  imap_username: string;
  imap_password: string;
  folders: string[];
  backfill_days: number;
  retention_count: number;
  sync_interval_minutes: number;
};

export type PreviewResult = {
  match_count: number;
  scanned_count: number;
  samples: Array<{
    folder: string;
    uid: string;
    subject: string;
    author: string;
    published_at: string;
  }>;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    },
    ...options
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep the status message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  me: () => request<{ authenticated: boolean }>("/api/auth/me"),
  login: (token: string) =>
    request<{ authenticated: boolean; expires_at: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ token })
    }),
  logout: () => request<{ authenticated: boolean }>("/api/auth/logout", { method: "POST" }),
  listFeeds: () => request<{ feeds: Feed[] }>("/api/feeds"),
  createFeed: (feed: FeedForm) =>
    request<{ feed: Feed }>("/api/feeds", {
      method: "POST",
      body: JSON.stringify(feed)
    }),
  updateFeed: (id: number, feed: Partial<FeedForm>) =>
    request<{ feed: Feed }>(`/api/feeds/${id}`, {
      method: "PUT",
      body: JSON.stringify(feed)
    }),
  deleteFeed: (id: number) =>
    request<{ deleted: boolean }>(`/api/feeds/${id}`, {
      method: "DELETE"
    }),
  preview: (feed: FeedForm) =>
    request<PreviewResult>("/api/feeds/preview", {
      method: "POST",
      body: JSON.stringify({ ...feed, limit_per_folder: 50 })
    }),
  syncFeed: (id: number) =>
    request<{ status: string; imported_count: number; skipped_count: number; error?: string }>(
      `/api/feeds/${id}/sync`,
      { method: "POST" }
    )
};
