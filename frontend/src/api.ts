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
  sender: string;
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
  item_count: number;
};

export type FeedSortBy = "created_at" | "updated_at" | "title" | "item_count" | "last_sync";
export type FeedSortDir = "asc" | "desc";

export type FeedListPagination = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type FeedListParams = {
  page?: number;
  page_size?: number;
  sort_by?: FeedSortBy;
  sort_dir?: FeedSortDir;
};

export type FeedListResponse = {
  feeds: Feed[];
  pagination: FeedListPagination;
  sort: {
    sort_by: FeedSortBy;
    sort_dir: FeedSortDir;
  };
};

export type FeedForm = {
  title: string;
  sender: string;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatErrorLocation(loc: unknown): string {
  if (!Array.isArray(loc)) return "";

  return loc
    .filter((part): part is string | number => typeof part === "string" || typeof part === "number")
    .map((part) => String(part))
    .filter((part) => !["body", "query", "path"].includes(part))
    .join(".");
}

function stringFromErrorRecord(record: Record<string, unknown>): string | null {
  for (const key of ["msg", "message", "error"]) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

function jsonFallback(value: unknown): string | null {
  try {
    return JSON.stringify(value) ?? null;
  } catch {
    return null;
  }
}

function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (typeof detail === "number" || typeof detail === "boolean") return String(detail);

  if (Array.isArray(detail)) {
    const messages = detail
      .map(formatErrorDetail)
      .filter((message): message is string => Boolean(message?.trim()));
    return messages.length > 0 ? messages.join("\n") : null;
  }

  if (isRecord(detail)) {
    const message = stringFromErrorRecord(detail);
    if (message) {
      const location = formatErrorLocation(detail.loc);
      return location ? `${location}: ${message}` : message;
    }

    const nestedDetail = formatErrorDetail(detail.detail);
    if (nestedDetail) return nestedDetail;

    return jsonFallback(detail);
  }

  return null;
}

function formatResponseError(body: unknown, fallback: string): string {
  if (isRecord(body)) {
    return (
      formatErrorDetail(body.detail) ??
      stringFromErrorRecord(body) ??
      formatErrorDetail(body.errors) ??
      fallback
    );
  }

  return formatErrorDetail(body) ?? fallback;
}

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
      message = formatResponseError(body, message);
    } catch {
      // Keep the status message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function queryString(params: FeedListParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const api = {
  me: () => request<{ authenticated: boolean }>("/api/auth/me"),
  login: (token: string) =>
    request<{ authenticated: boolean; expires_at: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ token })
    }),
  logout: () => request<{ authenticated: boolean }>("/api/auth/logout", { method: "POST" }),
  listFeeds: (params: FeedListParams = {}) => request<FeedListResponse>(`/api/feeds${queryString(params)}`),
  getFeed: (id: number) => request<{ feed: Feed }>(`/api/feeds/${id}`),
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
