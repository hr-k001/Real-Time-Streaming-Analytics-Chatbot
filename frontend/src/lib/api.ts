const BASE = import.meta.env.VITE_API_URL ?? '';

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Chat ───────────────────────────────────────────────────────────────────────

export interface ChatResponse {
  chat_id: string;
  answer: string;
  tool_calls: { name: string; input: object; output: object; error: string | null }[];
  chart: { content: string } | null;
  data: { content: string } | null;
  from_cache: boolean;
}

export const chatStream = (message: string, chatId?: string | null): Promise<Response> =>
  fetch(`${BASE}/api/chat/stream2`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, chat_id: chatId ?? undefined }),
  });

// ── Cache ──────────────────────────────────────────────────────────────────────

export interface CacheStats {
  hits: number;
  misses: number;
  entries: number;
  hit_rate_pct: number;
}

export interface FreshnessEntry {
  key: string;
  sql: string;
  elapsed_pct: number;
  remaining_seconds: number;
}

export const getCacheStats = (): Promise<CacheStats> =>
  fetch(`${BASE}/api/cache/stats`).then(r => json<CacheStats>(r));

export const getCacheFreshness = (): Promise<{ near_expiry_count: number; entries: FreshnessEntry[] }> =>
  fetch(`${BASE}/api/cache/freshness`).then(r => json(r));

export const flushCache = (): Promise<{ flushed: number }> =>
  fetch(`${BASE}/api/cache/flush`, { method: 'POST' }).then(r => json(r));

// ── Data sources ───────────────────────────────────────────────────────────────

export interface ColumnInfo { name: string; dtype: string; }

export interface DataSource {
  source_id: string;
  filename: string;
  row_count: number;
  columns: ColumnInfo[];
}

export const getDataSources = (): Promise<{ count: number; sources: DataSource[] }> =>
  fetch(`${BASE}/api/data-sources`).then(r => json(r));

export const uploadSpreadsheet = (file: File): Promise<DataSource & { message: string }> => {
  const form = new FormData();
  form.append('file', file);
  return fetch(`${BASE}/api/upload/spreadsheet`, { method: 'POST', body: form }).then(r => json(r));
};

export const deleteDataSource = (sourceId: string): Promise<{ status: string }> =>
  fetch(`${BASE}/api/data-sources/${sourceId}`, { method: 'DELETE' }).then(r => json(r));

export const queryDataSource = (
  sourceId: string,
  question: string,
  limit = 100,
): Promise<DataSource & { rows: Record<string, unknown>[]; question: string }> =>
  fetch(`${BASE}/api/data-sources/${sourceId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, limit }),
  }).then(r => json(r));

// ── Voice ──────────────────────────────────────────────────────────────────────

export const voiceQuery = (
  audio: Blob,
  chatId?: string | null,
): Promise<ChatResponse & { transcript: string; source: string }> => {
  const form = new FormData();
  form.append('file', audio, 'recording.webm');
  if (chatId) form.append('chat_id', chatId);
  return fetch(`${BASE}/api/voice/query`, { method: 'POST', body: form }).then(r => json(r));
};

// ── Reports ────────────────────────────────────────────────────────────────────

export const generateReport = (
  chatId: string,
  title?: string,
): Promise<{ report_id: string; title: string; download_url: string }> =>
  fetch(`${BASE}/api/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, title }),
  }).then(r => json(r));

export const reportDownloadUrl = (reportId: string) => `${BASE}/api/reports/${reportId}`;

// ── Analytics ──────────────────────────────────────────────────────────────────

export const detectAnomalies = (
  rows: Record<string, unknown>[],
  columns: string[],
  column?: string,
  method?: 'auto' | 'zscore' | 'iqr',
): Promise<unknown> =>
  fetch(`${BASE}/api/analytics/anomaly`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows, columns, column, method }),
  }).then(r => json(r));
