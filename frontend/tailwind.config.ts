import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['class'],
  theme: {
    extend: {
      colors: {
        bg:       'var(--bg)',
        surface:  'var(--surface)',
        panel:    'var(--panel)',
        card:     'var(--card)',
        border:   'var(--border)',
        accent:   'var(--accent)',
        't1':     'var(--text)',
        't2':     'var(--text-2)',
        't3':     'var(--text-3)',
        success:  'var(--green)',
        warning:  'var(--amber)',
        danger:   'var(--red)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'fade-in':   'fadeIn 0.18s ease-out',
        'slide-up':  'slideUp 0.2s ease-out',
        'blink':     'blink 1s step-start infinite',
        'pulse-ring':'pulseRing 1.4s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:    { '0%': { opacity: '0' },                           '100%': { opacity: '1' } },
        slideUp:   { '0%': { transform: 'translateY(6px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
        blink:     { '0%, 100%': { opacity: '1' },                    '50%': { opacity: '0' } },
        pulseRing: { '0%': { transform: 'scale(1)', opacity: '0.8' }, '70%': { transform: 'scale(1.4)', opacity: '0' }, '100%': { transform: 'scale(1.4)', opacity: '0' } },
      },
    },
  },
  plugins: [],
} satisfies Config;
