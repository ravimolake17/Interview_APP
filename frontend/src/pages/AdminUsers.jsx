import { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, Shield, UserCog } from 'lucide-react';
import { createUser, getUsers, updateUser } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import PasswordInput from '../components/PasswordInput';
import CompanyTableFilter, { companyLabel, matchesCompanyFilter } from '../components/CompanyTableFilter';
import { isValidEmail, isValidPassword } from '../utils/validation';
import { useAuth } from '../context/AuthContext';
import { useApp } from '../context/AppContext';
import { isSuperAdmin } from '../utils/roles';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

const EMPTY_FORM = {
  email: '',
  full_name: '',
  password: '',
  role: 'HR',
  company_id: '',
  is_active: true,
};

const inputCls = 'input-field';
const labelCls = 'text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5';

function RoleBadge({ role }) {
  const styles =
    role === 'SUPERADMIN'
      ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
      : role === 'COMPANY_ADMIN' || role === 'ADMIN'
      ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300'
      : 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300';
  return <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${styles}`}>{role}</span>;
}

function StatusBadge({ active }) {
  return (
    <span
      className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${
        active
          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
          : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
      }`}
    >
      {active ? 'Active' : 'Inactive'}
    </span>
  );
}

export default function AdminUsers() {
  const { user: currentUser } = useAuth();
  const { companies, workingCompanyId } = useApp();
  const [users, setUsers] = useState([]);
  const [companyFilter, setCompanyFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const loadUsers = useCallback(async (options = {}) => {
    const silent = Boolean(options.silent);
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const { data } = await getUsers();
      setUsers(data.users || []);
    } catch (err) {
      if (!silent) {
        setError(err.response?.data?.detail || 'Failed to load users.');
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useAutoRefresh(() => loadUsers({ silent: true }));

  useEffect(() => {
    if (!isSuperAdmin(currentUser?.role) || !workingCompanyId) return;
    setCompanyFilter(String(workingCompanyId));
  }, [currentUser?.role, workingCompanyId]);

  const visibleUsers = useMemo(
    () => (isSuperAdmin(currentUser?.role) ? users.filter((user) => matchesCompanyFilter(user, companyFilter)) : users),
    [users, companyFilter, currentUser?.role],
  );

  const validateForm = (isCreate) => {
    const errors = {};
    const emailErr = isValidEmail(form.email);
    if (emailErr) errors.email = emailErr;
    if (!form.full_name.trim()) errors.full_name = 'Full name is required.';
    if (isCreate || form.password) {
      const passErr = isValidPassword(form.password);
      if (passErr) errors.password = passErr;
    }
    if (isSuperAdmin(currentUser?.role) && form.role !== 'SUPERADMIN' && !form.company_id) {
      errors.company_id = 'Select a company.';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const resetForm = () => {
    setForm({
      ...EMPTY_FORM,
      company_id: workingCompanyId ? String(workingCompanyId) : '',
    });
    setFormErrors({});
    setEditingId(null);
    setShowCreate(false);
  };

  const startEdit = (user) => {
    setShowCreate(false);
    setEditingId(user.id);
    setForm({
      email: user.email,
      full_name: user.full_name,
      password: '',
      role: user.role,
      company_id: user.company_id ? String(user.company_id) : '',
      is_active: user.is_active,
    });
    setFormErrors({});
    setMessage(null);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!validateForm(true)) return;
    setSaving(true);
    setMessage(null);
    try {
      await createUser({
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
        role: form.role,
        company_id: form.role === 'SUPERADMIN' ? null : Number(form.company_id) || null,
      });
      setMessage({ type: 'success', text: 'User created successfully.' });
      resetForm();
      await loadUsers();
    } catch (err) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to create user.',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!validateForm(false)) return;
    setSaving(true);
    setMessage(null);
    const payload = {
      email: form.email.trim(),
      full_name: form.full_name.trim(),
      role: form.role,
      is_active: form.is_active,
    };
    if (form.password) payload.password = form.password;
    if (isSuperAdmin(currentUser?.role)) {
      payload.company_id = form.role === 'SUPERADMIN' ? null : Number(form.company_id) || null;
    }

    try {
      await updateUser(editingId, payload);
      setMessage({ type: 'success', text: 'User updated successfully.' });
      resetForm();
      await loadUsers();
    } catch (err) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to update user.',
      });
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (user) => {
    if (user.id === currentUser?.id && user.is_active) {
      setMessage({ type: 'error', text: 'You cannot deactivate your own account.' });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      await updateUser(user.id, { is_active: !user.is_active });
      setMessage({
        type: 'success',
        text: `User ${user.is_active ? 'deactivated' : 'activated'}.`,
      });
      await loadUsers();
    } catch (err) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to update user status.',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-col">User Management</h2>
          <p className="text-sm text-muted mt-1">
            Admin only — create and manage HR and admin accounts.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {isSuperAdmin(currentUser?.role) && (
            <CompanyTableFilter
              value={companyFilter}
              onChange={setCompanyFilter}
              companies={companies}
            />
          )}
          <button
            type="button"
            onClick={() => {
              setForm({
                ...EMPTY_FORM,
                company_id: workingCompanyId ? String(workingCompanyId) : '',
              });
              setFormErrors({});
              setEditingId(null);
              setShowCreate(true);
            }}
            className="btn-primary shrink-0 gap-2"
          >
            <Plus size={16} />
            Add User
          </button>
        </div>
      </div>

      {error && (
        <div className="card border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm px-4 py-3">
          {error}
        </div>
      )}

      {message && (
        <div
          className={`text-sm rounded-xl px-4 py-3 border ${
            message.type === 'success'
              ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800'
              : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800'
          }`}
        >
          {message.text}
        </div>
      )}

      {(showCreate || editingId) && (
        <div className="card p-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-9 h-9 rounded-xl bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
              <UserCog size={18} className="text-orange-600 dark:text-orange-400" />
            </div>
            <h3 className="font-semibold text-col">{editingId ? 'Edit User' : 'New User'}</h3>
          </div>

          <form onSubmit={editingId ? handleUpdate : handleCreate} className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="user-email" className={labelCls}>
                Email
              </label>
              <input
                id="user-email"
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                className={`${inputCls} ${formErrors.email ? 'border-red-400' : ''}`}
              />
              {formErrors.email && <p className="mt-1 text-xs text-red-500">{formErrors.email}</p>}
            </div>

            <div>
              <label htmlFor="user-name" className={labelCls}>
                Full name
              </label>
              <input
                id="user-name"
                type="text"
                value={form.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                className={`${inputCls} ${formErrors.full_name ? 'border-red-400' : ''}`}
              />
              {formErrors.full_name && (
                <p className="mt-1 text-xs text-red-500">{formErrors.full_name}</p>
              )}
            </div>

            <PasswordInput
              id="user-password"
              label={editingId ? 'New password (leave blank to keep)' : 'Password'}
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              error={formErrors.password}
              autoComplete="new-password"
              required={!editingId}
            />

            <div>
              <label htmlFor="user-role" className={labelCls}>
                Role
              </label>
              <select
                id="user-role"
                value={form.role}
                onChange={(e) => setForm((f) => ({
                  ...f,
                  role: e.target.value,
                  company_id: e.target.value === 'SUPERADMIN' ? '' : (f.company_id || (workingCompanyId ? String(workingCompanyId) : '')),
                }))}
                disabled={editingId === currentUser?.id}
                className={`${inputCls} disabled:opacity-60`}
              >
                <option value="HR">HR</option>
                {isSuperAdmin(currentUser?.role) && <option value="COMPANY_ADMIN">Company Admin</option>}
                {isSuperAdmin(currentUser?.role) && <option value="SUPERADMIN">Super Admin</option>}
              </select>
            </div>

            {isSuperAdmin(currentUser?.role) && form.role !== 'SUPERADMIN' && (
              <div>
                <label htmlFor="user-company" className={labelCls}>
                  Company
                </label>
                <select
                  id="user-company"
                  value={form.company_id}
                  onChange={(e) => setForm((f) => ({ ...f, company_id: e.target.value }))}
                  className={`${inputCls} ${formErrors.company_id ? 'border-red-400' : ''}`}
                  required
                >
                  <option value="">Select company</option>
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>{company.name}</option>
                  ))}
                </select>
                {formErrors.company_id && (
                  <p className="mt-1 text-xs text-red-500">{formErrors.company_id}</p>
                )}
              </div>
            )}

            {editingId && (
              <div className="flex items-center gap-2 sm:col-span-2">
                <input
                  id="user-active"
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                  disabled={editingId === currentUser?.id}
                  className="rounded border-col text-primary-accent focus:ring-primary-accent"
                />
                <label htmlFor="user-active" className="text-sm text-col">
                  Active account
                </label>
              </div>
            )}

            <div className="sm:col-span-2 flex flex-wrap gap-3 pt-2">
              <button type="submit" disabled={saving} className="btn-primary min-w-[140px]">
                {saving ? 'Saving…' : editingId ? 'Save Changes' : 'Create User'}
              </button>
              <button type="button" onClick={resetForm} className="btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card overflow-hidden">
        {loading ? (
          <LoadingSpinner message="Loading users..." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-col bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="text-left px-5 py-3.5 font-semibold text-muted">Name</th>
                  <th className="text-left px-5 py-3.5 font-semibold text-muted">Email</th>
                  <th className="text-left px-5 py-3.5 font-semibold text-muted">Company</th>
                  <th className="text-left px-5 py-3.5 font-semibold text-muted">Role</th>
                  <th className="text-left px-5 py-3.5 font-semibold text-muted">Status</th>
                  <th className="text-left px-5 py-3.5 font-semibold text-muted">Last login</th>
                  <th className="text-right px-5 py-3.5 font-semibold text-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-col">
                {visibleUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-primary-accent/10 text-primary-accent flex items-center justify-center text-xs font-bold shrink-0">
                          {user.full_name?.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}
                        </div>
                        <span className="font-medium text-col">{user.full_name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-muted">{user.email}</td>
                    <td className="px-5 py-3.5 text-col">{companyLabel(user)}</td>
                    <td className="px-5 py-3.5">
                      <RoleBadge role={user.role} />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge active={user.is_active} />
                    </td>
                    <td className="px-5 py-3.5 text-muted whitespace-nowrap">
                      {user.last_login_at
                        ? new Date(user.last_login_at).toLocaleString()
                        : 'Never'}
                    </td>
                    <td className="px-5 py-3.5 text-right space-x-3 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => startEdit(user)}
                        className="text-primary-accent hover:opacity-80 font-medium"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleActive(user)}
                        disabled={saving || user.id === currentUser?.id}
                        className="text-muted hover:text-col font-medium disabled:opacity-40"
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
                {!visibleUsers.length && (
                  <tr>
                    <td colSpan={7} className="px-5 py-12 text-center text-muted">
                      <Shield size={28} className="mx-auto mb-2 opacity-40" />
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
