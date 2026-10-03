import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { User, Building2, Link, Palette, Bell, Cpu, Save, Clock } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { isSuperAdmin } from '../../utils/roles';
import { PRIMARY_COLORS } from '../../utils/theme';
import {
  getSettings,
  testIntegrationConnection,
  updateAIModelSettings,
  updateCompanySettings,
  updateInterviewAvailability,
  updateProfileSettings,
} from '../../services/api';
import InterviewHoursForm, { normalizeAvailability } from '../../components/InterviewHoursForm';

const GROQ_MODEL_REPLACEMENTS = {
  'llama-3.3-70b-versatile': 'openai/gpt-oss-120b',
  'llama-3.1-8b-instant': 'openai/gpt-oss-20b',
};

const TABS = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'company', label: 'Company', icon: Building2 },
  { id: 'interview', label: 'Interview hours', icon: Clock },
  { id: 'api', label: 'API & Integration', icon: Link },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'model', label: 'AI Model', icon: Cpu },
];

function FormField({ label, children, hint }) {
  return (
    <div>
      <label className="text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted mt-1">{hint}</p>}
    </div>
  );
}

const inputCls = `input-field focus:ring-0`;

export default function Settings() {
  const { user, updateCurrentUser } = useAuth();
  const {
    appearance,
    setTheme,
    setPrimaryColorId,
    saveAppearance,
    notificationPreferences,
    saveNotificationPreferences,
    addToast,
    workingCompanyId,
  } = useApp();
  const [activeTab, setActiveTab] = useState('profile');
  const [integration, setIntegration] = useState(null);
  const [notifications, setNotifications] = useState(notificationPreferences);
  const [availability, setAvailability] = useState(normalizeAvailability());
  const [loading, setLoading] = useState(true);
  const visibleTabs = isSuperAdmin(user?.role)
    ? TABS
    : TABS.filter((tab) => tab.id !== 'model' && tab.id !== 'company' && tab.id !== 'api');
  const [saving, setSaving] = useState(false);
  const { register, handleSubmit, reset, watch } = useForm({
    defaultValues: {
      name: user?.full_name || '',
      email: user?.email || '',
      jobTitle: user?.job_title || '',
      phone: user?.phone || '',
      company: 'RR Global Pvt Ltd',
      website: 'https://rrglobal.in',
      industry: 'Technology',
      companySize: '201-1000',
      headquarters: 'Mumbai, India',
      timezone: 'Asia/Kolkata',
      model: 'openai/gpt-oss-120b',
      temperature: 0,
      maxTokens: 8192,
      promptStyle: 'detailed_analysis',
      provider: 'groq',
    },
  });

  useEffect(() => {
    let active = true;
    getSettings()
      .then(({ data }) => {
        if (!active) return;
        reset({
          name: data.profile.full_name || '',
          email: data.profile.email || '',
          jobTitle: data.profile.job_title || '',
          phone: data.profile.phone || '',
          company: data.company.company_name,
          website: data.company.website,
          industry: data.company.industry,
          companySize: data.company.company_size,
          headquarters: data.company.headquarters,
          timezone: data.company.timezone,
          model: GROQ_MODEL_REPLACEMENTS[data.ai_model.model_id] || data.ai_model.model_id,
          temperature: data.ai_model.temperature,
          maxTokens: data.ai_model.max_tokens,
          promptStyle: data.ai_model.prompt_style,
          provider: data.ai_model.provider || 'groq',
        });
        setIntegration(data.integration);
        setNotifications(data.preferences.notifications);
        setAvailability(normalizeAvailability(data.interview_availability));
      })
      .catch((error) => addToast(
        error.response?.data?.detail || 'Unable to load settings.',
        'error',
      ))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [user, reset, workingCompanyId, addToast]);

  useEffect(() => {
    setNotifications(notificationPreferences);
  }, [notificationPreferences]);

  useEffect(() => {
    if (!isSuperAdmin(user?.role) && (activeTab === 'model' || activeTab === 'company' || activeTab === 'api')) {
      setActiveTab('profile');
    }
  }, [user?.role, activeTab]);

  const onSave = async (values) => {
    setSaving(true);
    try {
      if (activeTab === 'profile') {
        const { data } = await updateProfileSettings({
          full_name: values.name,
          email: values.email,
          job_title: values.jobTitle,
          phone: values.phone,
        });
        updateCurrentUser(data);
      } else if (activeTab === 'company') {
        await updateCompanySettings({
          company_name: values.company,
          website: values.website,
          industry: values.industry,
          company_size: values.companySize,
          headquarters: values.headquarters,
          timezone: values.timezone,
        });
      } else if (activeTab === 'appearance') {
        await saveAppearance();
        return;
      } else if (activeTab === 'notifications') {
        await saveNotificationPreferences(notifications);
      } else if (activeTab === 'model') {
        await updateAIModelSettings({
          provider: values.provider || 'groq',
          model_id: values.model,
          temperature: Number(values.temperature),
          max_tokens: Number(values.maxTokens),
          prompt_style: values.promptStyle,
        });
      } else if (activeTab === 'api') {
        addToast('Integration secrets are managed securely on the backend.', 'info');
        return;
      } else if (activeTab === 'interview') {
        return;
      }
      addToast('Settings saved successfully.', 'success');
    } catch (error) {
      addToast(error.response?.data?.detail || 'Failed to save settings.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const saveInterviewHours = async (payload) => {
    setSaving(true);
    try {
      const { data } = await updateInterviewAvailability(payload);
      setAvailability(normalizeAvailability(data.availability || payload));
      addToast(
        `Interview hours saved. ${data.created || 0} slots added, ${data.removed || 0} unused slots removed.`,
        'success',
      );
    } catch (error) {
      addToast(error.response?.data?.detail || 'Failed to save interview hours.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    try {
      const { data } = await testIntegrationConnection();
      setIntegration((current) => ({
        ...current,
        backend_connected: data.ok,
        api_key_configured: data.provider_configured,
        message: data.message,
      }));
      addToast(data.message, data.ok ? 'success' : 'error');
    } catch (error) {
      setIntegration((current) => ({
        ...current,
        backend_connected: false,
        message: error.response?.data?.detail || 'Connection failed.',
      }));
      addToast('Backend connection failed.', 'error');
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'profile':
        return (
          <div className="space-y-5">
            <div className="flex items-center gap-5 p-5 bg-slate-50 dark:bg-slate-800/50 rounded-2xl">
              <div className="w-16 h-16 rounded-2xl bg-primary-accent flex items-center justify-center text-white text-xl font-bold">
                {(user?.full_name || 'HR').split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}
              </div>
              <div>
                <p className="font-semibold text-col">{user?.full_name || 'HR User'}</p>
                <p className="text-sm text-muted">
                  {user?.job_title || user?.role || 'HR'}
                  {user?.company?.name ? ` · ${user.company.name}` : ''}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Full Name">
                <input {...register('name')} className={inputCls} />
              </FormField>
              <FormField label="Email">
                <input {...register('email')} type="email" className={inputCls} />
              </FormField>
              <FormField label="Job Title">
                <input {...register('jobTitle')} className={inputCls} />
              </FormField>
              <FormField label="Phone">
                <input {...register('phone')} placeholder="+91 98765 43210" className={inputCls} />
              </FormField>
            </div>
          </div>
        );

      case 'company':
        return (
          <div className="space-y-4 grid grid-cols-2 gap-4">
            <FormField label="Company Name">
              <input {...register('company')} className={inputCls} />
            </FormField>
            <FormField label="Website">
              <input {...register('website')} className={inputCls} />
            </FormField>
            <FormField label="Industry">
              <select {...register('industry')} className={inputCls}>
                {['Technology', 'Finance', 'Healthcare', 'Education', 'E-commerce'].map(i => <option key={i}>{i}</option>)}
              </select>
            </FormField>
            <FormField label="Company Size">
              <select {...register('companySize')} className={inputCls}>
                {['1-50', '51-200', '201-1000', '1000+'].map(s => (
                  <option key={s} value={s}>{s} employees</option>
                ))}
              </select>
            </FormField>
            <FormField label="Headquarters Location">
              <input {...register('headquarters')} placeholder="e.g. Mumbai, India" className={inputCls} />
            </FormField>
            <FormField label="Timezone">
              <select {...register('timezone')} className={inputCls}>
                <option value="Asia/Kolkata">Asia/Kolkata (IST, UTC+5:30)</option>
                <option value="Asia/Dubai">Asia/Dubai (GST, UTC+4)</option>
                <option value="Europe/London">Europe/London (GMT, UTC+0)</option>
              </select>
            </FormField>
          </div>
        );

      case 'api':
        return (
          <div className="space-y-5">
            <FormField label="FastAPI Backend Endpoint" hint="Configured when the frontend is deployed">
              <input
                value={import.meta.env.VITE_API_URL || '/api'}
                readOnly
                className={`${inputCls} bg-slate-50 dark:bg-slate-800`}
              />
            </FormField>
            <FormField label="Groq / Azure keys" hint="SuperAdmin edits keys on SuperAdmin → API & Integration. Full secrets are never shown here.">
              <input
                value={integration?.api_key_masked || 'Checking…'}
                readOnly
                className={`${inputCls} bg-slate-50 dark:bg-slate-800`}
              />
            </FormField>
            <div>
              <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Connection Status</h4>
              <div className={`flex items-center gap-3 p-3 rounded-xl border ${
                integration?.backend_connected
                  ? 'bg-emerald-50 dark:bg-emerald-900/10 border-emerald-100 dark:border-emerald-800'
                  : 'bg-amber-50 dark:bg-amber-900/10 border-amber-100 dark:border-amber-800'
              }`}>
                <div className={`w-2.5 h-2.5 rounded-full ${
                  integration?.backend_connected ? 'bg-emerald-500' : 'bg-amber-400 animate-pulse'
                }`} />
                <p className={`text-sm ${
                  integration?.backend_connected
                    ? 'text-emerald-700 dark:text-emerald-400'
                    : 'text-amber-700 dark:text-amber-400'
                }`}>
                  {integration?.message || 'Checking connection…'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={testConnection}
              className="px-4 py-2 rounded-xl border border-col text-sm font-medium text-col hover:bg-slate-50 dark:hover:bg-slate-800 transition-all"
            >
              Test Connection
            </button>
          </div>
        );

      case 'appearance':
        return (
          <div className="space-y-6">
            <div>
              <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Theme</h4>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { id: 'light', label: 'Light', preview: 'bg-white border-2' },
                  { id: 'dark', label: 'Dark', preview: 'bg-slate-900 border-2' },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTheme(t.id)}
                    className={`p-4 rounded-xl border-2 text-left transition-all ${
                      appearance.theme === t.id ? 'border-primary-accent ring-primary-accent' : 'border-col hover:border-slate-400'
                    }`}
                  >
                    <div className={`w-full h-10 rounded-lg mb-2 ${t.preview} border-col`} />
                    <p className="text-sm font-medium text-col">{t.label}</p>
                    {appearance.theme === t.id && <p className="text-xs text-primary-accent">Active</p>}
                  </button>
                ))}
              </div>
            </div>
            <FormField label="Primary Color" hint="Used for buttons, links, and accents. Orange matches the RR Parkon logo by default.">
              <div className="flex flex-wrap gap-3">
                {PRIMARY_COLORS.map((color) => (
                  <button
                    key={color.id}
                    type="button"
                    title={color.label}
                    onClick={() => setPrimaryColorId(color.id)}
                    className={`w-10 h-10 rounded-lg border-2 transition-all ${
                      appearance.primaryColorId === color.id
                        ? 'border-primary-accent ring-primary-accent scale-105'
                        : 'border-transparent hover:border-slate-300'
                    }`}
                    style={{ background: color.primary }}
                  />
                ))}
              </div>
            </FormField>
          </div>
        );

      case 'notifications':
        return (
          <div className="space-y-4">
            {[
              { label: 'New Candidate Uploaded', desc: 'When a resume is added to the system', key: 'new_candidate_uploaded' },
              { label: 'AI Screening Complete', desc: 'When AI finishes processing resumes', key: 'ai_screening_complete' },
              { label: 'Candidate Shortlisted', desc: 'When a candidate is shortlisted', key: 'candidate_shortlisted' },
              { label: 'Job Application Received', desc: 'When a new job application comes in', key: 'job_application_received' },
              { label: 'Weekly Report', desc: 'Summary of hiring metrics every Monday', key: 'weekly_report' },
            ].map(n => (
              <div key={n.key} className="flex items-center justify-between p-4 rounded-xl border border-col">
                <div>
                  <p className="text-sm font-medium text-col">{n.label}</p>
                  <p className="text-xs text-muted mt-0.5">{n.desc}</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifications[n.key] ?? true}
                    onChange={(event) => setNotifications((current) => ({
                      ...current,
                      [n.key]: event.target.checked,
                    }))}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-200 dark:bg-slate-700 peer-checked:bg-primary-accent rounded-full peer peer-checked:after:translate-x-5 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:w-4 after:h-4 after:bg-white after:rounded-full after:transition-all" />
                </label>
              </div>
            ))}
          </div>
        );

      case 'interview':
        return (
          <InterviewHoursForm value={availability} onSave={saveInterviewHours} saving={saving} />
        );

      case 'model':
        return (
          <div className="space-y-5">
            <div className="p-4 rounded-xl bg-violet-50 dark:bg-violet-900/10 border border-violet-100 dark:border-violet-800">
              <div className="flex items-center gap-2 mb-1">
                <Cpu size={16} className="text-violet-500" />
                <p className="font-semibold text-sm text-violet-700 dark:text-violet-400">Groq Screening Model</p>
              </div>
              <p className="text-xs text-violet-600 dark:text-violet-400">
                Advanced reasoning model powering your resume screening. Configure parameters below to tune screening quality.
              </p>
            </div>
            <FormField label="Model">
              <select {...register('model')} className={inputCls}>
                <option value="openai/gpt-oss-120b">openai/gpt-oss-120b</option>
                <option value="openai/gpt-oss-20b">openai/gpt-oss-20b</option>
              </select>
            </FormField>
            <FormField label="Temperature" hint="Lower values (0.1–0.3) give more consistent results. Higher values (0.7+) add creativity.">
              <div className="flex items-center gap-3">
                <input
                  {...register('temperature')}
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  className="flex-1 accent-blue-500"
                />
                <span className="text-sm font-mono text-col w-10">
                  {Number(watch('temperature') || 0).toFixed(2)}
                </span>
              </div>
            </FormField>
            <FormField label="Max Tokens" hint="Maximum response length for AI analysis per candidate">
              <input {...register('maxTokens')} type="number" min="256" max="8192" className={inputCls} />
            </FormField>
            <FormField label="Screening Prompt Style">
              <select {...register('promptStyle')} className={inputCls}>
                <option value="detailed_analysis">Detailed Analysis (Recommended)</option>
                <option value="quick_summary">Quick Summary</option>
                <option value="technical_focus">Technical Focus</option>
                <option value="cultural_fit_focus">Cultural Fit Focus</option>
              </select>
            </FormField>
          </div>
        );

      default:
        return null;
    }
  };

  if (loading) {
    return <div className="card p-8 text-sm text-muted">Loading settings…</div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-col">Settings</h2>
        <p className="text-sm text-muted">Manage your account, company, and AI preferences</p>
      </div>

      <div className="flex gap-6">
        {/* Tabs */}
        <div className="w-48 flex-shrink-0">
          <nav className="space-y-1">
            {visibleTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium text-left transition-all ${
                  activeTab === tab.id
                    ? 'nav-active'
                    : 'text-muted hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-col'
                }`}
              >
                <tab.icon size={15} className="flex-shrink-0" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'interview' ? (
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.15 }}
              className="card p-6"
            >
              {renderContent()}
            </motion.div>
          ) : (
            <form onSubmit={handleSubmit(onSave)}>
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.15 }}
                className="card p-6 space-y-5"
              >
                {renderContent()}

                <div className="pt-4 border-t border-col">
                  <button
                    type="submit"
                    disabled={saving}
                    className="btn-primary flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-60"
                  >
                    <Save size={15} />
                    {saving ? 'Saving…' : 'Save Changes'}
                  </button>
                </div>
              </motion.div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
