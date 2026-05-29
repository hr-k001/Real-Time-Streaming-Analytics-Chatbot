import { useEffect, useState } from 'react';
import { BarChart3, MessageSquare, Moon, Plus, Sun, Zap } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import type { Theme } from '../App';
import { getChatHistory, type ChatSession } from '../lib/api';

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
  activeChatId: string | null;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
}

function relativeDate(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / 86_400_000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

const navItems = [
  { to: '/chat',      icon: MessageSquare, label: 'Chat'      },
  { to: '/dashboard', icon: BarChart3,     label: 'Dashboard' },
];

export function Sidebar({ theme, onToggleTheme, activeChatId, onSelectChat, onNewChat }: Props) {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  // Fetch history on mount and whenever the active chat changes (new chat was created)
  useEffect(() => {
    getChatHistory()
      .then(r => setSessions(r.sessions))
      .catch(() => {});
  }, [activeChatId]);

  const handleSelectSession = (chatId: string) => {
    onSelectChat(chatId);
    navigate('/chat');
  };

  const handleNewChat = () => {
    onNewChat();
    navigate('/chat');
  };

  return (
    <aside
      className="flex flex-col shrink-0 w-[220px] border-r h-full"
      style={{
        background: 'var(--surface)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2.5 px-5 py-5 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <div
          className="flex items-center justify-center w-8 h-8 rounded-lg"
          style={{ background: 'var(--accent)', boxShadow: '0 0 12px var(--accent-dim)' }}
        >
          <Zap size={16} className="text-white" strokeWidth={2.5} />
        </div>
        <div>
          <p className="font-semibold text-[13px] leading-tight" style={{ color: 'var(--text)' }}>
            Analytics
          </p>
          <p className="text-[11px]" style={{ color: 'var(--text-3)' }}>
            AI Chatbot
          </p>
        </div>
      </div>

      {/* Navigation + History — scrollable */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        <p
          className="text-[10px] font-semibold uppercase tracking-widest px-2 pt-1 pb-2"
          style={{ color: 'var(--text-3)' }}
        >
          Workspace
        </p>
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150',
                isActive
                  ? 'text-white'
                  : 'hover:bg-[var(--panel)]',
              ].join(' ')
            }
            style={({ isActive }) =>
              isActive
                ? { background: 'var(--accent)', color: 'white' }
                : { color: 'var(--text-2)' }
            }
          >
            <Icon size={16} strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}

        {/* Chat History */}
        <div className="pt-3">
          <div className="flex items-center justify-between px-2 pb-2">
            <p
              className="text-[10px] font-semibold uppercase tracking-widest"
              style={{ color: 'var(--text-3)' }}
            >
              History
            </p>
            <button
              onClick={handleNewChat}
              title="New chat"
              className="flex items-center justify-center w-5 h-5 rounded hover:opacity-80 transition-opacity"
              style={{ color: 'var(--text-3)' }}
            >
              <Plus size={13} strokeWidth={2} />
            </button>
          </div>

          {sessions.length === 0 ? (
            <p className="px-2 text-[11px]" style={{ color: 'var(--text-3)' }}>
              No history yet
            </p>
          ) : (
            <ul className="space-y-0.5">
              {sessions.map(s => (
                <li key={s.chat_id}>
                  <button
                    onClick={() => handleSelectSession(s.chat_id)}
                    className="w-full text-left px-3 py-2 rounded-lg text-[12px] transition-all duration-150 hover:bg-[var(--panel)]"
                    style={{
                      background: activeChatId === s.chat_id ? 'var(--panel)' : 'transparent',
                      color: activeChatId === s.chat_id ? 'var(--text)' : 'var(--text-2)',
                      borderLeft: activeChatId === s.chat_id
                        ? '2px solid var(--accent)'
                        : '2px solid transparent',
                    }}
                  >
                    <div className="truncate font-medium leading-snug">{s.title}</div>
                    <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-3)' }}>
                      {relativeDate(s.updated_at)}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </nav>

      {/* Bottom section */}
      <div
        className="p-3 border-t space-y-1"
        style={{ borderColor: 'var(--border)' }}
      >
        {/* Theme toggle */}
        <button
          onClick={onToggleTheme}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 hover:bg-[var(--panel)]"
          style={{ color: 'var(--text-2)' }}
        >
          {theme === 'dark' ? <Sun size={16} strokeWidth={1.75} /> : <Moon size={16} strokeWidth={1.75} />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>

        {/* Version badge */}
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-[11px]" style={{ color: 'var(--text-3)' }}>
            API
          </span>
          <span
            className="text-[10px] font-mono px-1.5 py-0.5 rounded"
            style={{
              background: 'var(--accent-dim)',
              color: 'var(--accent)',
              border: '1px solid var(--accent-dim)',
            }}
          >
            v0.1
          </span>
        </div>
      </div>
    </aside>
  );
}
