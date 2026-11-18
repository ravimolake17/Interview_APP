import { useEffect, useState } from 'react';
import { ChevronDown, Globe, KeyRound, Plus, Save, Trash2, X } from 'lucide-react';
import { updateAIModelSettings } from '../../services/api';
import ModelTestModal from './ModelTestModal';
import TtsVoicePicker, {
  findTtsVoice,
  inferTtsLanguage,
  ttsGenderFromModelId,
} from './TtsVoicePicker';

const GROQ_MODEL_REPLACEMENTS = {
  'llama-3.3-70b-versatile': 'openai/gpt-oss-120b',
  'llama-3.1-8b-instant': 'openai/gpt-oss-20b',
};

const inputCls = 'input-field';
const labelCls = 'text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5';

function formFromAiModel(ai) {
  const provider = ai.provider || 'groq';
  return {
    provider,
    model_id: GROQ_MODEL_REPLACEMENTS[ai.model_id] || ai.model_id,
    temperature: ai.temperature,
    max_tokens: ai.max_tokens,
    prompt_style: ai.prompt_style,
    azure_openai_endpoint: ai.azure_openai_endpoint || '',
    azure_openai_deployment: ai.azure_openai_deployment || 'gpt-4o',
    azure_openai_api_version: ai.azure_openai_api_version || '2024-10-21',
    stt_provider: ai.stt_provider || 'groq',
    tts_provider: ai.tts_provider || 'edge',
    azure_speech_region: ai.azure_speech_region || 'eastus2',
    azure_speech_stt_endpoint: ai.azure_speech_stt_endpoint || '',
    azure_speech_tts_endpoint: ai.azure_speech_tts_endpoint || '',
    chat_models: ai.chat_models || [],
    stt_models: ai.stt_models || [],
    tts_models: (ai.tts_models || []).map((item) => ({
      ...item,
      language: inferTtsLanguage(item?.model_id, item?.language),
    })),
    chat_primary_id: ai.chat_primary_id || '',
    chat_fallback_id: ai.chat_fallback_id || '',
    stt_primary_id: ai.stt_primary_id || '',
    stt_fallback_id: ai.stt_fallback_id || '',
    tts_primary_id: ai.tts_primary_id || '',
    tts_fallback_id: ai.tts_fallback_id || '',
    tts_hi_primary_id: ai.tts_hi_primary_id || '',
    tts_hi_fallback_id: ai.tts_hi_fallback_id || '',
  };
}

function catalogId(kind, provider, modelId) {
  const slug = `${kind}-${provider}-${String(modelId || 'model').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`.replace(/-+/g, '-');
  return `${slug}-${Math.random().toString(36).slice(2, 6)}`;
}

function ttsVoiceOf(item) {
  const raw = String(item?.voice || '').trim().toLowerCase();
  if (raw === 'male' || raw === 'female') return raw;
  return ttsGenderFromModelId(item?.model_id) || '';
}

function ttsLanguageOf(item) {
  return inferTtsLanguage(item?.model_id, item?.language);
}

function ttsVoiceLabel(item) {
  const known = findTtsVoice(item?.model_id);
  if (known) return `${known.gender === 'male' ? 'Male' : 'Female'} · ${known.name}`;
  const voice = ttsVoiceOf(item);
  if (voice === 'male') return 'Male';
  if (voice === 'female') return 'Female';
  return '—';
}

function emptyDraft(kind) {
  if (kind === 'chat') {
    return { name: '', provider: 'azure', model_id: 'gpt-4o', endpoint: '', api_version: '2024-10-21', region: '', enabled: true, voice: '', language: '' };
  }
  if (kind === 'stt') {
    return { name: '', provider: 'azure', model_id: 'azure-speech', endpoint: '', api_version: '', region: 'eastus2', enabled: true, voice: '', language: '' };
  }
  return {
    name: '',
    provider: '',
    model_id: '',
    endpoint: '',
    api_version: '',
    region: 'eastus2',
    enabled: true,
    voice: '',
    language: '',
  };
}

function providerOptions(kind) {
  if (kind === 'tts') {
    return [
      { value: 'azure', label: 'Azure Speech' },
      { value: 'edge', label: 'Edge neural' },
    ];
  }
  if (kind === 'stt') {
    return [
      { value: 'azure', label: 'Azure Speech' },
      { value: 'groq', label: 'Groq Whisper' },
    ];
  }
  return [
    { value: 'azure', label: 'Azure OpenAI' },
    { value: 'groq', label: 'Groq' },
  ];
}

function PreferenceSelect({ label, value, options, excludeId, onChange }) {
  const visible = options.filter((item) => item.id !== excludeId);
  // Keep the current value visible even if language filter/options briefly disagree.
  const selected = options.find((item) => item.id === value)
    || visible.find((item) => item.id === value);
  const rows = selected && !visible.some((item) => item.id === selected.id)
    ? [selected, ...visible]
    : visible;
  return (
    <div>
      <label className={labelCls}>{label}</label>
      <select
        className={inputCls}
        value={value || ''}
        onChange={(e) => {
          const next = e.target.value;
          if (typeof onChange === 'function') onChange(next);
        }}
      >
        <option value="">{label.toLowerCase().includes('fallback') ? 'None' : 'Select model'}</option>
        {rows.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name} ({item.model_id}){item.enabled === false ? ' — off' : ''}
          </option>
        ))}
      </select>
      {value && !rows.some((item) => item.id === value) && (
        <p className="text-[11px] text-amber-700 mt-1">
          Selected model is missing from this language list. Pick Reena/Abhishek again.
        </p>
      )}
      {!rows.length && (
        <p className="text-[11px] text-muted mt-1">
          No models in this language yet. Add a Hindi TTS voice below, then select it here.
        </p>
      )}
    </div>
  );
}

function ModelLane({
  title,
  hint,
  kind,
  models,
  primaryId,
  fallbackId,
  hiPrimaryId,
  hiFallbackId,
  draft,
  onDraft,
  onPrimary,
  onFallback,
  onHiPrimary,
  onHiFallback,
  onAdd,
  onUpdate,
  onRemove,
  onTest,
}) {
  const [voiceEditorId, setVoiceEditorId] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [adding, setAdding] = useState(false);
  const addLabel = `Add ${title.replace(/s$/, '').toLowerCase()}`;
  const englishModels = kind === 'tts' ? models.filter((item) => ttsLanguageOf(item) === 'en') : models;
  const hindiModels = kind === 'tts' ? models.filter((item) => ttsLanguageOf(item) === 'hi') : [];
  const draftLanguage = draft.language === 'hi' || draft.language === 'en' ? draft.language : '';
  const draftProvider = draft.provider || '';
  const canPickVoice = kind === 'tts' && Boolean(draftProvider) && Boolean(draftLanguage);

  const submitAdd = async () => {
    if (adding) return;
    setAdding(true);
    try {
      const ok = await onAdd();
      if (ok !== false) setShowAdd(false);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="rounded-2xl border border-col p-4 space-y-3">
      <div>
        <h3 className="font-semibold text-col">{title}</h3>
        <p className="text-xs text-muted mt-0.5">{hint}</p>
      </div>
      {kind === 'tts' ? (
        <div className="space-y-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-2">English interview</p>
            <div className="grid sm:grid-cols-2 gap-3">
              <PreferenceSelect
                label="First preference"
                value={primaryId}
                options={englishModels}
                onChange={onPrimary}
              />
              <PreferenceSelect
                label="Fallback (traffic / server error)"
                value={fallbackId}
                options={englishModels}
                excludeId={primaryId}
                onChange={onFallback}
              />
            </div>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-2">Hindi interview</p>
            <div className="grid sm:grid-cols-2 gap-3">
              <PreferenceSelect
                label="First preference"
                value={hiPrimaryId}
                options={hindiModels}
                onChange={onHiPrimary}
              />
              <PreferenceSelect
                label="Fallback (traffic / server error)"
                value={hiFallbackId}
                options={hindiModels}
                excludeId={hiPrimaryId}
                onChange={onHiFallback}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          <PreferenceSelect
            label="First preference"
            value={primaryId}
            options={models}
            onChange={onPrimary}
          />
          <PreferenceSelect
            label="Fallback (traffic / server error)"
            value={fallbackId}
            options={models}
            excludeId={primaryId}
            onChange={onFallback}
          />
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-muted">
              <th className="py-2 pr-2">Model</th>
              <th className="py-2 pr-2">Provider</th>
              <th className="py-2 pr-2">ID / deployment</th>
              {kind === 'tts' && <th className="py-2 pr-2">Language</th>}
              {kind === 'tts' && <th className="py-2 pr-2">Voice</th>}
              <th className="py-2 pr-2">On</th>
              <th className="py-2"> </th>
            </tr>
          </thead>
          <tbody>
            {models.map((item) => (
              <tr key={item.id} className="border-t border-col">
                <td className="py-2 pr-2">
                  <button
                    type="button"
                    className="font-medium text-col hover:text-orange-600 underline-offset-2 hover:underline text-left"
                    onClick={() => onTest(item)}
                    title="Test this model"
                  >
                    {item.name}
                  </button>
                </td>
                <td className="py-2 pr-2 text-muted">{item.provider}</td>
                <td className="py-2 pr-2 text-muted truncate max-w-[180px]">{item.model_id}</td>
                {kind === 'tts' && (
                  <td className="py-2 pr-2 text-muted">
                    {ttsLanguageOf(item) === 'hi' ? 'Hindi' : 'English'}
                  </td>
                )}
                {kind === 'tts' && (
                  <td className="py-2 pr-2">
                    <button
                      type="button"
                      className="text-xs text-orange-700 hover:underline"
                      onClick={() => setVoiceEditorId((cur) => (cur === item.id ? null : item.id))}
                    >
                      {ttsVoiceLabel(item)}
                    </button>
                  </td>
                )}
                <td className="py-2 pr-2">
                  <input
                    type="checkbox"
                    checked={item.enabled !== false}
                    onChange={(e) => onUpdate(item.id, { enabled: e.target.checked })}
                  />
                </td>
                <td className="py-2 text-right">
                  <button type="button" className="text-rose-600 hover:text-rose-700" onClick={() => onRemove(item.id)} title="Delete">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
            {models.length === 0 && (
              <tr>
                <td colSpan={kind === 'tts' ? 7 : 5} className="py-3 text-sm text-muted">No models yet. Add one below.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {kind === 'tts' && voiceEditorId && (
        <div className="mt-1">
          {(() => {
            const editing = models.find((row) => row.id === voiceEditorId);
            if (!editing) return null;
            const editingLanguage = ttsLanguageOf(editing);
            return (
              <div className="space-y-2 rounded-xl border border-col p-3 bg-orange-50/40">
                <p className="text-xs font-semibold text-col">
                  Change {editingLanguage === 'hi' ? 'Hindi' : 'English'} voice for {editing.name}
                </p>
                <TtsVoicePicker
                  provider={editing.provider}
                  language={editingLanguage}
                  modelId={editing.model_id}
                  voice={ttsVoiceOf(editing)}
                  onSelect={({ model_id, voice: nextVoice, language: nextLanguage }) => {
                    onUpdate(editing.id, {
                      model_id,
                      voice: nextVoice,
                      language: nextLanguage || editingLanguage,
                    });
                    setVoiceEditorId(null);
                  }}
                />
              </div>
            );
          })()}
        </div>
      )}
      {!showAdd ? (
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-orange-500 hover:bg-orange-600 shadow-sm shadow-orange-500/25 border border-orange-600/20 transition-colors"
        >
          <Plus size={15} strokeWidth={2.5} />
          {addLabel}
          <ChevronDown size={14} className="opacity-80" />
        </button>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3 pt-1 rounded-xl border border-orange-200/80 bg-orange-50/40 dark:bg-orange-950/20 dark:border-orange-900/40 p-3">
          <div className="sm:col-span-2 flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-orange-700 dark:text-orange-300">
              New {title.replace(/s$/, '').toLowerCase()}
            </p>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-col"
              onClick={() => setShowAdd(false)}
            >
              <X size={13} /> Cancel
            </button>
          </div>
          <div>
            <label className={labelCls}>Display name</label>
            <input
              className={inputCls}
              placeholder={kind === 'tts' ? 'Reena or Anuj' : 'Azure GPT-4o'}
              value={draft.name}
              onChange={(e) => onDraft({ ...draft, name: e.target.value })}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void submitAdd(); } }}
            />
            {kind === 'tts' && (
              <p className="text-[11px] text-muted mt-1">This name is how the interviewer introduces itself.</p>
            )}
          </div>
          <div>
            <label className={labelCls}>Provider</label>
            <select
              className={inputCls}
              value={draftProvider}
              onChange={(e) => onDraft({
                ...draft,
                provider: e.target.value,
                model_id: '',
                voice: '',
              })}
            >
              {kind === 'tts' && <option value="">Select provider</option>}
              {providerOptions(kind).map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </div>
          {kind === 'tts' ? (
            <>
              <div>
                <label className={labelCls}>Language</label>
                <select
                  className={inputCls}
                  value={draftLanguage}
                  onChange={(e) => onDraft({
                    ...draft,
                    language: e.target.value,
                    model_id: '',
                    voice: '',
                  })}
                >
                  <option value="">Select language</option>
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className={labelCls}>Voice</label>
                {!canPickVoice ? (
                  <p className="text-[11px] text-muted mt-1">
                    Select provider and language first. Voices then show only for that combination.
                  </p>
                ) : (
                  <>
                    <p className="text-[11px] text-muted mb-2">
                      Pick a category, then female or male, then a {draftLanguage === 'hi' ? 'Hindi' : 'English'} voice. Use Run to hear it before saving.
                    </p>
                    <TtsVoicePicker
                      provider={draftProvider}
                      language={draftLanguage}
                      modelId={draft.model_id}
                      voice={draft.voice || 'female'}
                      onSelect={({ model_id, voice: nextVoice, name, language: nextLanguage }) => {
                        onDraft({
                          ...draft,
                          model_id,
                          voice: nextVoice,
                          language: nextLanguage || draftLanguage,
                          name: draft.name?.trim() ? draft.name : name,
                        });
                      }}
                    />
                  </>
                )}
              </div>
            </>
          ) : (
            <div>
              <label className={labelCls}>{kind === 'chat' && draft.provider === 'azure' ? 'Deployment name' : 'Model ID'}</label>
              <input
                className={inputCls}
                placeholder={kind === 'chat' ? 'gpt-4o or gpt-5-mini' : 'whisper-large-v3'}
                value={draft.model_id}
                onChange={(e) => onDraft({ ...draft, model_id: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void submitAdd(); } }}
              />
            </div>
          )}
          {draft.provider === 'azure' && (
            <div>
              <label className={labelCls}>{kind === 'chat' ? 'Endpoint (optional)' : 'Speech endpoint (optional)'}</label>
              <input
                className={inputCls}
                placeholder={kind === 'chat' ? 'https://….openai.azure.com' : 'https://eastus2.stt.speech.microsoft.com'}
                value={draft.endpoint}
                onChange={(e) => onDraft({ ...draft, endpoint: e.target.value })}
              />
            </div>
          )}
          {kind === 'chat' && draft.provider === 'azure' && (
            <div>
              <label className={labelCls}>API version</label>
              <input className={inputCls} value={draft.api_version} onChange={(e) => onDraft({ ...draft, api_version: e.target.value })} />
            </div>
          )}
          {kind !== 'chat' && draft.provider === 'azure' && (
            <div>
              <label className={labelCls}>Region</label>
              <input className={inputCls} value={draft.region} onChange={(e) => onDraft({ ...draft, region: e.target.value })} />
            </div>
          )}
          <div className="sm:col-span-2 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={adding}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-orange-500 hover:bg-orange-600 shadow-sm shadow-orange-500/25 border border-orange-600/20 transition-colors disabled:opacity-60"
              onClick={() => void submitAdd()}
            >
              <Plus size={15} strokeWidth={2.5} />
              {adding ? 'Saving…' : addLabel}
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium text-muted border border-col hover:text-col hover:bg-slate-50 dark:hover:bg-slate-800/60"
              onClick={() => setShowAdd(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function LlmCatalogTab({ aiModel, integration, onMessage, onError }) {
  const [llmForm, setLlmForm] = useState(() => formFromAiModel(aiModel || {}));
  const [chatDraft, setChatDraft] = useState(emptyDraft('chat'));
  const [sttDraft, setSttDraft] = useState(emptyDraft('stt'));
  const [ttsDraft, setTtsDraft] = useState(emptyDraft('tts'));
  const [testingModel, setTestingModel] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (aiModel) applyAiModel(aiModel);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync when SuperAdmin reloads system bundle
  }, [aiModel]);

  // If Hindi voices exist but preference was never saved (or wiped by old API), default to first Hindi model.
  useEffect(() => {
    const hindi = (llmForm.tts_models || []).filter((item) => ttsLanguageOf(item) === 'hi');
    if (!hindi.length) return;
    if (llmForm.tts_hi_primary_id && hindi.some((item) => item.id === llmForm.tts_hi_primary_id)) {
      return;
    }
    const firstId = hindi[0].id;
    setLlmForm((prev) => ({ ...prev, tts_hi_primary_id: firstId }));
  }, [llmForm.tts_models, llmForm.tts_hi_primary_id]);

  const applyAiModel = (ai, { keepLocalHiPrefs = false } = {}) => {
    if (!ai) return;
    setLlmForm((prev) => {
      const next = formFromAiModel(ai);
      // Old backend processes (no --reload) may omit new Hindi preference fields
      // and wipe the dropdown after save — keep the optimistic local choice.
      if (
        keepLocalHiPrefs
        || !Object.prototype.hasOwnProperty.call(ai, 'tts_hi_primary_id')
      ) {
        if (prev.tts_hi_primary_id) next.tts_hi_primary_id = prev.tts_hi_primary_id;
        if (prev.tts_hi_fallback_id) next.tts_hi_fallback_id = prev.tts_hi_fallback_id;
      }
      return next;
    });
  };

  const llmPayload = (form) => ({
    ...form,
    temperature: Number(form.temperature),
    max_tokens: Number(form.max_tokens),
    chat_models: form.chat_models || [],
    stt_models: form.stt_models || [],
    tts_models: (form.tts_models || []).map((item) => ({
      ...item,
      language: inferTtsLanguage(item?.model_id, item?.language),
    })),
    tts_hi_primary_id: form.tts_hi_primary_id || '',
    tts_hi_fallback_id: form.tts_hi_fallback_id || '',
  });

  const persistLlm = async (form, successMessage) => {
    const payload = llmPayload(form);
    const { data } = await updateAIModelSettings(payload);
    // If the API echoed Hindi prefs, trust it; otherwise keep what we just saved.
    const serverHasHi = data && Object.prototype.hasOwnProperty.call(data, 'tts_hi_primary_id');
    const serverLostHi = serverHasHi
      && payload.tts_hi_primary_id
      && !data.tts_hi_primary_id;
    applyAiModel(data, { keepLocalHiPrefs: serverLostHi || !serverHasHi });
    if (serverLostHi || !serverHasHi) {
      onMessage?.(
        `${successMessage} Restart the API server (uvicorn) so Hindi TTS preferences persist.`,
      );
    } else {
      onMessage?.(successMessage);
    }
    return data;
  };

  const addCatalogModel = async (kind, draft, resetDraft) => {
    const name = String(draft.name || '').trim();
    const modelId = String(draft.model_id || '').trim();
    if (!name || !modelId) {
      onError?.(kind === 'tts'
        ? 'Enter a display name and pick a voice after provider + language.'
        : 'Enter a display name and model / deployment ID.');
      return false;
    }
    if (kind === 'tts' && (!draft.provider || (draft.language !== 'en' && draft.language !== 'hi'))) {
      onError?.('Select provider and language before saving a TTS model.');
      return false;
    }
    const key = `${kind}_models`;
    const sharedEndpoint = kind === 'chat'
      ? llmForm.azure_openai_endpoint
      : kind === 'stt'
        ? llmForm.azure_speech_stt_endpoint
        : llmForm.azure_speech_tts_endpoint;
    const language = kind === 'tts' ? inferTtsLanguage(modelId, draft.language) : '';
    const entry = {
      id: catalogId(kind, draft.provider, modelId),
      name,
      kind,
      provider: draft.provider,
      model_id: modelId,
      enabled: true,
      endpoint: draft.endpoint || (draft.provider === 'azure' ? sharedEndpoint : '') || '',
      api_version: draft.api_version || (kind === 'chat' ? llmForm.azure_openai_api_version : '') || '',
      region: draft.region || llmForm.azure_speech_region || '',
      voice: kind === 'tts' ? (draft.voice || 'female') : '',
      language,
    };
    const models = [...(llmForm[key] || []), entry];
    const next = { ...llmForm, [key]: models };
    if (kind === 'tts') {
      if (language === 'hi') {
        if (!llmForm.tts_hi_primary_id) next.tts_hi_primary_id = entry.id;
      } else if (!llmForm.tts_primary_id) {
        next.tts_primary_id = entry.id;
      }
    } else {
      const primaryKey = `${kind}_primary_id`;
      if (!llmForm[primaryKey]) next[primaryKey] = entry.id;
    }
    onError?.(null);
    setLlmForm(next);
    resetDraft(emptyDraft(kind));
    setSaving(true);
    try {
      await persistLlm(next, `${name} saved.`);
      return true;
    } catch (err) {
      onError?.(err.response?.data?.detail || 'Could not save the new model.');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const updateCatalogModel = async (kind, id, patch) => {
    const key = `${kind}_models`;
    const prev = llmForm;
    const next = {
      ...llmForm,
      [key]: (llmForm[key] || []).map((item) => (item.id === id ? { ...item, ...patch } : item)),
    };
    setLlmForm(next);
    setSaving(true);
    onError?.(null);
    try {
      await persistLlm(next, 'Model list saved.');
    } catch (err) {
      setLlmForm(prev);
      onError?.(err.response?.data?.detail || 'Could not update the model list.');
    } finally {
      setSaving(false);
    }
  };

  const removeCatalogModel = async (kind, id) => {
    const key = `${kind}_models`;
    const prev = llmForm;
    const models = (llmForm[key] || []).filter((item) => item.id !== id);
    const removed = (llmForm[key] || []).find((item) => item.id === id);
    const primaryKey = `${kind}_primary_id`;
    const fallbackKey = `${kind}_fallback_id`;
    const next = {
      ...llmForm,
      [key]: models,
      [primaryKey]: llmForm[primaryKey] === id
        ? (models.find((item) => kind !== 'tts' || ttsLanguageOf(item) === 'en')?.id || '')
        : llmForm[primaryKey],
      [fallbackKey]: llmForm[fallbackKey] === id ? '' : llmForm[fallbackKey],
    };
    if (kind === 'tts') {
      next.tts_hi_primary_id = llmForm.tts_hi_primary_id === id
        ? (models.find((item) => ttsLanguageOf(item) === 'hi')?.id || '')
        : llmForm.tts_hi_primary_id;
      next.tts_hi_fallback_id = llmForm.tts_hi_fallback_id === id ? '' : llmForm.tts_hi_fallback_id;
    }
    setLlmForm(next);
    setSaving(true);
    onError?.(null);
    try {
      await persistLlm(next, `${removed?.name || 'Model'} removed.`);
    } catch (err) {
      setLlmForm(prev);
      onError?.(err.response?.data?.detail || 'Could not remove the model.');
    } finally {
      setSaving(false);
    }
  };

  const savePreference = async (kind, role, value, language = 'en') => {
    const isHiTts = kind === 'tts' && language === 'hi';
    const primaryKey = isHiTts ? 'tts_hi_primary_id' : `${kind}_primary_id`;
    const fallbackKey = isHiTts ? 'tts_hi_fallback_id' : `${kind}_fallback_id`;
    const prev = llmForm;
    const next = { ...llmForm };
    if (role === 'primary') {
      next[primaryKey] = value;
      if (value && next[fallbackKey] === value) next[fallbackKey] = '';
    } else {
      next[fallbackKey] = value === next[primaryKey] ? '' : value;
    }
    const models = llmForm[`${kind}_models`] || [];
    const selected = models.find((item) => item.id === value);
    const label = role === 'primary' ? 'First preference' : 'Fallback';
    const kindLabel = kind === 'chat'
      ? 'Chat'
      : kind === 'stt'
        ? 'STT'
        : isHiTts
          ? 'Hindi TTS'
          : kind === 'tts'
            ? 'English TTS'
            : 'TTS';
    setLlmForm(next);
    setSaving(true);
    onError?.(null);
    try {
      await persistLlm(
        next,
        value
          ? `${kindLabel} ${label.toLowerCase()} set to ${selected?.name || value}.`
          : `${kindLabel} ${label.toLowerCase()} cleared.`,
      );
    } catch (err) {
      setLlmForm(prev);
      onError?.(err.response?.data?.detail || `Could not save ${kindLabel.toLowerCase()} preference.`);
    } finally {
      setSaving(false);
    }
  };

  const saveLlm = async (event) => {
    event.preventDefault();
    setSaving(true);
    onError?.(null);
    try {
      await persistLlm(
        llmForm,
        'Shared Azure defaults, temperature, and prompt style saved. Preference dropdowns already save on change.',
      );
    } catch (err) {
      onError?.(err.response?.data?.detail || 'Could not save LLM settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <form onSubmit={saveLlm} className="max-w-4xl space-y-4">
        <div className="card overflow-hidden">
          <div className="px-5 py-4 bg-gradient-to-r from-orange-50 to-amber-50 border-b border-orange-100">
            <h2 className="text-lg font-semibold text-col">Models, preference, and fallback</h2>
            <p className="text-sm text-muted mt-1">
              Screening, questions, scoring, and reports use <strong>Chat</strong>.
              The live room uses <strong>STT</strong> and <strong>TTS</strong>.
              Order: first preference → fallback → every other model left ON in the table (same Chat / STT / TTS lane).
            </p>
          </div>
          <div className="px-5 py-3 flex flex-wrap gap-2">
            {[
              ['Groq', integration?.groq_api_key_masked],
              ['Azure OpenAI', integration?.azure_openai_api_key_masked],
              ['Speech', integration?.azure_speech_key_masked],
            ].map(([label, masked]) => {
              const ready = masked && !String(masked).toLowerCase().includes('not configured');
              return (
                <span
                  key={label}
                  className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${
                    ready ? 'bg-emerald-50 text-emerald-800 border-emerald-100' : 'bg-amber-50 text-amber-800 border-amber-100'
                  }`}
                >
                  <KeyRound size={12} />
                  {label}: {masked || 'not set'}
                </span>
              );
            })}
          </div>
        </div>

        <ModelLane
          title="Chat models"
          hint="Used by Agent 1 screening, Agent 4 questions, Agent 6 scoring, and Agent 7 reports. Agent 3 blueprint is rule-based and does not call an AI model."
          kind="chat"
          models={llmForm.chat_models || []}
          primaryId={llmForm.chat_primary_id}
          fallbackId={llmForm.chat_fallback_id}
          draft={chatDraft}
          onDraft={setChatDraft}
          onPrimary={(value) => savePreference('chat', 'primary', value)}
          onFallback={(value) => savePreference('chat', 'fallback', value)}
          onAdd={() => addCatalogModel('chat', chatDraft, setChatDraft)}
          onUpdate={(id, patch) => updateCatalogModel('chat', id, patch)}
          onRemove={(id) => removeCatalogModel('chat', id)}
          onTest={setTestingModel}
        />
        <ModelLane
          title="Speech-to-text"
          hint="Used when the candidate answers in the interview room (Agent 4) and for voice checks (Agent 5)."
          kind="stt"
          models={llmForm.stt_models || []}
          primaryId={llmForm.stt_primary_id}
          fallbackId={llmForm.stt_fallback_id}
          draft={sttDraft}
          onDraft={setSttDraft}
          onPrimary={(value) => savePreference('stt', 'primary', value)}
          onFallback={(value) => savePreference('stt', 'fallback', value)}
          onAdd={() => addCatalogModel('stt', sttDraft, setSttDraft)}
          onUpdate={(id, patch) => updateCatalogModel('stt', id, patch)}
          onRemove={(id) => removeCatalogModel('stt', id)}
          onTest={setTestingModel}
        />
        <ModelLane
          title="Text-to-speech"
          hint="Used to speak interview questions (Agent 4). Set English and Hindi first preference + fallback separately. Display name is the interviewer identity (Reena, Anuj)."
          kind="tts"
          models={llmForm.tts_models || []}
          primaryId={llmForm.tts_primary_id}
          fallbackId={llmForm.tts_fallback_id}
          hiPrimaryId={llmForm.tts_hi_primary_id}
          hiFallbackId={llmForm.tts_hi_fallback_id}
          draft={ttsDraft}
          onDraft={setTtsDraft}
          onPrimary={(value) => savePreference('tts', 'primary', value, 'en')}
          onFallback={(value) => savePreference('tts', 'fallback', value, 'en')}
          onHiPrimary={(value) => savePreference('tts', 'primary', value, 'hi')}
          onHiFallback={(value) => savePreference('tts', 'fallback', value, 'hi')}
          onAdd={() => addCatalogModel('tts', ttsDraft, setTtsDraft)}
          onUpdate={(id, patch) => updateCatalogModel('tts', id, patch)}
          onRemove={(id) => removeCatalogModel('tts', id)}
          onTest={setTestingModel}
        />

        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500 to-blue-600 text-white flex items-center justify-center shadow-sm">
              <Globe size={18} />
            </div>
            <div>
              <h3 className="font-semibold text-col">Shared Azure defaults</h3>
              <p className="text-xs text-muted">Used when an Azure model row does not set its own endpoint.</p>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <label className={labelCls}>Azure OpenAI endpoint</label>
              <input
                className={inputCls}
                placeholder="https://interview-openai-foundr-resource.openai.azure.com"
                value={llmForm.azure_openai_endpoint}
                onChange={(e) => setLlmForm((f) => ({ ...f, azure_openai_endpoint: e.target.value }))}
              />
            </div>
            <div>
              <label className={labelCls}>Azure OpenAI API version</label>
              <input className={inputCls} value={llmForm.azure_openai_api_version} onChange={(e) => setLlmForm((f) => ({ ...f, azure_openai_api_version: e.target.value }))} />
            </div>
            <div>
              <label className={labelCls}>Azure Speech region</label>
              <input className={inputCls} value={llmForm.azure_speech_region} onChange={(e) => setLlmForm((f) => ({ ...f, azure_speech_region: e.target.value }))} />
            </div>
            <div>
              <label className={labelCls}>STT endpoint</label>
              <input className={inputCls} placeholder="https://eastus2.stt.speech.microsoft.com" value={llmForm.azure_speech_stt_endpoint} onChange={(e) => setLlmForm((f) => ({ ...f, azure_speech_stt_endpoint: e.target.value }))} />
            </div>
            <div>
              <label className={labelCls}>TTS endpoint</label>
              <input className={inputCls} placeholder="https://eastus2.tts.speech.microsoft.com" value={llmForm.azure_speech_tts_endpoint} onChange={(e) => setLlmForm((f) => ({ ...f, azure_speech_tts_endpoint: e.target.value }))} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Temperature ({Number(llmForm.temperature).toFixed(2)})</label>
            <input type="range" min="0" max="1" step="0.05" value={llmForm.temperature} onChange={(e) => setLlmForm((f) => ({ ...f, temperature: e.target.value }))} className="w-full accent-orange-500" />
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Max tokens</label>
              <input type="number" min="256" max="32768" className={inputCls} value={llmForm.max_tokens} onChange={(e) => setLlmForm((f) => ({ ...f, max_tokens: e.target.value }))} />
            </div>
            <div>
              <label className={labelCls}>Prompt style</label>
              <select className={inputCls} value={llmForm.prompt_style} onChange={(e) => setLlmForm((f) => ({ ...f, prompt_style: e.target.value }))}>
                <option value="detailed_analysis">Detailed analysis</option>
                <option value="quick_summary">Quick summary</option>
                <option value="technical_focus">Technical focus</option>
                <option value="cultural_fit_focus">Cultural fit focus</option>
              </select>
            </div>
          </div>
          <button type="submit" disabled={saving} className="btn-primary inline-flex items-center gap-2">
            <Save size={14} /> Save model settings
          </button>
        </div>
      </form>
      {testingModel && (
        <ModelTestModal model={testingModel} onClose={() => setTestingModel(null)} />
      )}
    </>
  );
}
