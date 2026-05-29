import { useCallback, useEffect, useState } from 'react';
import {
  BarChart3,
  Database,
  RefreshCw,
  Trash2,
  Upload,
  Zap,
  Clock,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  X,
} from 'lucide-react';
import {
  getCacheStats,
  getCacheFreshness,
  flushCache,
  getDataSources,
  deleteDataSource,
  queryDataSource,
  type CacheStats,
  type FreshnessEntry,
  type DataSource,
} from '../lib/api';
import { FileUpload } from './FileUpload';

// ── Small stat card ────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div
      className="rounded-xl p-4 border flex flex-col gap-3"
      style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
    >
      <div className="flex items-center justify-between">
        <span
          className="flex items-center justify-center w-8 h-8 rounded-lg"
          style={{ background: accent ? 'var(--accent-dim)' : 'var(--panel)', color: accent ? 'var(--accent)' : 'var(--text-2)' }}
        >
          {icon}
        </span>
        {sub && (
          <span className="text-[11px]" style={{ color: 'var(--text-3)' }}>
            {sub}
          </span>
        )}
      </div>
      <div>
        <p className="text-2xl font-semibold" style={{ color: 'var(--text)' }}>
          {value}
        </p>
        <p className="text-[12px]" style={{ color: 'var(--text-2)' }}>
          {label}
        </p>
      </div>
    </div>
  );
}

// ── Section header ─────────────────────────────────────────────────────────────

function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-[13px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-3)' }}>
        {title}
      </h2>
      {action}
    </div>
  );
}

// ── Main dashboard ─────────────────────────────────────────────────────────────

export function AnalyticsDashboard() {
  const [stats, setStats]   = useState<CacheStats | null>(null);
  const [fresh, setFresh]   = useState<FreshnessEntry[]>([]);
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState('');
  const [flushing, setFlushing] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [previewSource, setPreviewSource] = useState<string | null>(null);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [previewCols, setPreviewCols] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [s, f, d] = await Promise.all([
        getCacheStats(),
        getCacheFreshness(),
        getDataSources(),
      ]);
      setStats(s);
      setFresh(f.entries);
      setSources(d.sources);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleFlush = async () => {
    setFlushing(true);
    try {
      await flushCache();
      await load();
    } finally {
      setFlushing(false);
    }
  };

  const handleDeleteSource = async (id: string) => {
    await deleteDataSource(id);
    setSources(s => s.filter(x => x.source_id !== id));
    if (previewSource === id) setPreviewSource(null);
  };

  const handlePreview = async (id: string, cols: string[]) => {
    if (previewSource === id) { setPreviewSource(null); return; }
    try {
      const res = await queryDataSource(id, '', 10);
      setPreviewRows(res.rows);
      setPreviewCols(cols.map(c => (typeof c === 'string' ? c : (c as { name: string }).name)));
      setPreviewSource(id);
    } catch { /* ignore */ }
  };

  const hitRate = stats ? Math.round(stats.hit_rate_pct ?? 0) : 0;

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: 'var(--bg)' }}
    >
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b sticky top-0 z-10"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
      >
        <h1 className="text-[15px] font-semibold" style={{ color: 'var(--text)' }}>
          Dashboard
        </h1>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all hover:opacity-80 disabled:opacity-40"
          style={{ background: 'var(--panel)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </header>

      <div className="p-6 space-y-8 max-w-5xl mx-auto">
        {error && (
          <div
            className="flex items-center gap-2 px-4 py-3 rounded-xl border text-[13px]"
            style={{ background: 'rgba(248,113,113,0.08)', borderColor: 'var(--red)', color: 'var(--red)' }}
          >
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* Cache stats */}
        <section>
          <SectionHeader
            title="Query Cache"
            action={
              <button
                onClick={handleFlush}
                disabled={flushing || loading}
                className="flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-lg transition-all hover:opacity-80 disabled:opacity-40"
                style={{ background: 'var(--panel)', color: 'var(--red)', border: '1px solid var(--border)' }}
              >
                <Trash2 size={12} /> {flushing ? 'Flushing…' : 'Flush'}
              </button>
            }
          />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard
              icon={<TrendingUp size={16} />}
              label="Cache hit rate"
              value={`${hitRate}%`}
              accent={hitRate > 50}
            />
            <StatCard
              icon={<CheckCircle size={16} />}
              label="Cache hits"
              value={stats?.hits ?? '—'}
            />
            <StatCard
              icon={<Zap size={16} />}
              label="Cache misses"
              value={stats?.misses ?? '—'}
            />
            <StatCard
              icon={<Database size={16} />}
              label="Cached entries"
              value={stats?.entries ?? '—'}
            />
          </div>
        </section>

        {/* Near-expiry keys */}
        {fresh.length > 0 && (
          <section>
            <SectionHeader title={`Near Expiry (${fresh.length})`} />
            <div className="space-y-2">
              {fresh.map((entry, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl border text-[12px]"
                  style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
                >
                  <Clock size={14} style={{ color: 'var(--amber)', flexShrink: 0 }} />
                  <span
                    className="flex-1 font-mono truncate"
                    style={{ color: 'var(--text-2)' }}
                  >
                    {entry.sql}
                  </span>
                  <span
                    className="shrink-0 px-2 py-0.5 rounded-full text-[11px]"
                    style={{ background: 'rgba(251,191,36,0.1)', color: 'var(--amber)' }}
                  >
                    {Math.round(entry.remaining_seconds)}s left
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Data sources */}
        <section>
          <SectionHeader
            title={`Data Sources (${sources.length})`}
            action={
              <button
                onClick={() => setShowUpload(v => !v)}
                className="flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-lg transition-all hover:opacity-80"
                style={{ background: 'var(--accent-dim)', color: 'var(--accent)', border: '1px solid var(--accent-dim)' }}
              >
                <Upload size={12} /> Upload
              </button>
            }
          />

          {showUpload && (
            <div className="mb-4">
              <FileUpload
                onUploaded={src => {
                  setSources(s => [...s, src]);
                  setShowUpload(false);
                }}
              />
            </div>
          )}

          {sources.length === 0 ? (
            <EmptyState
              icon={<Database size={24} strokeWidth={1.5} />}
              message="No spreadsheets uploaded yet"
              sub="Upload a CSV or Excel file to start querying it"
            />
          ) : (
            <div className="space-y-2">
              {sources.map(src => {
                const cols = src.columns ?? [];
                return (
                  <div
                    key={src.source_id}
                    className="rounded-xl border overflow-hidden"
                    style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
                  >
                    <div className="flex items-center gap-3 px-4 py-3">
                      <Database size={15} strokeWidth={1.5} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-medium truncate" style={{ color: 'var(--text)' }}>
                          {src.filename}
                        </p>
                        <p className="text-[11px]" style={{ color: 'var(--text-3)' }}>
                          {src.row_count?.toLocaleString()} rows ·{' '}
                          {cols.map(c => (typeof c === 'string' ? c : c.name)).join(', ')}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => handlePreview(src.source_id, cols.map(c => typeof c === 'string' ? c : c.name))}
                          className="px-2.5 py-1 rounded-lg text-[11px] transition-all hover:opacity-80"
                          style={{ background: 'var(--panel)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
                        >
                          {previewSource === src.source_id ? 'Hide' : 'Preview'}
                        </button>
                        <button
                          onClick={() => handleDeleteSource(src.source_id)}
                          className="p-1.5 rounded-lg transition-all hover:opacity-80"
                          style={{ color: 'var(--text-3)' }}
                        >
                          <X size={13} />
                        </button>
                      </div>
                    </div>

                    {previewSource === src.source_id && previewRows.length > 0 && (
                      <DataTable columns={previewCols} rows={previewRows} />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* System info */}
        <section>
          <SectionHeader title="System" />
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            <StatCard icon={<BarChart3 size={16} />} label="Registered tools" value={11} />
            <StatCard icon={<Zap size={16} />} label="LLM model" value="llama-3.3-70b" />
            <StatCard icon={<Database size={16} />} label="Data warehouse" value="Azure SQL" />
          </div>
        </section>
      </div>
    </div>
  );
}

// ── Data table ─────────────────────────────────────────────────────────────────

function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
}) {
  return (
    <div
      className="border-t overflow-x-auto"
      style={{ borderColor: 'var(--border)' }}
    >
      <table className="w-full text-[12px]">
        <thead>
          <tr style={{ background: 'var(--panel)' }}>
            {columns.map(col => (
              <th
                key={col}
                className="px-3 py-2 text-left font-semibold whitespace-nowrap"
                style={{ color: 'var(--text-2)', borderBottom: '1px solid var(--border)' }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              style={{ background: i % 2 === 0 ? 'transparent' : 'var(--panel)' }}
            >
              {columns.map(col => (
                <td
                  key={col}
                  className="px-3 py-2 whitespace-nowrap font-mono"
                  style={{ color: 'var(--text)', borderBottom: '1px solid var(--border)' }}
                >
                  {String(row[col] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────

function EmptyState({
  icon,
  message,
  sub,
}: {
  icon: React.ReactNode;
  message: string;
  sub?: string;
}) {
  return (
    <div
      className="flex flex-col items-center gap-2 py-10 rounded-xl border text-center"
      style={{ borderColor: 'var(--border)', color: 'var(--text-3)' }}
    >
      {icon}
      <p className="text-[13px] font-medium" style={{ color: 'var(--text-2)' }}>
        {message}
      </p>
      {sub && <p className="text-[12px]">{sub}</p>}
    </div>
  );
}
