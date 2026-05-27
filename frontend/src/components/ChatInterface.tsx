import { useEffect, useRef, useState, useCallback } from 'react';
import { Send, Square, Trash2, FileDown, Paperclip, X } from 'lucide-react';
import { useSSEChat } from '../hooks/useSSEChat';
import { MessageBubble } from './MessageBubble';
import { VoiceInput } from './VoiceInput';
import { FileUpload } from './FileUpload';
import { generateReport } from '../lib/api';

export function ChatInterface() {
  const { chatId, messages, isStreaming, error, sendMessage, stop, clear } = useSSEChat();
  const [input, setInput] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const bottomRef  = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const submit = useCallback(() => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');
    setReportUrl(null);
    sendMessage(text);
  }, [input, isStreaming, sendMessage]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
    if (e.key === 'Escape' && isStreaming) stop();
  };

  const onVoiceResult = useCallback(
    (transcript: string, answer: string) => {
      // Voice query already ran through the agent; add messages manually
      if (transcript) sendMessage(transcript);
      void answer; // answer is already sent via the API; SSE will handle display
    },
    [sendMessage],
  );

  const handleGenerateReport = useCallback(async () => {
    if (!chatId || generatingReport) return;
    setGeneratingReport(true);
    try {
      const res = await generateReport(chatId, 'Chat Session Report');
      setReportUrl(res.download_url);
    } catch (err) {
      console.error('Report generation failed:', err);
    } finally {
      setGeneratingReport(false);
    }
  }, [chatId, generatingReport]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b shrink-0"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-[15px] font-semibold" style={{ color: 'var(--text)' }}>
            Chat
          </h1>
          {chatId && (
            <span
              className="text-[11px] font-mono px-2 py-0.5 rounded-md"
              style={{ background: 'var(--panel)', color: 'var(--text-3)', border: '1px solid var(--border)' }}
            >
              #{chatId.slice(0, 8)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Report download */}
          {reportUrl && (
            <a
              href={reportUrl}
              download
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all"
              style={{ background: 'var(--accent-dim)', color: 'var(--accent)', border: '1px solid var(--accent-dim)' }}
            >
              <FileDown size={13} /> Download PDF
            </a>
          )}
          {chatId && messages.length > 0 && !reportUrl && (
            <button
              onClick={handleGenerateReport}
              disabled={generatingReport}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all disabled:opacity-50 hover:opacity-80"
              style={{ background: 'var(--panel)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
            >
              <FileDown size={13} />
              {generatingReport ? 'Generating…' : 'Export PDF'}
            </button>
          )}
          {messages.length > 0 && (
            <button
              onClick={clear}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all hover:opacity-80"
              style={{ background: 'var(--panel)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
            >
              <Trash2 size={13} /> Clear
            </button>
          )}
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {isEmpty ? (
          <WelcomeScreen onSend={sendMessage} disabled={isStreaming} />
        ) : (
          messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)
        )}
        {error && (
          <div
            className="flex items-center gap-2 px-4 py-3 rounded-lg text-[13px] border"
            style={{ background: 'rgba(248,113,113,0.08)', borderColor: 'var(--red)', color: 'var(--red)' }}
          >
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* File upload panel */}
      {showUpload && (
        <div
          className="px-6 py-3 border-t"
          style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12px] font-medium" style={{ color: 'var(--text-2)' }}>
              Upload Spreadsheet
            </span>
            <button onClick={() => setShowUpload(false)} style={{ color: 'var(--text-3)' }}>
              <X size={14} />
            </button>
          </div>
          <FileUpload
            onUploaded={src => {
              setShowUpload(false);
              sendMessage(
                `I've uploaded a spreadsheet "${src.filename}" (${src.row_count} rows, source_id: ${src.source_id}). ` +
                  `Columns: ${src.columns.map(c => c.name).join(', ')}. Please help me analyze it.`,
              );
            }}
          />
        </div>
      )}

      {/* Input bar */}
      <div
        className="px-4 py-3 border-t shrink-0"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
      >
        <div
          className="flex items-end gap-2 rounded-xl border px-3 py-2 transition-all"
          style={{
            background: 'var(--panel)',
            borderColor: 'var(--border)',
          }}
        >
          {/* Attachment button */}
          <button
            onClick={() => setShowUpload(v => !v)}
            title="Upload spreadsheet"
            className="mb-1 flex items-center justify-center w-8 h-8 rounded-lg transition-all hover:opacity-80 shrink-0"
            style={{
              background: showUpload ? 'var(--accent-dim)' : 'transparent',
              color: showUpload ? 'var(--accent)' : 'var(--text-3)',
            }}
          >
            <Paperclip size={15} strokeWidth={1.75} />
          </button>

          {/* Text input */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question about your data… (Shift+Enter for new line)"
            rows={1}
            className="flex-1 resize-none bg-transparent outline-none text-[13.5px] leading-relaxed placeholder:opacity-50"
            style={{ color: 'var(--text)', maxHeight: 160 }}
          />

          {/* Voice */}
          <div className="mb-1 shrink-0">
            <VoiceInput chatId={chatId} onResult={onVoiceResult} disabled={isStreaming} />
          </div>

          {/* Send / Stop */}
          <button
            onClick={isStreaming ? stop : submit}
            disabled={!isStreaming && !input.trim()}
            className="mb-1 flex items-center justify-center w-9 h-9 rounded-xl transition-all disabled:opacity-30 shrink-0"
            style={{
              background: isStreaming ? 'var(--red)' : 'var(--accent)',
              color: '#fff',
            }}
          >
            {isStreaming ? <Square size={14} strokeWidth={2.5} /> : <Send size={14} strokeWidth={2} />}
          </button>
        </div>
        <p className="text-[11px] text-center mt-1.5" style={{ color: 'var(--text-3)' }}>
          Enter to send · Shift+Enter for new line · Esc to stop
        </p>
      </div>
    </div>
  );
}

function WelcomeScreen({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
}) {
  const suggestions = [
    'Show me the top 10 products by revenue',
    'What are the sales trends over the last 30 days?',
    'Are there any anomalies in the order data?',
    'Summarize the sales data by region',
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 py-16 text-center">
      <div>
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
          style={{ background: 'var(--accent-dim)', border: '1px solid var(--border)' }}
        >
          <span className="text-2xl">⚡</span>
        </div>
        <h2 className="text-xl font-semibold mb-1" style={{ color: 'var(--text)' }}>
          Start a conversation
        </h2>
        <p className="text-[13px]" style={{ color: 'var(--text-2)' }}>
          Ask anything about your Azure SQL data
        </p>
      </div>

      <div className="grid grid-cols-1 gap-2 w-full max-w-md">
        {suggestions.map(s => (
          <button
            key={s}
            onClick={() => !disabled && onSend(s)}
            disabled={disabled}
            className="px-4 py-2.5 rounded-xl border text-left text-[13px] transition-all hover:opacity-80 disabled:opacity-40"
            style={{
              background: 'var(--card)',
              borderColor: 'var(--border)',
              color: 'var(--text-2)',
            }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
