import { BarChart3, MessageSquare, Moon, Sun, Zap } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import type { Theme } from '../App';

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
}

const navItems = [
  { to: '/chat',      icon: MessageSquare, label: 'Chat'      },
  { to: '/dashboard', icon: BarChart3,     label: 'Dashboard' },
];

export function Sidebar({ theme, onToggleTheme }: Props) {
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

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
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
