import { useEffect, useState } from 'react';
import { ChevronDown, Globe, KeyRound, Plus, Save, Trash2, X } from 'lucide-react';
import { updateAIModelSettings } from '../../services/api';
import ModelTestModal from './ModelTestModal';
import TtsVoicePicker, { findTtsVoice, ttsGenderFromModelId } from './TtsVoicePicker';

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
    tts_models: ai.tts_models || [],
    chat_primary_id: ai.chat_primary_id || '',
    chat_fallback_id: ai.chat_fallback_id || '',
    stt_primary_id: ai.stt_primary_id || '',
    stt_fallback_id: ai.stt_fallback_id || '',
    tts_primary_id: ai.tts_primary_id || '',
    tts_fallback_id: ai.tts_fallback_id || '',
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
    return { name: '', provider: 'azure', model_id: 'gpt-4o', endpoint: '', api_version: '2024-10-21', region: '', enabled: true, voice: '' };
  }
  if (kind === 'stt') {
    return { name: '', provider: 'azure', model_id: 'azure-speech', endpoint: '', api_version: '', region: 'eastus2', enabled: true, voice: '' };
  }
  return { name: '', provider: 'azure', model_id: 'en-IN-NeerjaNeural', endpoint: '', api_version: '', region: 'eastus2', enabled: true, voice: 'female' };
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

function ModelLane({
  title,
  hint,
  kind,
  models,
  primaryId,
  fallbackId,
  draft,
  onDraft,
  onPrimary,
  onFallback,
  onAdd,
  onUpdate,
  onRemove,
  onTest,
}) {
  const [voiceEditorId, setVoiceEditorId] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [adding, setAdding] = useState(false);
  const addLabel = `Add ${title.replace(/s$/, '').toLowerCase()}`;

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
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>First preference</label>
          <select className={inputCls} value={primaryId || ''} onChange={(e) => onPrimary(e.target.value)}>
            <option value="">Select model</option>
            {models.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.model_id}){item.enabled === false ? ' — off' : ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Fallback (traffic / server error)</label>
          <select className={inputCls} value={fallbackId || ''} onChange={(e) => onFallback(e.target.value)}>
            <option value="">None</option>
            {models.filter((item) => item.id !== primaryId).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} ({item.model_id}){item.enabled === false ? ' — off' : ''}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-muted">
              <th className="py-2 pr-2">Model</th>
              <th className="py-2 pr-2">Provider</th>
              <th className="py-2 pr-2">ID / deployment</th>
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
                <td colSpan={kind === 'tts' ? 6 : 5} className="py-3 text-sm text-muted">No models yet. Add one below.</td>
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
            return (
              <div className="space-y-2 rounded-xl border border-col p-3 bg-orange-50/40">
                <p className="text-xs font-semibold text-col">Change voice for {editing.name}</p>
                <TtsVoicePicker
                  provider={editing.provider}
                  modelId={editing.model_id}
                  voice={ttsVoiceOf(editing)}
                  onSelect={({ model_id, voice: nextVoice }) => {
                    onUpdate(editing.id, { model_id, voice: nextVoice });
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
            <select className={inputCls} value={draft.provider} onChange={(e) => onDraft({ ...draft, provider: e.target.value })}>
              {providerOptions(kind).map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </div>
          {kind === 'tts' ? (
            <div className="sm:col-span-2">
              <label className={labelCls}>Voice</label>
              <p className="text-[11px] text-muted mb-2">
                Pick a category, then female or male, then a voice. Use Run to hear it before saving.
              </p>
              <TtsVoicePicker
                provider={draft.provider}
                modelId={draft.model_id}
                voice={draft.voice || 'female'}
                onSelect={({ model_id, voice: nextVoice, name }) => {
                  onDraft({
                    ...draft,
                    model_id,
                    voice: nextVoice,
                    name: draft.name?.trim() ? draft.name : name,
                  });
                }}
              />
            </div>
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
    if (aiModel) setLlmForm(formFromAiModel(aiModel));
  }, [aiModel]);

  const applyAiModel = (ai) => {
    if (!ai) return;
    setLlmForm(formFromAiModel(ai));
  };

  const llmPayload = (form) => ({
    ...form,
    temperature: Number(form.temperature),
    max_tokens: Number(form.max_tokens),
    chat_models: form.chat_models || [],
    stt_models: form.stt_models || [],
    tts_models: form.tts_models || [],
  });

  const persistLlm = async (form, successMessage) => {
    const { data } = await updateAIModelSettings(llmPayload(form));
    applyAiModel(data);
    onMessage?.(successMessage);
    return data;
  };

  const addCatalogModel = async (kind, draft, resetDraft) => {
    const name = String(draft.name || '').trim();
    const modelId = String(draft.model_id || '').trim();
    if (!name || !modelId) {
      onError?.('Enter a display name and model / deployment ID.');
      return false;
    }
    const key = `${kind}_models`;
    const sharedEndpoint = kind === 'chat'
      ? llmForm.azure_openai_endpoint
      : kind === 'stt'
        ? llmForm.azure_speech_stt_endpoint
        : llmForm.azure_speech_tts_endpoint;
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
    };
    const models = [...(llmForm[key] || []), entry];
    const primaryKey = `${kind}_primary_id`;
    const next = { ...llmForm, [key]: models };
    if (!llmForm[primaryKey]) next[primaryKey] = entry.id;
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
      [primaryKey]: llmForm[primaryKey] === id ? (models[0]?.id || '') : llmForm[primaryKey],
      [fallbackKey]: llmForm[fallbackKey] === id ? '' : llmForm[fallbackKey],
    };
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

  const savePreference = async (kind, role, value) => {
    const primaryKey = `${kind}_primary_id`;
    const fallbackKey = `${kind}_fallback_id`;
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
    const kindLabel = kind === 'chat' ? 'Chat' : kind === 'stt' ? 'STT' : 'TTS';
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
          hint="Used to speak interview questions to the candidate (Agent 4). Display name is the interviewer identity (Reena, Anuj). Voice is female or male Indian English."
          kind="tts"
          models={llmForm.tts_models || []}
          primaryId={llmForm.tts_primary_id}
          fallbackId={llmForm.tts_fallback_id}
          draft={ttsDraft}
          onDraft={setTtsDraft}
          onPrimary={(value) => savePreference('tts', 'primary', value)}
          onFallback={(value) => savePreference('tts', 'fallback', value)}
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
