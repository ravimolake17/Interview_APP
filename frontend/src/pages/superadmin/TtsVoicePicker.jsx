import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronRight, Loader2, Play } from 'lucide-react';
import { previewTtsVoice } from '../../services/api';

/** Azure English (India) voices by category. Edge usually supports Standard only. */
export const TTS_VOICE_CATALOG = [
  {
    id: 'standard',
    title: 'Standard neural',
    subtitle: 'Clear everyday Indian English — best default for interviews',
    voices: [
      { model_id: 'en-IN-NeerjaNeural', name: 'Neerja', gender: 'female' },
      { model_id: 'en-IN-AnanyaNeural', name: 'Ananya', gender: 'female' },
      { model_id: 'en-IN-AartiNeural', name: 'Aarti', gender: 'female' },
      { model_id: 'en-IN-AashiNeural', name: 'Aashi', gender: 'female' },
      { model_id: 'en-IN-KavyaNeural', name: 'Kavya', gender: 'female' },
      { model_id: 'en-IN-PrabhatNeural', name: 'Prabhat', gender: 'male' },
      { model_id: 'en-IN-AaravNeural', name: 'Aarav', gender: 'male' },
      { model_id: 'en-IN-KunalNeural', name: 'Kunal', gender: 'male' },
      { model_id: 'en-IN-ArjunNeural', name: 'Arjun', gender: 'male' },
      { model_id: 'en-IN-RehaanNeural', name: 'Rehaan', gender: 'male' },
    ],
  },
  {
    id: 'indic',
    title: 'Indic neural',
    subtitle: 'Indic-style delivery (…IndicNeural)',
    voices: [
      { model_id: 'en-IN-AartiIndicNeural', name: 'Aarti Indic', gender: 'female' },
      { model_id: 'en-IN-NeerjaIndicNeural', name: 'Neerja Indic', gender: 'female' },
      { model_id: 'en-IN-ArjunIndicNeural', name: 'Arjun Indic', gender: 'male' },
      { model_id: 'en-IN-PrabhatIndicNeural', name: 'Prabhat Indic', gender: 'male' },
    ],
  },
  {
    id: 'hd',
    title: 'HD Dragon',
    subtitle: 'Higher-fidelity DragonHD voices',
    voices: [
      { model_id: 'en-IN-Diya:DragonHDLatestNeural', name: 'Diya HD', gender: 'female' },
      { model_id: 'en-IN-Meera:DragonHDLatestNeural', name: 'Meera HD', gender: 'female' },
      { model_id: 'en-IN-Aarti:DragonHDLatestNeural', name: 'Aarti HD', gender: 'female' },
      { model_id: 'en-IN-Neerja:DragonHDLatestNeural', name: 'Neerja HD', gender: 'female' },
      { model_id: 'en-IN-Lavanya:DragonHDLatestNeural', name: 'Lavanya HD', gender: 'female' },
      { model_id: 'en-IN-Arjun:DragonHDLatestNeural', name: 'Arjun HD', gender: 'male' },
    ],
  },
];

export function findTtsVoice(modelId) {
  const id = String(modelId || '').trim();
  for (const category of TTS_VOICE_CATALOG) {
    const match = category.voices.find((voice) => voice.model_id === id);
    if (match) return { ...match, categoryId: category.id, categoryTitle: category.title };
  }
  return null;
}

export function ttsGenderFromModelId(modelId) {
  return findTtsVoice(modelId)?.gender || '';
}

function playBase64(base64, contentType, audioRef) {
  if (audioRef.current) {
    audioRef.current.pause();
    URL.revokeObjectURL(audioRef.current.src);
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type: contentType || 'audio/wav' }));
  const player = new Audio(url);
  audioRef.current = player;
  player.play().catch(() => {});
}

function errorText(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return err?.message || 'Could not play this voice.';
}

export default function TtsVoicePicker({
  provider = 'azure',
  modelId,
  voice,
  onSelect,
  compact = false,
}) {
  const known = findTtsVoice(modelId);
  const [categoryId, setCategoryId] = useState(known?.categoryId || 'standard');
  const [gender, setGender] = useState(known?.gender || voice || 'female');
  const [previewing, setPreviewing] = useState(null);
  const [error, setError] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => () => {
    if (audioRef.current) {
      audioRef.current.pause();
      URL.revokeObjectURL(audioRef.current.src);
    }
  }, []);

  useEffect(() => {
    const next = findTtsVoice(modelId);
    if (next) {
      setCategoryId(next.categoryId);
      setGender(next.gender);
    }
  }, [modelId]);

  const categories = useMemo(() => {
    if (provider === 'edge') {
      const edgeIds = new Set(['en-IN-NeerjaNeural', 'en-IN-PrabhatNeural']);
      return TTS_VOICE_CATALOG.filter((item) => item.id === 'standard').map((item) => ({
        ...item,
        subtitle: 'Edge preview supports Neerja (female) and Prabhat (male). Use Azure for Indic / HD.',
        voices: item.voices.filter((voiceItem) => edgeIds.has(voiceItem.model_id)),
      }));
    }
    return TTS_VOICE_CATALOG;
  }, [provider]);

  const category = categories.find((item) => item.id === categoryId) || categories[0];
  const genderVoices = (category?.voices || []).filter((item) => item.gender === gender);

  const preview = async (voiceItem, event) => {
    event?.stopPropagation?.();
    setError(null);
    setPreviewing(voiceItem.model_id);
    try {
      const previewProvider = provider === 'edge' && categoryId !== 'standard' ? 'azure' : provider;
      const { data } = await previewTtsVoice({
        provider: previewProvider === 'edge' ? 'edge' : 'azure',
        model_id: voiceItem.model_id,
        voice: voiceItem.gender,
      });
      if (data.audio_base64) playBase64(data.audio_base64, data.audio_content_type, audioRef);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPreviewing(null);
    }
  };

  return (
    <div className={`rounded-xl border border-col bg-white/80 dark:bg-slate-900/40 ${compact ? 'p-2' : 'p-3'} space-y-3`}>
      <div>
        <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-1.5">Category</p>
        <div className="flex flex-wrap gap-2">
          {categories.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setCategoryId(item.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                category?.id === item.id
                  ? 'bg-violet-600 text-white border-violet-600'
                  : 'border-col text-col hover:bg-violet-50 dark:hover:bg-violet-950/30'
              }`}
            >
              {item.title}
              <span className="opacity-80 ml-1">({item.voices.length})</span>
            </button>
          ))}
        </div>
        {category?.subtitle && (
          <p className="text-[11px] text-muted mt-1.5">{category.subtitle}</p>
        )}
      </div>

      <div className="grid sm:grid-cols-[140px_1fr] gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-1.5">Gender</p>
          <div className="flex sm:flex-col gap-2">
            {['female', 'male'].map((value) => {
              const count = (category?.voices || []).filter((item) => item.gender === value).length;
              return (
                <button
                  key={value}
                  type="button"
                  disabled={!count}
                  onClick={() => setGender(value)}
                  className={`px-3 py-2 rounded-lg text-xs font-medium border text-left transition-colors disabled:opacity-40 ${
                    gender === value
                      ? 'bg-orange-500 text-white border-orange-500'
                      : 'border-col text-col hover:bg-orange-50 dark:hover:bg-orange-950/20'
                  }`}
                >
                  {value === 'female' ? 'Female' : 'Male'}
                  <span className="opacity-80 ml-1">({count})</span>
                  <ChevronRight size={12} className="inline ml-1 opacity-70" />
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-1.5">
            {gender === 'female' ? 'Female' : 'Male'} voices
          </p>
          <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
            {genderVoices.map((voiceItem) => {
              const selected = modelId === voiceItem.model_id;
              const busy = previewing === voiceItem.model_id;
              return (
                <div
                  key={voiceItem.model_id}
                  className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 ${
                    selected
                      ? 'border-orange-400 bg-orange-50/80 dark:bg-orange-950/20'
                      : 'border-col hover:bg-slate-50 dark:hover:bg-slate-800/50'
                  }`}
                >
                  <button
                    type="button"
                    className="flex-1 min-w-0 text-left"
                    onClick={() => onSelect({
                      model_id: voiceItem.model_id,
                      voice: voiceItem.gender,
                      name: voiceItem.name,
                    })}
                  >
                    <p className="text-sm font-medium text-col truncate">{voiceItem.name}</p>
                    <p className="text-[11px] text-muted font-mono truncate">{voiceItem.model_id}</p>
                  </button>
                  <button
                    type="button"
                    className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-60"
                    onClick={(event) => preview(voiceItem, event)}
                    disabled={Boolean(previewing)}
                    title={`Hear ${voiceItem.name}`}
                  >
                    {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                    Run
                  </button>
                </div>
              );
            })}
            {!genderVoices.length && (
              <p className="text-xs text-muted py-3">No voices in this gender for the selected category.</p>
            )}
          </div>
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
      {modelId && (
        <p className="text-[11px] text-muted">
          Selected: <span className="font-mono text-col">{modelId}</span>
        </p>
      )}
    </div>
  );
}
