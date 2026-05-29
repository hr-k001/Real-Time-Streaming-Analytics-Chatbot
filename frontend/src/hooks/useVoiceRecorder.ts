import { useCallback, useRef, useState } from 'react';

export type RecorderStatus = 'idle' | 'recording';

export function useVoiceRecorder() {
  const [status, setStatus] = useState<RecorderStatus>('idle');
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef  = useRef<Blob[]>([]);

  const start = useCallback(async (): Promise<boolean> => {
    if (status !== 'idle') return false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = e => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start(250); // collect every 250ms
      recorderRef.current = recorder;
      setStatus('recording');
      return true;
    } catch {
      return false;
    }
  }, [status]);

  const stop = useCallback((): Promise<Blob | null> => {
    const recorder = recorderRef.current;
    if (!recorder || status !== 'recording') return Promise.resolve(null);

    return new Promise(resolve => {
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        chunksRef.current = [];
        recorder.stream.getTracks().forEach(t => t.stop());
        recorderRef.current = null;
        setStatus('idle');
        resolve(blob);
      };
      recorder.stop();
    });
  }, [status]);

  return { status, start, stop };
}
