import { useState } from 'react';
import { ChevronDown, ChevronRight, Database, BarChart3, Cpu } from 'lucide-react';
import type { Message, ToolCall } from '../hooks/useSSEChat';
import { ChartDisplay } from './ChartDisplay';

const TOOL_ICONS: Record<string, React.ReactNode> = {
  sql_executor:       <Database size={13} strokeWidth={1.75} />,
  dynamic_chart:      <BarChart3 size={13} strokeWidth={1.75} />,
  plotly_viz:         <BarChart3 size={13} strokeWidth={1.75} />,
  chart_generator:    <BarChart3 size={13} strokeWidth={1.75} />,
  anomaly_detector:   <Cpu size={13} strokeWidth={1.75} />,
  spreadsheet_query:  <Database size={13} strokeWidth={1.75} />,
};

function ToolAccordion({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);
  const icon = TOOL_ICONS[call.name] ?? <Cpu size={13} strokeWidth={1.75} />;

  return (
    <div
      className="rounded-lg border text-[12px] overflow-hidden mb-1.5"
      style={{ borderColor: 'var(--border)', background: 'var(--panel)' }}
    >
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left transition-all duration-150 hover:opacity-80"
        style={{ color: 'var(--text-2)' }}
      >
        <span style={{ color: 'var(--accent)' }}>{icon}</span>
        <span className="font-medium font-mono">{call.name}</span>
        {!call.summary && (
          <span
            className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full animate-pulse"
            style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}
          >
            running
          </span>
        )}
        {call.summary && (
          <span className="ml-auto" style={{ color: 'var(--text-3)' }}>
            {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        )}
      </button>
      {open && call.summary && (
        <div
          className="px-3 pb-3 font-mono text-[11px] leading-relaxed border-t"
          style={{ borderColor: 'var(--border)', color: 'var(--text-3)' }}
        >
          <pre className="whitespace-pre-wrap break-all mt-2">{call.summary}</pre>
        </div>
      )}
    </div>
  );
}

function UserBubble({ msg }: { msg: Message }) {
  return (
    <div className="flex justify-end animate-slide-up">
      <div
        className="max-w-[75%] px-4 py-3 rounded-2xl rounded-tr-sm text-[13.5px] leading-relaxed"
        style={{ background: 'var(--user-bg)', color: 'var(--text)' }}
      >
        {msg.content}
      </div>
    </div>
  );
}

function AssistantBubble({ msg }: { msg: Message }) {
  return (
    <div className="flex flex-col gap-1.5 animate-slide-up">
      {/* Tool calls */}
      {(msg.toolCalls ?? []).length > 0 && (
        <div className="space-y-0.5">
          {msg.toolCalls!.map((call, i) => (
            <ToolAccordion key={i} call={call} />
          ))}
        </div>
      )}

      {/* Answer */}
      <div
        className="max-w-[85%] px-4 py-3 rounded-2xl rounded-tl-sm text-[13.5px] leading-relaxed"
        style={{ background: 'var(--asst-bg)', color: 'var(--text)' }}
      >
        {msg.content ? (
          <div
            className={`prose-chat${msg.isStreaming ? ' cursor-stream' : ''}`}
            dangerouslySetInnerHTML={{
              __html: formatContent(msg.content),
            }}
          />
        ) : (
          msg.isStreaming && (
            <span className="inline-flex items-center gap-1.5" style={{ color: 'var(--text-3)' }}>
              <span className="animate-pulse">Thinking</span>
              <span className="flex gap-0.5">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1 h-1 rounded-full animate-bounce"
                    style={{
                      background: 'var(--accent)',
                      animationDelay: `${i * 0.15}s`,
                    }}
                  />
                ))}
              </span>
            </span>
          )
        )}

        {/* Chart rendered from the dedicated chart SSE event */}
        {msg.chartFigure && !msg.isStreaming && (
          <ChartDisplay figure={msg.chartFigure} />
        )}
      </div>
    </div>
  );
}

// Very lightweight markdown→html: bold, inline code, newlines → <br>
function formatContent(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>');
}

export function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === 'user') return <UserBubble msg={msg} />;
  return <AssistantBubble msg={msg} />;
}
