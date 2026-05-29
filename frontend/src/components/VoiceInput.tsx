import { Mic, MicOff, Loader2 } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useVoiceRecorder } from '../hooks/useVoiceRecorder';
import { voiceQuery } from '../lib/api';

interface Props {
  chatId: string | null;
  onResult: (transcript: string, answer: string) => void;
  disabled?: boolean;
}

export function VoiceInput({ chatId, onResult, disabled }: Props) {
  const { status, start, stop } = useVoiceRecorder();
  const [processing, setProcessing] = useState(false);

  const handleClick = useCallback(async () => {
    if (disabled || processing) return;

    if (status === 'idle') {
      const ok = await start();
      if (!ok) alert('Microphone access denied. Please allow microphone permissions.');
    } else {
      const blob = await stop();
      if (!blob) return;

      setProcessing(true);
      try {
        const res = await voiceQuery(blob, chatId);
        onResult(res.transcript ?? '', res.answer ?? '');
      } catch (err) {
        console.error('Voice query failed:', err);
      } finally {
        setProcessing(false);
      }
    }
  }, [status, start, stop, chatId, onResult, disabled, processing]);

  const isRecording = status === 'recording';

  return (
    <div className="relative flex items-center justify-center">
      {/* Pulse ring when recording */}
      {isRecording && (
        <span
          className="absolute w-9 h-9 rounded-full animate-pulse-ring pointer-events-none"
          style={{ background: 'var(--red)', opacity: 0.35 }}
        />
      )}
      <button
        onClick={handleClick}
        disabled={disabled || processing}
        title={isRecording ? 'Stop recording' : 'Start voice input'}
        className="relative flex items-center justify-center w-9 h-9 rounded-full transition-all duration-200 disabled:opacity-40"
        style={{
          background: isRecording ? 'var(--red)' : 'var(--panel)',
          border: `1px solid ${isRecording ? 'var(--red)' : 'var(--border)'}`,
          color: isRecording ? '#fff' : 'var(--text-2)',
        }}
      >
        {processing ? (
          <Loader2 size={16} className="animate-spin" />
        ) : isRecording ? (
          <MicOff size={15} strokeWidth={2} />
        ) : (
          <Mic size={15} strokeWidth={1.75} />
        )}
      </button>
    </div>
  );
}
