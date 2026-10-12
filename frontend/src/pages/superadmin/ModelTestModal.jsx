import { useEffect, useRef, useState } from 'react';
import { Mic, Square } from 'lucide-react';
import { testCatalogModel, testCatalogStt } from '../../services/api';

function errorText(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return err?.message || 'Test failed.';
}

export default function ModelTestModal({ model, onClose }) {
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioRef = useRef(null);

  useEffect(() => {
    if (!model) return;
    if (model.kind === 'tts') {
      const persona = model.name || 'the interviewer';
      const gender = model.voice === 'male' ? 'male' : 'female';
      setPrompt(`Hello. I am ${persona}. I speak with a clear Indian English ${gender} voice.`);
    } else if (model.kind === 'chat') {
      setPrompt('Reply with one short sentence confirming you are ready for interviews.');
    } else {
      setPrompt('');
    }
    setResult(null);
    setError(null);
  }, [model]);

  useEffect(() => () => {
    if (audioRef.current) {
      URL.revokeObjectURL(audioRef.current);
      audioRef.current = null;
    }
  }, [model]);

  if (!model) return null;

  const playAudio = (base64, contentType) => {
    if (audioRef.current) URL.revokeObjectURL(audioRef.current);
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], { type: contentType || 'audio/wav' });
    const url = URL.createObjectURL(blob);
    audioRef.current = url;
    const player = new Audio(url);
    player.play().catch(() => {});
    return url;
  };

  const runChatOrTts = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const { data } = await testCatalogModel({
        kind: model.kind,
        catalog_id: model.id,
        prompt,
      });
      setResult(data);
      if (data.audio_base64) playAudio(data.audio_base64, data.audio_content_type);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const runSttFile = async (file) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const { data } = await testCatalogStt(model.id, file);
      setResult(data);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const toggleRecord = async () => {
    if (recording && recorderRef.current) {
      recorderRef.current.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ['audio/ogg;codecs=opus', 'audio/webm;codecs=opus', 'audio/webm']
        .find((type) => window.MediaRecorder?.isTypeSupported?.(type));
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const type = recorder.mimeType || mimeType || 'audio/webm';
        const ext = type.includes('ogg') ? 'ogg' : type.includes('mp4') ? 'm4a' : 'webm';
        const blob = new Blob(chunksRef.current, { type });
        const file = new File([blob], `test-stt.${ext}`, { type });
        runSttFile(file);
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch (err) {
      setError('Microphone permission is required to test speech-to-text.');
    }
  };

  const title = `Test ${model.name}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button type="button" className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={onClose} aria-label="Close" />
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full border border-col overflow-hidden">
        <div className="px-5 py-4 bg-gradient-to-r from-orange-500 to-amber-500 text-white">
          <h2 className="text-base font-semibold">{title}</h2>
          <p className="text-xs text-orange-50 mt-0.5">
            {model.provider} · {model.model_id}
            {model.kind === 'tts' && model.voice ? ` · ${model.voice} Indian English` : ''}
          </p>
        </div>
        <div className="px-5 py-4 space-y-3">
          {model.kind !== 'stt' && (
            <div>
              <label className="text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5">
                {model.kind === 'tts' ? 'Spoken line' : 'Prompt'}
              </label>
              <textarea
                className="input-field min-h-[88px]"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </div>
          )}
          {model.kind === 'stt' && (
            <div className="space-y-2">
              <p className="text-sm text-muted">Record a short clip or upload audio. This model only is used — no fallback.</p>
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={toggleRecord} disabled={busy}>
                  {recording ? <Square size={14} /> : <Mic size={14} />}
                  {recording ? 'Stop and transcribe' : 'Record'}
                </button>
                <label className="btn-secondary cursor-pointer">
                  Upload audio
                  <input
                    type="file"
                    accept="audio/*,.wav,.mp3,.webm,.m4a"
                    className="hidden"
                    onChange={(e) => runSttFile(e.target.files?.[0])}
                  />
                </label>
              </div>
            </div>
          )}
          {error && <p className="text-sm text-rose-600">{error}</p>}
          {result?.text && (
            <div className="rounded-xl border border-col bg-slate-50 px-3 py-2 text-sm text-col whitespace-pre-wrap">
              {result.text}
            </div>
          )}
          {result?.audio_base64 && (
            <audio
              className="w-full"
              controls
              src={`data:${result.audio_content_type || 'audio/wav'};base64,${result.audio_base64}`}
            />
          )}
        </div>
        <div className="px-5 pb-5 flex gap-2">
          <button type="button" className="btn-secondary flex-1" onClick={onClose}>Close</button>
          {model.kind !== 'stt' && (
            <button type="button" className="btn-primary flex-1" onClick={runChatOrTts} disabled={busy}>
              {busy ? 'Testing…' : model.kind === 'tts' ? 'Speak' : 'Send'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
