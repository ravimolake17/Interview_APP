import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Building2,
  Cpu,
  FileText,
  Globe,
  Layers,
  Link as LinkIcon,
  Mail,
  Plus,
  Save,
  Shield,
  SlidersHorizontal,
  Table2,
  Users,
} from 'lucide-react';
import {
  createCompany,
  createDepartment,
  createUser,
  getAuditLogs,
  getCompanies,
  getManagedDepartments,
  getSuperAdminSystem,
  getUsers,
  testIntegrationConnection,
  updateAIModelSettings,
  updateCompany,
  updateDepartment,
  updateIntegrationSettings,
  updateCompanySmtp,
  updateScreeningPolicy,
  updateSuperAdminCompany,
  updateUser,
} from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import PasswordInput from '../components/PasswordInput';
import DatabaseBrowser from './superadmin/DatabaseBrowser';
import DataManagement from './superadmin/DataManagement';
import { isValidEmail, isValidPassword } from '../utils/validation';
import { useAuth } from '../context/AuthContext';
import { useApp } from '../context/AppContext';
import CompanyTableFilter, { companyLabel, matchesCompanyFilter } from '../components/CompanyTableFilter';

const TABS = [
  { id: 'overview', label: 'Overview', icon: Shield },
  { id: 'companies', label: 'Companies', icon: Globe },
  { id: 'admins', label: 'Admins', icon: Users },
  { id: 'departments', label: 'Departments', icon: Building2 },
  { id: 'llm', label: 'LLM & AI', icon: Cpu },
  { id: 'integration', label: 'API & Integration', icon: LinkIcon },
  { id: 'screening', label: 'Screening', icon: SlidersHorizontal },
  { id: 'company', label: 'Company', icon: Globe },
  { id: 'data', label: 'Data Management', icon: Layers },
  { id: 'database', label: 'Database Console', icon: Table2 },
  { id: 'audit', label: 'Audit Log', icon: FileText },
];

const EMPTY_ADMIN = {
  email: '',
  full_name: '',
  password: '',
  role: 'COMPANY_ADMIN',
  company_id: '',
  is_active: true,
};

const EMPTY_DEPT = {
  name: '',
  description: '',
  sort_order: 0,
  company_id: '',
};

const EMPTY_COMPANY = {
  name: '',
  code: '',
  logo: '',
  status: 'active',
};

const GROQ_MODEL_REPLACEMENTS = {
  'llama-3.3-70b-versatile': 'openai/gpt-oss-120b',
  'llama-3.1-8b-instant': 'openai/gpt-oss-20b',
};

const AZURE_DEPLOYMENTS = [
  { value: 'gpt-4o', label: 'gpt-4o' },
  { value: 'gpt-4o-mini', label: 'gpt-4o mini' },
];
const AZURE_DEPLOYMENT_IDS = AZURE_DEPLOYMENTS.map((item) => item.value);

function resolveAzureDeployment(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/\s+/g, '-');
  if (AZURE_DEPLOYMENT_IDS.includes(normalized)) return normalized;
  if (normalized === 'gpt-4o-mini' || normalized === 'gpt4o-mini' || normalized === 'gpt-4omini') return 'gpt-4o-mini';
  return 'gpt-4o';
}

const inputCls = 'input-field';
const labelCls = 'text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5';

function StatCard({ label, value, hint }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wider text-muted font-semibold">{label}</p>
      <p className="text-2xl font-bold text-col mt-1">{value}</p>
      {hint && <p className="text-xs text-muted mt-1">{hint}</p>}
    </div>
  );
}

export default function SuperAdmin() {
  const { user: currentUser } = useAuth();
  const { refreshData, workingCompanyId, switchWorkingCompany, reloadCompanies } = useApp();
  const [tab, setTab] = useState('overview');
  const [system, setSystem] = useState(null);
  const [users, setUsers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [companyRecordForm, setCompanyRecordForm] = useState(EMPTY_COMPANY);
  const [editingCompanyId, setEditingCompanyId] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [adminForm, setAdminForm] = useState(EMPTY_ADMIN);
  const [editingAdminId, setEditingAdminId] = useState(null);
  const [deptForm, setDeptForm] = useState(EMPTY_DEPT);
  const [editingDeptId, setEditingDeptId] = useState(null);
  const [llmForm, setLlmForm] = useState({
    provider: 'groq',
    model_id: 'openai/gpt-oss-120b',
    temperature: 0,
    max_tokens: 8192,
    prompt_style: 'detailed_analysis',
    azure_openai_endpoint: '',
    azure_openai_deployment: 'gpt-4o',
    azure_openai_api_version: '2024-10-21',
    stt_provider: 'groq',
    tts_provider: 'edge',
    azure_speech_region: 'eastus2',
    azure_speech_stt_endpoint: '',
    azure_speech_tts_endpoint: '',
  });
  const [integrationForm, setIntegrationForm] = useState({
    groq_api_key: '',
    azure_openai_api_key: '',
    azure_speech_key: '',
    frontend_url: '',
    agent5_public_url: '',
  });
  const [smtpForms, setSmtpForms] = useState({});
  const [companyForm, setCompanyForm] = useState({
    company_name: '',
    website: '',
    industry: '',
    company_size: '',
    headquarters: '',
    timezone: 'Asia/Kolkata',
  });
  const [screeningForm, setScreeningForm] = useState({
    shortlist_threshold: 75,
    review_threshold: 55,
    use_llm_for_jd_parsing: true,
    use_llm_for_resume_parsing: true,
  });
  const [auditEntries, setAuditEntries] = useState([]);
  const [companyFilter, setCompanyFilter] = useState('all');

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [systemRes, usersRes, deptRes, companiesRes] = await Promise.all([
        getSuperAdminSystem(),
        getUsers(),
        getManagedDepartments({ include_all: true }),
        getCompanies(),
      ]);
      setSystem(systemRes.data);
      setUsers(usersRes.data.users || []);
      setDepartments(deptRes.data.departments || []);
      setCompanies(companiesRes.data.companies || []);
      const ai = systemRes.data?.ai_model;
      if (ai) {
        const provider = ai.provider || 'groq';
        const azureDeployment = resolveAzureDeployment(ai.azure_openai_deployment || ai.model_id);
        setLlmForm({
          provider,
          model_id: provider === 'azure' ? azureDeployment : (GROQ_MODEL_REPLACEMENTS[ai.model_id] || ai.model_id),
          temperature: ai.temperature,
          max_tokens: ai.max_tokens,
          prompt_style: ai.prompt_style,
          azure_openai_endpoint: ai.azure_openai_endpoint || '',
          azure_openai_deployment: azureDeployment,
          azure_openai_api_version: ai.azure_openai_api_version || '2024-10-21',
          stt_provider: ai.stt_provider || 'groq',
          tts_provider: ai.tts_provider || 'edge',
          azure_speech_region: ai.azure_speech_region || 'eastus2',
          azure_speech_stt_endpoint: ai.azure_speech_stt_endpoint || '',
          azure_speech_tts_endpoint: ai.azure_speech_tts_endpoint || '',
        });
      }
      const integration = systemRes.data?.integration;
      if (integration) {
        setIntegrationForm({
          groq_api_key: '',
          azure_openai_api_key: '',
          azure_speech_key: '',
          frontend_url: integration.frontend_url || '',
          agent5_public_url: integration.agent5_public_url || '',
        });
      }
      const smtpAccounts = systemRes.data?.smtp_accounts || [];
      setSmtpForms(
        Object.fromEntries(
          smtpAccounts.map((account) => [
            account.company_id,
            {
              company_id: account.company_id,
              company_name: account.company_name,
              company_code: account.company_code,
              host: account.host || '',
              port: account.port || 587,
              username: account.username || '',
              password: '',
              from_email: account.from_email || '',
              from_name: account.from_name || '',
              use_tls: Boolean(account.use_tls),
              use_ssl: Boolean(account.use_ssl),
              timeout_seconds: account.timeout_seconds || 30,
              password_masked: account.password_masked,
              using_env_fallback: account.using_env_fallback,
            },
          ]),
        ),
      );
      const company = systemRes.data?.company;
      if (company) setCompanyForm(company);
      const policy = systemRes.data?.screening_policy;
      if (policy) setScreeningForm(policy);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load SuperAdmin data.');
    } finally {
      setLoading(false);
    }
  }, [workingCompanyId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (workingCompanyId) setCompanyFilter(String(workingCompanyId));
    setDeptForm((current) => (
      current.company_id || editingDeptId
        ? current
        : { ...current, company_id: workingCompanyId ? String(workingCompanyId) : '' }
    ));
  }, [workingCompanyId, editingDeptId]);

  useEffect(() => {
    if (tab !== 'audit') return;
    getAuditLogs(25, companyFilter === 'all' ? undefined : companyFilter)
      .then((res) => setAuditEntries(res.data.entries || []))
      .catch(() => setAuditEntries([]));
  }, [tab, companyFilter]);

  const admins = users.filter(
    (user) => user.role === 'ADMIN' || user.role === 'COMPANY_ADMIN' || user.role === 'SUPERADMIN' || user.role === 'HR',
  );
  const visibleAdmins = admins.filter((user) => matchesCompanyFilter(user, companyFilter));
  const visibleDepartments = departments.filter((department) => matchesCompanyFilter(department, companyFilter));

  const saveCompanyRecord = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: companyRecordForm.name.trim(),
        code: companyRecordForm.code.trim().toUpperCase(),
        logo: companyRecordForm.logo.trim() || null,
        status: companyRecordForm.status,
      };
      if (editingCompanyId) {
        await updateCompany(editingCompanyId, payload);
        setMessage('Company updated.');
      } else {
        await createCompany(payload);
        setMessage('Company created.');
      }
      setCompanyRecordForm(EMPTY_COMPANY);
      setEditingCompanyId(null);
      await reloadCompanies();
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save company.');
    } finally {
      setSaving(false);
    }
  };

  const saveAdmin = async (event) => {
    event.preventDefault();
    const emailErr = isValidEmail(adminForm.email);
    if (emailErr) {
      setError(emailErr);
      return;
    }
    if (!editingAdminId) {
      const passErr = isValidPassword(adminForm.password);
      if (passErr) {
        setError(passErr);
        return;
      }
    }
    setSaving(true);
    setMessage(null);
    try {
      if (editingAdminId) {
        const payload = {
          email: adminForm.email,
          full_name: adminForm.full_name,
          role: adminForm.role,
          is_active: adminForm.is_active,
          company_id: adminForm.role === 'SUPERADMIN' ? null : Number(adminForm.company_id) || null,
        };
        if (adminForm.password) payload.password = adminForm.password;
        await updateUser(editingAdminId, payload);
        setMessage('Admin account updated.');
      } else {
        if (adminForm.role !== 'SUPERADMIN' && !adminForm.company_id) {
          setError('Assign this user to a company.');
          setSaving(false);
          return;
        }
        await createUser({
          ...adminForm,
          company_id: adminForm.role === 'SUPERADMIN' ? null : Number(adminForm.company_id),
        });
        setMessage('Admin account created.');
      }
      setAdminForm(EMPTY_ADMIN);
      setEditingAdminId(null);
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save admin.');
    } finally {
      setSaving(false);
    }
  };

  const saveDepartment = async (event) => {
    event.preventDefault();
    if (!deptForm.name.trim()) return;
    if (!editingDeptId && !deptForm.company_id) {
      setError('Select a company for this department.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (editingDeptId) {
        await updateDepartment(editingDeptId, {
          name: deptForm.name.trim(),
          description: deptForm.description,
        });
        setMessage('Department updated.');
      } else {
        await createDepartment({
          name: deptForm.name.trim(),
          description: deptForm.description,
          sort_order: Number(deptForm.sort_order) || departments.length,
          is_active: true,
          company_id: Number(deptForm.company_id),
        });
        setMessage('Department added.');
      }
      setDeptForm({
        ...EMPTY_DEPT,
        company_id: deptForm.company_id || (workingCompanyId ? String(workingCompanyId) : ''),
      });
      setEditingDeptId(null);
      await loadAll();
      await refreshData({ silent: true, force: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save department.');
    } finally {
      setSaving(false);
    }
  };

  const toggleDepartment = async (department) => {
    setError(null);
    try {
      await updateDepartment(department.id, { is_active: !department.is_active });
      await loadAll();
      await refreshData({ silent: true, force: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update department.');
    }
  };

  const saveLlm = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await updateAIModelSettings({
        provider: llmForm.provider,
        model_id: llmForm.provider === 'azure' ? resolveAzureDeployment(llmForm.azure_openai_deployment) : llmForm.model_id,
        temperature: Number(llmForm.temperature),
        max_tokens: Number(llmForm.max_tokens),
        prompt_style: llmForm.prompt_style,
        azure_openai_endpoint: llmForm.azure_openai_endpoint,
        azure_openai_deployment: llmForm.provider === 'azure' ? resolveAzureDeployment(llmForm.azure_openai_deployment) : llmForm.azure_openai_deployment,
        azure_openai_api_version: llmForm.azure_openai_api_version,
        stt_provider: llmForm.stt_provider,
        tts_provider: llmForm.tts_provider,
        azure_speech_region: llmForm.azure_speech_region,
        azure_speech_stt_endpoint: llmForm.azure_speech_stt_endpoint,
        azure_speech_tts_endpoint: llmForm.azure_speech_tts_endpoint,
      });
      setMessage('LLM, STT, and TTS settings saved.');
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save LLM settings.');
    } finally {
      setSaving(false);
    }
  };

  const saveIntegration = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await updateIntegrationSettings({
        groq_api_key: integrationForm.groq_api_key,
        azure_openai_api_key: integrationForm.azure_openai_api_key,
        azure_speech_key: integrationForm.azure_speech_key,
        frontend_url: integrationForm.frontend_url,
        agent5_public_url: integrationForm.agent5_public_url,
      });
      setMessage('API keys and public URLs saved. Secrets stay masked and are never shown in full.');
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save API integration settings.');
    } finally {
      setSaving(false);
    }
  };

  const saveSmtp = async (event, companyId) => {
    event.preventDefault();
    const form = smtpForms[companyId];
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      await updateCompanySmtp(companyId, {
        host: form.host,
        port: Number(form.port),
        username: form.username,
        password: form.password,
        from_email: form.from_email,
        from_name: form.from_name,
        use_tls: Boolean(form.use_tls),
        use_ssl: Boolean(form.use_ssl),
        timeout_seconds: Number(form.timeout_seconds),
      });
      setMessage(`SMTP saved for ${form.company_name}. Password stays hidden.`);
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save SMTP settings.');
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTestingConnection(true);
    setError(null);
    try {
      const { data } = await testIntegrationConnection();
      setMessage(data.message || 'Backend and Groq are configured.');
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Connection test failed.');
    } finally {
      setTestingConnection(false);
    }
  };

  const saveCompany = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await updateSuperAdminCompany(companyForm);
      setMessage('Company settings saved.');
      await loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not save company settings.');
    } finally {
      setSaving(false);
    }
  };

  const saveScreening = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await updateScreeningPolicy({
        shortlist_threshold: Number(screeningForm.shortlist_threshold),
        review_threshold: Number(screeningForm.review_threshold),
        use_llm_for_jd_parsing: Boolean(screeningForm.use_llm_for_jd_parsing),
        use_llm_for_resume_parsing: Boolean(screeningForm.use_llm_for_resume_parsing),
      });
      setMessage('Screening policy saved.');
      await loadAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Could not save screening policy.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16">
        <LoadingSpinner message="Loading SuperAdmin control plane..." />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      <div>
        <h2 className="text-xl font-bold text-col">SuperAdmin Control Plane</h2>
        <p className="text-sm text-muted mt-1">
          Enterprise access for admins, departments, LLM, screening, company, data management, and the database console. Signed in as {currentUser?.email}.
        </p>
      </div>

      {error && (
        <div className="card bg-red-50 dark:bg-red-900/20 border border-red-200 text-red-700 dark:text-red-300 text-sm px-4 py-3">
          {error}
        </div>
      )}
      {message && (
        <div className="card bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 text-emerald-700 text-sm px-4 py-3">
          {message}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setTab(item.id);
              setError(null);
              setMessage(null);
            }}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium ${
              tab === item.id ? 'nav-active' : 'text-muted hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <item.icon size={15} />
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && system && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total users" value={system.users.total} hint={`${system.users.superadmin} SuperAdmin · ${system.users.admin || system.users.company_admin || 0} Company Admin · ${system.users.hr} HR`} />
          <StatCard label="Companies" value={companies.length} hint={companies.map((c) => c.name).join(' · ') || '—'} />
          <StatCard label="Queue pending" value={system.screening_queue.pending} hint={`${system.screening_queue.processing} processing`} />
          <StatCard label="Database" value={system.database.health} hint={`${system.database.engine} · ${system.database.environment}`} />
          <StatCard label="LLM" value={system.ai_model.model_id} hint={`temp ${system.ai_model.temperature}`} />
          <StatCard label="Departments" value={departments.length} hint={`${departments.filter((row) => row.is_active).length} active`} />
          <StatCard label="Company" value={system.company?.company_name || '—'} hint={system.company?.headquarters} />
          <StatCard label="Shortlist" value={system.screening_policy?.shortlist_threshold} hint={`review ${system.screening_policy?.review_threshold}`} />
          <StatCard label="SMTP" value={system.platform?.smtp_configured ? 'Configured' : 'Missing'} hint={system.platform?.smtp_host} />
        </div>
      )}

      {tab === 'companies' && (
        <div className="grid lg:grid-cols-5 gap-5">
          <form onSubmit={saveCompanyRecord} className="lg:col-span-2 card p-5 space-y-3">
            <h3 className="font-semibold text-col">{editingCompanyId ? 'Edit company' : 'Create company'}</h3>
            <input className={inputCls} placeholder="Company name" value={companyRecordForm.name} onChange={(e) => setCompanyRecordForm((f) => ({ ...f, name: e.target.value }))} required />
            <input className={inputCls} placeholder="Code (e.g. RRKABEL)" value={companyRecordForm.code} onChange={(e) => setCompanyRecordForm((f) => ({ ...f, code: e.target.value }))} required />
            <input className={inputCls} placeholder="Logo URL (optional)" value={companyRecordForm.logo} onChange={(e) => setCompanyRecordForm((f) => ({ ...f, logo: e.target.value }))} />
            <select className={inputCls} value={companyRecordForm.status} onChange={(e) => setCompanyRecordForm((f) => ({ ...f, status: e.target.value }))}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <button type="submit" disabled={saving} className="btn-primary w-full">
              {saving ? 'Saving…' : editingCompanyId ? 'Update company' : 'Create company'}
            </button>
            {editingCompanyId && (
              <button type="button" className="btn-secondary w-full" onClick={() => { setEditingCompanyId(null); setCompanyRecordForm(EMPTY_COMPANY); }}>
                Cancel
              </button>
            )}
          </form>
          <div className="lg:col-span-3 card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">Company</th>
                  <th className="text-left px-4 py-3">Code</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-col">
                {companies.map((company) => (
                  <tr key={company.id}>
                    <td className="px-4 py-3 font-medium text-col">{company.name}</td>
                    <td className="px-4 py-3 text-col">{company.code}</td>
                    <td className="px-4 py-3">{company.status}</td>
                    <td className="px-4 py-3 text-right space-x-3">
                      <button
                        type="button"
                        className="text-blue-600 text-xs font-medium"
                        onClick={() => {
                          switchWorkingCompany(company.id);
                          setMessage(`Now working in ${company.name}. Dashboard, candidates, and settings will show this company.`);
                        }}
                      >
                        Use
                      </button>
                      <button
                        type="button"
                        className="text-blue-600 text-xs font-medium"
                        onClick={() => {
                          setEditingCompanyId(company.id);
                          setCompanyRecordForm({
                            name: company.name,
                            code: company.code,
                            logo: company.logo || '',
                            status: company.status,
                          });
                        }}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {workingCompanyId && (
              <p className="px-4 py-3 text-xs text-muted border-t border-col">
                Currently viewing company #{workingCompanyId}. Use Switch company in the top-right to change.
              </p>
            )}
          </div>
        </div>
      )}

      {tab === 'admins' && (
        <div className="grid lg:grid-cols-5 gap-5">
          <form onSubmit={saveAdmin} className="lg:col-span-2 card p-5 space-y-3">
            <h3 className="font-semibold text-col">{editingAdminId ? 'Edit admin' : 'Create admin'}</h3>
            <input className={inputCls} placeholder="Full name" value={adminForm.full_name} onChange={(e) => setAdminForm((f) => ({ ...f, full_name: e.target.value }))} required />
            <input className={inputCls} placeholder="Email" value={adminForm.email} onChange={(e) => setAdminForm((f) => ({ ...f, email: e.target.value }))} required />
            <PasswordInput
              id="sa-admin-password"
              label={editingAdminId ? 'New password (optional)' : 'Password'}
              value={adminForm.password}
              onChange={(e) => setAdminForm((f) => ({ ...f, password: e.target.value }))}
              required={!editingAdminId}
            />
            <select className={inputCls} value={adminForm.role} onChange={(e) => setAdminForm((f) => ({ ...f, role: e.target.value }))}>
              <option value="HR">HR</option>
              <option value="COMPANY_ADMIN">Company Admin</option>
              <option value="SUPERADMIN">Super Admin</option>
            </select>
            {adminForm.role !== 'SUPERADMIN' && (
              <select className={inputCls} value={adminForm.company_id} onChange={(e) => setAdminForm((f) => ({ ...f, company_id: e.target.value }))} required>
                <option value="">Select company</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>{company.name}</option>
                ))}
              </select>
            )}
            <label className="flex items-center gap-2 text-sm text-col">
              <input
                type="checkbox"
                checked={adminForm.is_active}
                onChange={(e) => setAdminForm((f) => ({ ...f, is_active: e.target.checked }))}
                className="rounded border-col"
              />
              Active account
            </label>
            <button type="submit" disabled={saving} className="btn-primary w-full">
              {saving ? 'Saving…' : editingAdminId ? 'Update' : 'Create admin'}
            </button>
            {editingAdminId && (
              <button
                type="button"
                className="btn-secondary w-full"
                onClick={() => {
                  setEditingAdminId(null);
                  setAdminForm(EMPTY_ADMIN);
                }}
              >
                Cancel
              </button>
            )}
          </form>
          <div className="lg:col-span-3 card p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-col flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-medium text-col">Company users</p>
              <CompanyTableFilter value={companyFilter} onChange={setCompanyFilter} companies={companies} />
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">User</th>
                  <th className="text-left px-4 py-3">Role</th>
                  <th className="text-left px-4 py-3">Company</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-col">
                {visibleAdmins.map((user) => (
                  <tr key={user.id}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-col">{user.full_name}</p>
                      <p className="text-xs text-muted">{user.email}</p>
                    </td>
                    <td className="px-4 py-3 text-col">{user.role}</td>
                    <td className="px-4 py-3 text-col">{companyLabel(user)}</td>
                    <td className="px-4 py-3">{user.is_active ? 'Active' : 'Inactive'}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        className="text-blue-600 text-xs font-medium"
                        onClick={() => {
                          setEditingAdminId(user.id);
                          setAdminForm({
                            email: user.email,
                            full_name: user.full_name,
                            password: '',
                            role: user.role === 'ADMIN' ? 'COMPANY_ADMIN' : user.role,
                            company_id: user.company_id || '',
                            is_active: user.is_active,
                          });
                        }}
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'departments' && (
        <div className="space-y-4">
          <form onSubmit={saveDepartment} className="card p-5 grid sm:grid-cols-5 gap-3">
            <input className={inputCls} placeholder="Department name" value={deptForm.name} onChange={(e) => setDeptForm((f) => ({ ...f, name: e.target.value }))} required />
            <input className={`${inputCls} sm:col-span-2`} placeholder="Description" value={deptForm.description} onChange={(e) => setDeptForm((f) => ({ ...f, description: e.target.value }))} />
            <select
              className={inputCls}
              value={deptForm.company_id}
              onChange={(e) => setDeptForm((f) => ({ ...f, company_id: e.target.value }))}
              required={!editingDeptId}
              disabled={Boolean(editingDeptId)}
            >
              <option value="">Select company</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>{company.name}</option>
              ))}
            </select>
            <button type="submit" className="btn-primary inline-flex items-center justify-center gap-2">
              <Plus size={14} /> {editingDeptId ? 'Save' : 'Add'}
            </button>
            {editingDeptId && (
              <button
                type="button"
                className="btn-secondary sm:col-start-5"
                onClick={() => {
                  setEditingDeptId(null);
                  setDeptForm({
                    ...EMPTY_DEPT,
                    company_id: workingCompanyId ? String(workingCompanyId) : '',
                  });
                }}
              >
                Cancel
              </button>
            )}
          </form>
          <div className="card p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-col flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-medium text-col">Company departments</p>
              <CompanyTableFilter value={companyFilter} onChange={setCompanyFilter} companies={companies} />
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">Department</th>
                  <th className="text-left px-4 py-3">Company</th>
                  <th className="text-left px-4 py-3">Description</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-col">
                {visibleDepartments.map((department) => (
                  <tr key={department.id}>
                    <td className="px-4 py-3 font-medium text-col">{department.name}</td>
                    <td className="px-4 py-3 text-muted">{companyLabel(department)}</td>
                    <td className="px-4 py-3 text-muted">{department.description || '—'}</td>
                    <td className="px-4 py-3">{department.is_active ? 'Active' : 'Inactive'}</td>
                    <td className="px-4 py-3 text-right space-x-3">
                      <button
                        type="button"
                        className="text-blue-600 text-xs font-medium"
                        onClick={() => {
                          setEditingDeptId(department.id);
                          setDeptForm({
                            name: department.name,
                            description: department.description || '',
                            sort_order: department.sort_order || 0,
                            company_id: department.company_id ? String(department.company_id) : '',
                          });
                        }}
                      >
                        Edit
                      </button>
                      <button type="button" className="text-blue-600 text-xs font-medium" onClick={() => toggleDepartment(department)}>
                        {department.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
                {visibleDepartments.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted">
                      No departments for this company yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'llm' && (
        <form onSubmit={saveLlm} className="card p-6 max-w-3xl space-y-4">
          <p className="text-sm text-muted">
            Choose Groq or Azure OpenAI for screening, interviews, and evaluation. Speech endpoints are stored here; keys are edited on API &amp; Integration and never shown in full.
          </p>
          <div>
            <label className={labelCls}>Chat provider</label>
            <select
              className={inputCls}
              value={llmForm.provider}
              onChange={(e) => {
                const provider = e.target.value;
                setLlmForm((f) => {
                  if (provider === 'azure') {
                    const deployment = resolveAzureDeployment(f.azure_openai_deployment);
                    return { ...f, provider, azure_openai_deployment: deployment, model_id: deployment };
                  }
                  return {
                    ...f,
                    provider,
                    model_id: GROQ_MODEL_REPLACEMENTS[f.model_id] || (AZURE_DEPLOYMENT_IDS.includes(f.model_id) ? 'openai/gpt-oss-120b' : f.model_id),
                  };
                });
              }}
            >
              <option value="groq">Groq</option>
              <option value="azure">Azure OpenAI (South India)</option>
            </select>
          </div>
          {llmForm.provider === 'groq' ? (
            <div>
              <label className={labelCls}>Groq model</label>
              <select className={inputCls} value={llmForm.model_id} onChange={(e) => setLlmForm((f) => ({ ...f, model_id: e.target.value }))}>
                <option value="openai/gpt-oss-120b">openai/gpt-oss-120b</option>
                <option value="openai/gpt-oss-20b">openai/gpt-oss-20b</option>
              </select>
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2">
                <label className={labelCls}>Azure OpenAI endpoint</label>
                <input
                  className={inputCls}
                  placeholder="https://interview-azure-openai.openai.azure.com"
                  value={llmForm.azure_openai_endpoint}
                  onChange={(e) => setLlmForm((f) => ({ ...f, azure_openai_endpoint: e.target.value }))}
                />
              </div>
              <div>
                <label className={labelCls}>Deployment name</label>
                <select
                  className={inputCls}
                  value={resolveAzureDeployment(llmForm.azure_openai_deployment)}
                  onChange={(e) => setLlmForm((f) => ({ ...f, azure_openai_deployment: e.target.value, model_id: e.target.value }))}
                >
                  {AZURE_DEPLOYMENTS.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls}>API version</label>
                <input
                  className={inputCls}
                  value={llmForm.azure_openai_api_version}
                  onChange={(e) => setLlmForm((f) => ({ ...f, azure_openai_api_version: e.target.value }))}
                />
              </div>
            </div>
          )}
          <div>
            <label className={labelCls}>Temperature ({Number(llmForm.temperature).toFixed(2)})</label>
            <input type="range" min="0" max="1" step="0.05" value={llmForm.temperature} onChange={(e) => setLlmForm((f) => ({ ...f, temperature: e.target.value }))} className="w-full accent-blue-500" />
          </div>
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
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Speech-to-text</label>
              <select className={inputCls} value={llmForm.stt_provider} onChange={(e) => setLlmForm((f) => ({ ...f, stt_provider: e.target.value }))}>
                <option value="groq">Groq Whisper</option>
                <option value="azure">Azure Speech (Foundry / East US 2)</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Text-to-speech</label>
              <select className={inputCls} value={llmForm.tts_provider} onChange={(e) => setLlmForm((f) => ({ ...f, tts_provider: e.target.value }))}>
                <option value="edge">Edge TTS (current default)</option>
                <option value="azure">Azure Speech TTS</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Azure Speech region</label>
              <input className={inputCls} value={llmForm.azure_speech_region} onChange={(e) => setLlmForm((f) => ({ ...f, azure_speech_region: e.target.value }))} />
            </div>
            <div>
              <label className={labelCls}>STT endpoint</label>
              <input
                className={inputCls}
                placeholder="https://eastus2.stt.speech.microsoft.com"
                value={llmForm.azure_speech_stt_endpoint}
                onChange={(e) => setLlmForm((f) => ({ ...f, azure_speech_stt_endpoint: e.target.value }))}
              />
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>TTS endpoint</label>
              <input
                className={inputCls}
                placeholder="https://eastus2.tts.speech.microsoft.com"
                value={llmForm.azure_speech_tts_endpoint}
                onChange={(e) => setLlmForm((f) => ({ ...f, azure_speech_tts_endpoint: e.target.value }))}
              />
            </div>
          </div>
          <p className="text-xs text-muted">
            Groq key {system?.integration?.groq_api_key_masked || system?.integration?.api_key_masked}. Azure OpenAI {system?.integration?.azure_openai_api_key_masked}. Speech {system?.integration?.azure_speech_key_masked}. Edit keys on API &amp; Integration.
          </p>
          <button type="submit" disabled={saving} className="btn-primary inline-flex items-center gap-2">
            <Save size={14} /> Save LLM settings
          </button>
        </form>
      )}

      {tab === 'integration' && (
        <div className="space-y-5 max-w-3xl">
          <form onSubmit={saveIntegration} className="card p-6 space-y-4">
            <p className="text-sm text-muted">
              Paste a new key to replace it. Leave a field blank to keep the current secret. Full keys are never returned to the browser.
            </p>
            <div>
              <label className={labelCls}>Public app URL (emails / join links)</label>
              <input className={inputCls} placeholder="https://app.yourcompany.com" value={integrationForm.frontend_url} onChange={(e) => setIntegrationForm((f) => ({ ...f, frontend_url: e.target.value }))} />
            </div>
            <div>
              <label className={labelCls}>Proctoring / interview public URL</label>
              <input className={inputCls} placeholder="https://proctor.yourcompany.com" value={integrationForm.agent5_public_url} onChange={(e) => setIntegrationForm((f) => ({ ...f, agent5_public_url: e.target.value }))} />
            </div>
            <PasswordInput
              id="sa-groq-key"
              label={`Groq API key (${system?.integration?.groq_api_key_masked || 'Not configured'})`}
              value={integrationForm.groq_api_key}
              onChange={(e) => setIntegrationForm((f) => ({ ...f, groq_api_key: e.target.value }))}
              placeholder="Leave blank to keep current key"
              autoComplete="new-password"
            />
            <PasswordInput
              id="sa-azure-openai-key"
              label={`Azure OpenAI key — South India (${system?.integration?.azure_openai_api_key_masked || 'Not configured'})`}
              value={integrationForm.azure_openai_api_key}
              onChange={(e) => setIntegrationForm((f) => ({ ...f, azure_openai_api_key: e.target.value }))}
              placeholder="Leave blank to keep current key"
              autoComplete="new-password"
            />
            <PasswordInput
              id="sa-azure-speech-key"
              label={`Azure Speech / Foundry key — East US 2 (${system?.integration?.azure_speech_key_masked || 'Not configured'})`}
              value={integrationForm.azure_speech_key}
              onChange={(e) => setIntegrationForm((f) => ({ ...f, azure_speech_key: e.target.value }))}
              placeholder="Leave blank to keep current key"
              autoComplete="new-password"
            />
            <div className={`p-3 rounded-xl border text-sm ${
              system?.integration?.api_key_configured
                ? 'bg-emerald-50 border-emerald-100 text-emerald-700'
                : 'bg-amber-50 border-amber-100 text-amber-700'
            }`}>
              {system?.integration?.message || 'Checking…'}
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="submit" disabled={saving} className="btn-primary inline-flex items-center gap-2">
                <Save size={14} /> Save keys and URLs
              </button>
              <button type="button" className="btn-secondary" onClick={testConnection} disabled={testingConnection}>
                {testingConnection ? 'Testing…' : 'Test connection'}
              </button>
            </div>
          </form>

          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Mail size={16} className="text-muted" />
              <h3 className="font-semibold text-col">SMTP per company</h3>
            </div>
            <p className="text-sm text-muted">
              Parkon and Kabel can use different mailboxes. Invite emails use the candidate&apos;s company SMTP.
            </p>
            {Object.values(smtpForms).length === 0 && (
              <p className="text-sm text-muted card p-4">No companies found. Create Parkon and Kabel first on the Companies tab.</p>
            )}
            {Object.values(smtpForms).map((form) => (
              <form key={form.company_id} onSubmit={(event) => saveSmtp(event, form.company_id)} className="card p-5 space-y-3">
                <p className="font-medium text-col">
                  {form.company_name} <span className="text-xs text-muted font-normal">({form.company_code})</span>
                  {form.using_env_fallback && (
                    <span className="ml-2 text-xs text-amber-700">Using .env fallback until saved</span>
                  )}
                </p>
                <div className="grid sm:grid-cols-2 gap-3">
                  <div>
                    <label className={labelCls}>SMTP host</label>
                    <input className={inputCls} placeholder="smtp.office365.com" value={form.host} onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, host: e.target.value } }))} />
                  </div>
                  <div>
                    <label className={labelCls}>Port</label>
                    <input type="number" className={inputCls} value={form.port} onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, port: e.target.value } }))} />
                  </div>
                  <div>
                    <label className={labelCls}>Username</label>
                    <input className={inputCls} value={form.username} onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, username: e.target.value } }))} />
                  </div>
                  <PasswordInput
                    id={`smtp-pass-${form.company_id}`}
                    label={`Password (${form.password_masked || 'Not configured'})`}
                    value={form.password}
                    onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, password: e.target.value } }))}
                    placeholder="Leave blank to keep current password"
                    autoComplete="new-password"
                  />
                  <div>
                    <label className={labelCls}>From email</label>
                    <input className={inputCls} value={form.from_email} onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, from_email: e.target.value } }))} />
                  </div>
                  <div>
                    <label className={labelCls}>From name</label>
                    <input className={inputCls} placeholder="RR Parkon HR Team" value={form.from_name} onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, from_name: e.target.value } }))} />
                  </div>
                </div>
                <div className="flex flex-wrap gap-4 text-sm text-col">
                  <label className="inline-flex items-center gap-2">
                    <input type="checkbox" checked={form.use_tls} onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, use_tls: e.target.checked } }))} />
                    TLS (port 587)
                  </label>
                  <label className="inline-flex items-center gap-2">
                    <input type="checkbox" checked={form.use_ssl} onChange={(e) => setSmtpForms((all) => ({ ...all, [form.company_id]: { ...form, use_ssl: e.target.checked } }))} />
                    SSL (port 465)
                  </label>
                </div>
                <button type="submit" disabled={saving} className="btn-primary inline-flex items-center gap-2">
                  <Save size={14} /> Save SMTP for {form.company_name}
                </button>
              </form>
            ))}
          </div>
        </div>
      )}

      {tab === 'screening' && (
        <form onSubmit={saveScreening} className="card p-6 max-w-2xl space-y-4">
          <p className="text-sm text-muted">ATS shortlist and review cutoffs used after resume scoring.</p>
          <div>
            <label className={labelCls}>Shortlist threshold</label>
            <input type="number" min="0" max="100" step="1" className={inputCls} value={screeningForm.shortlist_threshold} onChange={(e) => setScreeningForm((f) => ({ ...f, shortlist_threshold: e.target.value }))} />
          </div>
          <div>
            <label className={labelCls}>Review threshold</label>
            <input type="number" min="0" max="100" step="1" className={inputCls} value={screeningForm.review_threshold} onChange={(e) => setScreeningForm((f) => ({ ...f, review_threshold: e.target.value }))} />
          </div>
          <label className="flex items-center gap-2 text-sm text-col">
            <input
              type="checkbox"
              checked={screeningForm.use_llm_for_jd_parsing}
              onChange={(e) => setScreeningForm((f) => ({ ...f, use_llm_for_jd_parsing: e.target.checked }))}
              className="rounded border-col"
            />
            Use LLM for JD parsing
          </label>
          <label className="flex items-center gap-2 text-sm text-col">
            <input
              type="checkbox"
              checked={screeningForm.use_llm_for_resume_parsing}
              onChange={(e) => setScreeningForm((f) => ({ ...f, use_llm_for_resume_parsing: e.target.checked }))}
              className="rounded border-col"
            />
            Use LLM for resume parsing
          </label>
          <button type="submit" disabled={saving} className="btn-primary inline-flex items-center gap-2">
            <Save size={14} /> Save screening policy
          </button>
        </form>
      )}

      {tab === 'company' && (
        <form onSubmit={saveCompany} className="card p-6 max-w-2xl space-y-4">
          <div>
            <label className={labelCls}>Company name</label>
            <input className={inputCls} value={companyForm.company_name} onChange={(e) => setCompanyForm((f) => ({ ...f, company_name: e.target.value }))} required />
          </div>
          <div>
            <label className={labelCls}>Website</label>
            <input className={inputCls} value={companyForm.website} onChange={(e) => setCompanyForm((f) => ({ ...f, website: e.target.value }))} />
          </div>
          <div>
            <label className={labelCls}>Industry</label>
            <input className={inputCls} value={companyForm.industry} onChange={(e) => setCompanyForm((f) => ({ ...f, industry: e.target.value }))} />
          </div>
          <div>
            <label className={labelCls}>Company size</label>
            <input className={inputCls} value={companyForm.company_size} onChange={(e) => setCompanyForm((f) => ({ ...f, company_size: e.target.value }))} />
          </div>
          <div>
            <label className={labelCls}>Headquarters</label>
            <input className={inputCls} value={companyForm.headquarters} onChange={(e) => setCompanyForm((f) => ({ ...f, headquarters: e.target.value }))} />
          </div>
          <div>
            <label className={labelCls}>Timezone</label>
            <select className={inputCls} value={companyForm.timezone} onChange={(e) => setCompanyForm((f) => ({ ...f, timezone: e.target.value }))}>
              <option value="Asia/Kolkata">Asia/Kolkata</option>
              <option value="Asia/Dubai">Asia/Dubai</option>
              <option value="Europe/London">Europe/London</option>
            </select>
          </div>
          <button type="submit" disabled={saving} className="btn-primary inline-flex items-center gap-2">
            <Save size={14} /> Save company settings
          </button>
        </form>
      )}

      {tab === 'data' && <DataManagement />}

      {tab === 'database' && (
        <div className="space-y-4">
          {system && (
            <div className="card p-5 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Engine" value={system.database.engine} />
              <StatCard label="Status" value={system.database.connected ? 'Connected' : 'Disconnected'} />
              <StatCard label="Environment" value={system.database.environment} />
              <StatCard label="Health" value={system.database.health} hint={system.database.message} />
            </div>
          )}
          <p className="text-sm text-muted">
            Connection credentials stay on the server. This console is allowlisted and read-only. Use Data Management to change business records.
          </p>
          <DatabaseBrowser />
        </div>
      )}

      {tab === 'audit' && (
        <div className="space-y-4">
          <div className="card p-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-col">Audit history is read-only</p>
              <p className="text-sm text-muted mt-1">
                Historical snapshots are never rewritten when a user or department later changes. Full detail, IP, and before/after values are on the Audit Log page.
              </p>
            </div>
            <Link to="/audit" className="btn-primary">Open full Audit Log</Link>
          </div>
          <div className="card p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-col flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-medium text-col">Recent audit events</p>
              <CompanyTableFilter value={companyFilter} onChange={setCompanyFilter} companies={companies} />
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">When</th>
                  <th className="text-left px-4 py-3">Actor</th>
                  <th className="text-left px-4 py-3">Company</th>
                  <th className="text-left px-4 py-3">Action</th>
                  <th className="text-left px-4 py-3">Entity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-col">
                {auditEntries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="px-4 py-3 text-xs text-muted">{entry.created_at ? new Date(entry.created_at).toLocaleString() : '—'}</td>
                    <td className="px-4 py-3">{entry.user_email || entry.user_name || '—'}</td>
                    <td className="px-4 py-3">{entry.company_name || '—'}</td>
                    <td className="px-4 py-3">{entry.action}</td>
                    <td className="px-4 py-3">{entry.entity_type}{entry.entity_id ? ` #${entry.entity_id}` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!auditEntries.length && <p className="px-4 py-6 text-sm text-muted">No audit events loaded.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
