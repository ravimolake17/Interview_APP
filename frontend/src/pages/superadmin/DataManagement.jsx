import { useCallback, useEffect, useState } from 'react';
import { Plus, Save } from 'lucide-react';
import {
  createDataDepartment,
  createDataJob,
  createDataUser,
  deactivateDataDepartment,
  deleteDataJob,
  getDataCatalog,
  getDataImpact,
  getDataRecords,
  getDepartments,
  updateDataCandidate,
  updateDataCompany,
  updateDataDepartment,
  updateDataJob,
  updateDataUser,
} from '../../services/api';
import PasswordInput from '../../components/PasswordInput';
import { isValidEmail, isValidPassword } from '../../utils/validation';

const PAGE_SIZE = 25;
const CANDIDATE_STATUSES = ['PENDING', 'SHORTLISTED', 'NEEDS_REVIEW', 'REJECTED', 'INTERVIEW_SCHEDULED', 'INTERVIEW_COMPLETED'];
const inputCls = 'input-field';

function errorMessage(err, fallback) {
  const detail = err.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

export default function DataManagement() {
  const [catalog, setCatalog] = useState([]);
  const [entity, setEntity] = useState('users');
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(null);
  const [reason, setReason] = useState('');
  const [departments, setDepartments] = useState([]);
  const [userForm, setUserForm] = useState({ email: '', full_name: '', password: '', role: 'HR', is_active: true });
  const [candidateForm, setCandidateForm] = useState(null);
  const [jobForm, setJobForm] = useState({ title: '', department: '', experience: '', location: '', description: '', status: 'Active' });
  const [deptForm, setDeptForm] = useState({ name: '', description: '', is_active: true });
  const [companyForm, setCompanyForm] = useState(null);

  const loadCatalog = async () => {
    const { data } = await getDataCatalog();
    setCatalog(data || []);
  };

  const loadRecords = useCallback(async (nextEntity, nextOffset, nextSearch, nextStatus) => {
    const params = { limit: PAGE_SIZE, offset: nextOffset, search: nextSearch };
    if (nextEntity === 'candidates' && nextStatus) params.status = nextStatus;
    const { data } = await getDataRecords(nextEntity, params);
    setRecords(data.records || []);
    setTotal(data.total || 0);
    if (nextEntity === 'company' && data.records?.[0]) setCompanyForm(data.records[0]);
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([loadCatalog(), getDepartments()])
      .then(([, deptRes]) => {
        if (!active) return;
        setDepartments(deptRes.data.departments || []);
      })
      .catch((err) => setError(errorMessage(err, 'Could not load Data Management.')))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setLoading(true);
    loadRecords(entity, offset, search, status)
      .catch((err) => setError(errorMessage(err, 'Could not load records.')))
      .finally(() => setLoading(false));
  }, [entity, offset, status, loadRecords]);

  const selectEntity = (id) => {
    setEntity(id);
    setOffset(0);
    setSearch('');
    setStatus('');
    setEditing(null);
    setError(null);
    setMessage(null);
  };

  const refresh = async () => {
    await loadCatalog();
    await loadRecords(entity, offset, search, status);
  };

  const submitUser = async (event) => {
    event.preventDefault();
    const emailErr = isValidEmail(userForm.email);
    if (emailErr) return setError(emailErr);
    if (!editing) {
      const passErr = isValidPassword(userForm.password);
      if (passErr) return setError(passErr);
    }
    setSaving(true);
    setError(null);
    try {
      const payload = { ...userForm, reason };
      if (editing) {
        if (!payload.password) delete payload.password;
        await updateDataUser(editing.id, payload);
        setMessage('User updated.');
      } else {
        await createDataUser(payload);
        setMessage('User created.');
      }
      setEditing(null);
      setUserForm({ email: '', full_name: '', password: '', role: 'HR', is_active: true });
      setReason('');
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not save user.'));
    } finally {
      setSaving(false);
    }
  };

  const submitCandidate = async (event) => {
    event.preventDefault();
    if (!candidateForm?.candidate_id) return;
    setSaving(true);
    try {
      await updateDataCandidate(candidateForm.candidate_id, { ...candidateForm, reason });
      setMessage('Candidate updated. Historical audit snapshots were not rewritten.');
      setCandidateForm(null);
      setReason('');
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not update candidate.'));
    } finally {
      setSaving(false);
    }
  };

  const submitJob = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = { ...jobForm, reason };
      if (editing) {
        payload.expected_updated_at = editing.updated_at;
        await updateDataJob(editing.id, payload);
        setMessage('Job updated.');
      } else {
        await createDataJob(payload);
        setMessage('Job created.');
      }
      setEditing(null);
      setJobForm({ title: '', department: '', experience: '', location: '', description: '', status: 'Active' });
      setReason('');
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not save job.'));
    } finally {
      setSaving(false);
    }
  };

  const submitDepartment = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = { ...deptForm, reason };
      if (editing) {
        payload.expected_updated_at = editing.updated_at;
        await updateDataDepartment(editing.id, payload);
        setMessage('Department updated. Related jobs keep their stored department name until those jobs are edited.');
      } else {
        await createDataDepartment(payload);
        setMessage('Department created.');
      }
      setEditing(null);
      setDeptForm({ name: '', description: '', is_active: true });
      setReason('');
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not save department.'));
    } finally {
      setSaving(false);
    }
  };

  const submitCompany = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await updateDataCompany({ ...companyForm, reason });
      setMessage('Company settings saved.');
      setReason('');
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not save company.'));
    } finally {
      setSaving(false);
    }
  };

  const removeJob = async (job) => {
    try {
      const { data } = await getDataImpact('jobs', job.id);
      const related = data.related?.candidates || 0;
      const ok = window.confirm(
        related
          ? `This job has ${related} linked candidates. It will be closed instead of deleted. Continue?`
          : `Delete job "${job.title}"? This cannot be undone.`
      );
      if (!ok) return;
      const result = await deleteDataJob(job.id);
      setMessage(result.data?.message || `Job ${result.data?.action || 'updated'}.`);
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not change this job.'));
    }
  };

  const deactivateDept = async (department) => {
    try {
      const { data } = await getDataImpact('departments', department.id);
      const jobs = data.related?.jobs || 0;
      const ok = window.confirm(
        jobs
          ? `Cannot hard-delete this department: ${jobs} jobs still list it. Deactivate instead? Jobs keep the stored name.`
          : `Deactivate department "${department.name}"?`
      );
      if (!ok) return;
      const result = await deactivateDataDepartment(department.id);
      setMessage(result.data?.message || 'Department deactivated.');
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not deactivate department.'));
    }
  };

  const deactivateUser = async (user) => {
    if (!window.confirm(`Deactivate ${user.email}? The account can be reactivated later.`)) return;
    try {
      await updateDataUser(user.id, { is_active: false, reason: reason || 'Deactivated from Data Management' });
      setMessage('User deactivated.');
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Could not deactivate user.'));
    }
  };

  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="grid lg:grid-cols-4 gap-4">
      <div className="card p-4 space-y-1">
        <p className="text-xs uppercase tracking-wider text-muted font-semibold mb-2">Business entities</p>
        {catalog.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => selectEntity(item.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm ${entity === item.id ? 'nav-active' : 'text-col hover:bg-slate-100 dark:hover:bg-slate-800'}`}
          >
            <span className="font-medium">{item.label}</span>
            <span className="text-xs text-muted ml-2">{item.rows}</span>
          </button>
        ))}
      </div>

      <div className="lg:col-span-3 space-y-4">
        {error && <div className="card bg-red-50 dark:bg-red-900/20 border border-red-200 text-red-700 text-sm px-4 py-3">{error}</div>}
        {message && <div className="card bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 text-emerald-700 text-sm px-4 py-3">{message}</div>}

        {entity !== 'company' && (
          <form
            className="card p-4 flex flex-wrap gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              setOffset(0);
              loadRecords(entity, 0, search, status).catch((err) => setError(errorMessage(err, 'Search failed.')));
            }}
          >
            <input className={`${inputCls} max-w-xs`} placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
            {entity === 'candidates' && (
              <select className={`${inputCls} max-w-[180px]`} value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
                <option value="">All statuses</option>
                {CANDIDATE_STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            )}
            <button type="submit" className="btn-secondary">Search</button>
          </form>
        )}

        {entity === 'users' && (
          <form onSubmit={submitUser} className="card p-5 grid sm:grid-cols-2 gap-3">
            <h3 className="sm:col-span-2 font-semibold text-col">{editing ? 'Edit user' : 'Add user'}</h3>
            <input className={inputCls} placeholder="Full name" value={userForm.full_name} onChange={(e) => setUserForm((f) => ({ ...f, full_name: e.target.value }))} required />
            <input className={inputCls} placeholder="Email" value={userForm.email} onChange={(e) => setUserForm((f) => ({ ...f, email: e.target.value }))} required />
            <PasswordInput id="dm-user-password" label={editing ? 'New password (optional)' : 'Password'} value={userForm.password} onChange={(e) => setUserForm((f) => ({ ...f, password: e.target.value }))} required={!editing} />
            <select className={inputCls} value={userForm.role} onChange={(e) => setUserForm((f) => ({ ...f, role: e.target.value }))}>
              <option value="HR">HR</option>
              <option value="ADMIN">Admin</option>
              <option value="SUPERADMIN">SuperAdmin</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-col">
              <input type="checkbox" checked={userForm.is_active} onChange={(e) => setUserForm((f) => ({ ...f, is_active: e.target.checked }))} />
              Active
            </label>
            <input className={`${inputCls} sm:col-span-2`} placeholder="Reason (optional, recorded in audit log)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button type="submit" disabled={saving} className="btn-primary inline-flex items-center justify-center gap-2">
              <Save size={14} /> {saving ? 'Saving…' : editing ? 'Update user' : 'Create user'}
            </button>
          </form>
        )}

        {entity === 'jobs' && (
          <form onSubmit={submitJob} className="card p-5 grid sm:grid-cols-2 gap-3">
            <h3 className="sm:col-span-2 font-semibold text-col">{editing ? 'Edit job' : 'Add job'}</h3>
            <input className={inputCls} placeholder="Title" value={jobForm.title} onChange={(e) => setJobForm((f) => ({ ...f, title: e.target.value }))} required />
            <select className={inputCls} value={jobForm.department} onChange={(e) => setJobForm((f) => ({ ...f, department: e.target.value }))}>
              <option value="">Department</option>
              {departments.filter((row) => row.is_active).map((row) => (
                <option key={row.id} value={row.name}>{row.name}</option>
              ))}
            </select>
            <input className={inputCls} placeholder="Experience" value={jobForm.experience} onChange={(e) => setJobForm((f) => ({ ...f, experience: e.target.value }))} />
            <input className={inputCls} placeholder="Location" value={jobForm.location} onChange={(e) => setJobForm((f) => ({ ...f, location: e.target.value }))} />
            <select className={inputCls} value={jobForm.status} onChange={(e) => setJobForm((f) => ({ ...f, status: e.target.value }))}>
              <option value="Active">Active</option>
              <option value="Draft">Draft</option>
              <option value="Closed">Closed</option>
            </select>
            <textarea className={`${inputCls} sm:col-span-2 min-h-[70px]`} placeholder="Description" value={jobForm.description} onChange={(e) => setJobForm((f) => ({ ...f, description: e.target.value }))} />
            <input className={`${inputCls} sm:col-span-2`} placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button type="submit" disabled={saving} className="btn-primary inline-flex items-center justify-center gap-2">
              <Plus size={14} /> {saving ? 'Saving…' : editing ? 'Update job' : 'Create job'}
            </button>
          </form>
        )}

        {entity === 'departments' && (
          <form onSubmit={submitDepartment} className="card p-5 grid sm:grid-cols-2 gap-3">
            <h3 className="sm:col-span-2 font-semibold text-col">{editing ? 'Edit department' : 'Add department'}</h3>
            <input className={inputCls} placeholder="Name" value={deptForm.name} onChange={(e) => setDeptForm((f) => ({ ...f, name: e.target.value }))} required />
            <input className={inputCls} placeholder="Description" value={deptForm.description} onChange={(e) => setDeptForm((f) => ({ ...f, description: e.target.value }))} />
            <input className={`${inputCls} sm:col-span-2`} placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button type="submit" disabled={saving} className="btn-primary">{saving ? 'Saving…' : editing ? 'Update department' : 'Create department'}</button>
          </form>
        )}

        {entity === 'candidates' && candidateForm && (
          <form onSubmit={submitCandidate} className="card p-5 grid sm:grid-cols-2 gap-3">
            <h3 className="sm:col-span-2 font-semibold text-col">Edit candidate {candidateForm.candidate_id}</h3>
            <input className={inputCls} value={candidateForm.full_name} onChange={(e) => setCandidateForm((f) => ({ ...f, full_name: e.target.value }))} />
            <input className={inputCls} value={candidateForm.email} onChange={(e) => setCandidateForm((f) => ({ ...f, email: e.target.value }))} />
            <input className={inputCls} placeholder="Phone" value={candidateForm.phone || ''} onChange={(e) => setCandidateForm((f) => ({ ...f, phone: e.target.value }))} />
            <input className={inputCls} placeholder="Job position" value={candidateForm.job_position || ''} onChange={(e) => setCandidateForm((f) => ({ ...f, job_position: e.target.value }))} />
            <select className={inputCls} value={candidateForm.status} onChange={(e) => setCandidateForm((f) => ({ ...f, status: e.target.value }))}>
              {CANDIDATE_STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <input className={`${inputCls} sm:col-span-2`} placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button type="submit" disabled={saving} className="btn-primary">Save candidate</button>
          </form>
        )}

        {entity === 'company' && companyForm && (
          <form onSubmit={submitCompany} className="card p-5 grid sm:grid-cols-2 gap-3">
            <p className="sm:col-span-2 text-sm text-muted">Company profile is stored in application settings, not as a raw table. Credentials stay on the server.</p>
            <input className={inputCls} value={companyForm.company_name} onChange={(e) => setCompanyForm((f) => ({ ...f, company_name: e.target.value }))} />
            <input className={inputCls} value={companyForm.website} onChange={(e) => setCompanyForm((f) => ({ ...f, website: e.target.value }))} />
            <input className={inputCls} value={companyForm.industry} onChange={(e) => setCompanyForm((f) => ({ ...f, industry: e.target.value }))} />
            <input className={inputCls} value={companyForm.company_size} onChange={(e) => setCompanyForm((f) => ({ ...f, company_size: e.target.value }))} />
            <input className={inputCls} value={companyForm.headquarters} onChange={(e) => setCompanyForm((f) => ({ ...f, headquarters: e.target.value }))} />
            <select className={inputCls} value={companyForm.timezone} onChange={(e) => setCompanyForm((f) => ({ ...f, timezone: e.target.value }))}>
              <option value="Asia/Kolkata">Asia/Kolkata</option>
              <option value="Asia/Dubai">Asia/Dubai</option>
              <option value="Europe/London">Europe/London</option>
            </select>
            <input className={`${inputCls} sm:col-span-2`} placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <button type="submit" disabled={saving} className="btn-primary">Save company</button>
          </form>
        )}

        {entity !== 'company' && (
          <div className="card p-0 overflow-auto">
            {loading ? (
              <p className="p-4 text-sm text-muted">Loading records…</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-muted text-xs uppercase">
                  <tr>
                    {entity === 'users' && (
                      <>
                        <th className="text-left px-4 py-3">User</th>
                        <th className="text-left px-4 py-3">Role</th>
                        <th className="text-left px-4 py-3">Status</th>
                        <th className="px-4 py-3" />
                      </>
                    )}
                    {entity === 'candidates' && (
                      <>
                        <th className="text-left px-4 py-3">Candidate</th>
                        <th className="text-left px-4 py-3">Job</th>
                        <th className="text-left px-4 py-3">Status</th>
                        <th className="px-4 py-3" />
                      </>
                    )}
                    {entity === 'jobs' && (
                      <>
                        <th className="text-left px-4 py-3">Job</th>
                        <th className="text-left px-4 py-3">Department</th>
                        <th className="text-left px-4 py-3">Status</th>
                        <th className="px-4 py-3" />
                      </>
                    )}
                    {entity === 'departments' && (
                      <>
                        <th className="text-left px-4 py-3">Department</th>
                        <th className="text-left px-4 py-3">Jobs</th>
                        <th className="text-left px-4 py-3">Status</th>
                        <th className="px-4 py-3" />
                      </>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-col">
                  {records.map((row) => (
                    <tr key={row.id || row.candidate_id}>
                      {entity === 'users' && (
                        <>
                          <td className="px-4 py-3"><p className="font-medium text-col">{row.full_name}</p><p className="text-xs text-muted">{row.email}</p></td>
                          <td className="px-4 py-3">{row.role}</td>
                          <td className="px-4 py-3">{row.is_active ? 'Active' : 'Inactive'}</td>
                          <td className="px-4 py-3 text-right space-x-3">
                            <button type="button" className="text-blue-600 text-xs font-medium" onClick={() => { setEditing(row); setUserForm({ email: row.email, full_name: row.full_name, password: '', role: row.role, is_active: row.is_active }); }}>Edit</button>
                            {row.is_active && <button type="button" className="text-red-600 text-xs font-medium" onClick={() => deactivateUser(row)}>Deactivate</button>}
                          </td>
                        </>
                      )}
                      {entity === 'candidates' && (
                        <>
                          <td className="px-4 py-3"><p className="font-medium text-col">{row.full_name}</p><p className="text-xs text-muted">{row.candidate_id} · {row.email}</p></td>
                          <td className="px-4 py-3">{row.job_position || '—'}</td>
                          <td className="px-4 py-3">{row.status}</td>
                          <td className="px-4 py-3 text-right">
                            <button type="button" className="text-blue-600 text-xs font-medium" onClick={() => setCandidateForm(row)}>Edit</button>
                          </td>
                        </>
                      )}
                      {entity === 'jobs' && (
                        <>
                          <td className="px-4 py-3"><p className="font-medium text-col">{row.title}</p><p className="text-xs text-muted">{row.applicants || 0} candidates</p></td>
                          <td className="px-4 py-3">{row.department || '—'}</td>
                          <td className="px-4 py-3">{row.status}</td>
                          <td className="px-4 py-3 text-right space-x-3">
                            <button type="button" className="text-blue-600 text-xs font-medium" onClick={() => { setEditing(row); setJobForm({ title: row.title, department: row.department || '', experience: row.experience || '', location: row.location || '', description: row.description || '', status: row.status }); }}>Edit</button>
                            <button type="button" className="text-red-600 text-xs font-medium" onClick={() => removeJob(row)}>{row.applicants ? 'Close' : 'Delete'}</button>
                          </td>
                        </>
                      )}
                      {entity === 'departments' && (
                        <>
                          <td className="px-4 py-3"><p className="font-medium text-col">{row.name}</p><p className="text-xs text-muted">{row.description || '—'}</p></td>
                          <td className="px-4 py-3">{row.job_count ?? 0}</td>
                          <td className="px-4 py-3">{row.is_active ? 'Active' : 'Inactive'}</td>
                          <td className="px-4 py-3 text-right space-x-3">
                            <button type="button" className="text-blue-600 text-xs font-medium" onClick={() => { setEditing(row); setDeptForm({ name: row.name, description: row.description || '', is_active: row.is_active }); }}>Edit</button>
                            {row.is_active && <button type="button" className="text-red-600 text-xs font-medium" onClick={() => deactivateDept(row)}>Deactivate</button>}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {!loading && !records.length && <p className="px-4 py-6 text-sm text-muted">No records found.</p>}
          </div>
        )}

        {entity !== 'company' && (
          <div className="flex items-center justify-between text-xs text-muted">
            <span>{total ? `${offset + 1}–${pageEnd} of ${total}` : '0 records'}</span>
            <div className="flex gap-2">
              <button type="button" className="btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
              <button type="button" className="btn-secondary" disabled={pageEnd >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
