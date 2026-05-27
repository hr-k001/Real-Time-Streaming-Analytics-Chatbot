import { useCallback, useRef, useState } from 'react';
import { chatStream } from '../lib/api';

export interface ToolCall {
  name: string;
  summary: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
  chartFigure?: Record<string, unknown>;
}

export interface SSEState {
  chatId: string | null;
  messages: Message[];
  isStreaming: boolean;
  error: string | null;
}

function uid() {
  return Math.random().toString(36).slice(2);
}

// Parse SSE frames from raw text chunks.
// Each frame is separated by "\n\n" and has "event:" + "data:" lines.
function* parseFrames(text: string): Generator<{ event: string; data: string }> {
  for (const frame of text.split('\n\n')) {
    if (!frame.trim()) continue;
    let event = 'message';
    let data = '';
    for (const line of frame.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice(7).trim();
      else if (line.startsWith('data: ')) data = line.slice(6);
    }
    yield { event, data };
  }
}

export function useSSEChat() {
  const [state, setState] = useState<SSEState>({
    chatId: null,
    messages: [],
    isStreaming: false,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);

  // Update only the last message in the list
  const patchLast = (patch: Partial<Message>) =>
    setState(prev => ({
      ...prev,
      messages: prev.messages.map((m, i) =>
        i === prev.messages.length - 1 ? { ...m, ...patch } : m,
      ),
    }));

  const sendMessage = useCallback(
    async (text: string) => {
      if (state.isStreaming) return;

      const userMsg: Message = { id: uid(), role: 'user', content: text };
      const assistantMsg: Message = {
        id: uid(),
        role: 'assistant',
        content: '',
        toolCalls: [],
        isStreaming: true,
      };

      setState(prev => ({
        ...prev,
        isStreaming: true,
        error: null,
        messages: [...prev.messages, userMsg, assistantMsg],
      }));

      abortRef.current = new AbortController();

      try {
        const response = await chatStream(text, state.chatId);
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Keep the incomplete trailing frame in buffer
          const boundary = buffer.lastIndexOf('\n\n');
          if (boundary === -1) continue;

          const complete = buffer.slice(0, boundary + 2);
          buffer = buffer.slice(boundary + 2);

          for (const { event, data } of parseFrames(complete)) {
            if (event === 'chat_id') {
              setState(prev => ({ ...prev, chatId: data }));
            } else if (event === 'token') {
              setState(prev => ({
                ...prev,
                messages: prev.messages.map((m, i) =>
                  i === prev.messages.length - 1
                    ? { ...m, content: m.content + data }
                    : m,
                ),
              }));
            } else if (event === 'tool_start') {
              setState(prev => ({
                ...prev,
                messages: prev.messages.map((m, i) =>
                  i === prev.messages.length - 1
                    ? { ...m, toolCalls: [...(m.toolCalls ?? []), { name: data, summary: '' }] }
                    : m,
                ),
              }));
            } else if (event === 'tool_end') {
              try {
                const parsed = JSON.parse(data) as { tool: string; summary: string };
                setState(prev => ({
                  ...prev,
                  messages: prev.messages.map((m, i) => {
                    if (i !== prev.messages.length - 1) return m;
                    const calls = [...(m.toolCalls ?? [])];
                    const last = calls.length - 1;
                    if (last >= 0) calls[last] = { ...calls[last], summary: parsed.summary };
                    return { ...m, toolCalls: calls };
                  }),
                }));
              } catch { /* ignore */ }
            } else if (event === 'chart') {
              try {
                const figure = JSON.parse(data) as Record<string, unknown>;
                setState(prev => ({
                  ...prev,
                  messages: prev.messages.map((m, i) =>
                    i === prev.messages.length - 1
                      ? { ...m, chartFigure: figure }
                      : m,
                  ),
                }));
              } catch { /* ignore malformed chart data */ }
            } else if (event === 'done') {
              setState(prev => ({
                ...prev,
                isStreaming: false,
                messages: prev.messages.map((m, i) =>
                  i === prev.messages.length - 1 ? { ...m, isStreaming: false } : m,
                ),
              }));
            } else if (event === 'error') {
              setState(prev => ({
                ...prev,
                isStreaming: false,
                error: data,
                messages: prev.messages.map((m, i) =>
                  i === prev.messages.length - 1
                    ? { ...m, isStreaming: false, content: m.content || `Error: ${data}` }
                    : m,
                ),
              }));
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          patchLast({ isStreaming: false });
          setState(prev => ({
            ...prev,
            isStreaming: false,
            error: (err as Error).message,
          }));
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [state.chatId, state.isStreaming],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    patchLast({ isStreaming: false });
    setState(prev => ({ ...prev, isStreaming: false }));
  }, []);

  const clear = useCallback(() => {
    setState({ chatId: null, messages: [], isStreaming: false, error: null });
  }, []);

  return { ...state, sendMessage, stop, clear };
}
