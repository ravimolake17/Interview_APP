import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { User, Palette, Bell, Save, Clock } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { PRIMARY_COLORS } from '../../utils/theme';
import {
  getSettings,
  updateInterviewAvailability,
  updateProfileSettings,
} from '../../services/api';
import InterviewHoursForm, { normalizeAvailability } from '../../components/InterviewHoursForm';

const TABS = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'interview', label: 'Interview hours', icon: Clock },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'notifications', label: 'Notifications', icon: Bell },
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
  const [notifications, setNotifications] = useState(notificationPreferences);
  const [availability, setAvailability] = useState(normalizeAvailability());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { register, handleSubmit, reset } = useForm({
    defaultValues: {
      name: user?.full_name || '',
      email: user?.email || '',
      jobTitle: user?.job_title || '',
      phone: user?.phone || '',
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
        });
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
      } else if (activeTab === 'appearance') {
        await saveAppearance();
        return;
      } else if (activeTab === 'notifications') {
        await saveNotificationPreferences(notifications);
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
        <p className="text-sm text-muted">Manage your account, interview hours, and preferences</p>
      </div>

      <div className="flex gap-6">
        <div className="w-48 flex-shrink-0">
          <nav className="space-y-1">
            {TABS.map(tab => (
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
