import { useCallback, useRef, useState } from 'react';
import { Upload, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { uploadSpreadsheet, type DataSource } from '../lib/api';

interface UploadedSource extends DataSource {
  message: string;
}

interface Props {
  onUploaded?: (source: UploadedSource) => void;
}

export function FileUpload({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [result, setResult] = useState<UploadedSource | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const upload = useCallback(async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!['csv', 'xlsx', 'xls'].includes(ext)) {
      setErrorMsg('Only CSV and Excel files are supported.');
      setStatus('error');
      return;
    }

    setStatus('uploading');
    setErrorMsg('');
    try {
      const data = await uploadSpreadsheet(file);
      setResult(data);
      setStatus('success');
      onUploaded?.(data);
    } catch (err) {
      setErrorMsg((err as Error).message);
      setStatus('error');
    }
  }, [onUploaded]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) upload(file);
    },
    [upload],
  );

  const reset = () => { setStatus('idle'); setResult(null); setErrorMsg(''); };

  return (
    <div className="w-full">
      {status === 'idle' || status === 'error' ? (
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center gap-2 py-6 px-4 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-150 text-center"
          style={{
            borderColor: dragging ? 'var(--accent)' : 'var(--border)',
            background: dragging ? 'var(--accent-dim)' : 'transparent',
            color: 'var(--text-2)',
          }}
        >
          <Upload size={20} strokeWidth={1.5} style={{ color: dragging ? 'var(--accent)' : 'var(--text-3)' }} />
          <div>
            <p className="text-[13px] font-medium" style={{ color: 'var(--text)' }}>
              Drop file or click to browse
            </p>
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-3)' }}>
              CSV, XLSX, XLS supported
            </p>
          </div>
          {status === 'error' && (
            <p className="text-[12px] flex items-center gap-1.5 mt-1" style={{ color: 'var(--red)' }}>
              <AlertCircle size={13} /> {errorMsg}
            </p>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); }}
          />
        </div>
      ) : status === 'uploading' ? (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-xl border text-[13px]"
          style={{ borderColor: 'var(--border)', background: 'var(--panel)', color: 'var(--text-2)' }}
        >
          <Loader2 size={16} className="animate-spin shrink-0" style={{ color: 'var(--accent)' }} />
          Uploading spreadsheet…
        </div>
      ) : (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-xl border text-[13px]"
          style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
        >
          <CheckCircle size={16} className="shrink-0" style={{ color: 'var(--green)' }} />
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate" style={{ color: 'var(--text)' }}>{result?.filename}</p>
            <p className="text-[11px]" style={{ color: 'var(--text-3)' }}>
              {result?.row_count?.toLocaleString()} rows · {result?.columns?.length} columns
            </p>
          </div>
          <button
            onClick={reset}
            className="shrink-0 rounded-md p-1 hover:opacity-70 transition-opacity"
            style={{ color: 'var(--text-3)' }}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
