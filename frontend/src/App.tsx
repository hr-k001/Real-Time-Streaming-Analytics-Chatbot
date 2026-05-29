import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';

export type Theme = 'dark' | 'light';

function App() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem('theme');
    return (stored === 'light' ? 'light' : 'dark') as Theme;
  });
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  // Incrementing this key causes ChatInterface to remount (fresh state)
  const [chatKey, setChatKey] = useState(0);

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light');
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'));

  const handleSelectChat = (chatId: string) => setActiveChatId(chatId);

  const handleNewChat = () => {
    setActiveChatId(null);
    setChatKey(k => k + 1);
  };

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
        <Sidebar
          theme={theme}
          onToggleTheme={toggleTheme}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
        />
        <main className="flex-1 overflow-hidden flex flex-col min-w-0">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route
              path="/chat"
              element={
                <ChatInterface
                  key={chatKey}
                  activeChatId={activeChatId}
                  onChatIdChange={setActiveChatId}
                />
              }
            />
            <Route path="/dashboard" element={<AnalyticsDashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
