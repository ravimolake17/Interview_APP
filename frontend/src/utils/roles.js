export function isSuperAdmin(role) {
  return role === 'SUPERADMIN';
}

export function isCompanyAdmin(role) {
  return role === 'COMPANY_ADMIN' || role === 'ADMIN';
}

export function isStaffAdmin(role) {
  return isSuperAdmin(role) || isCompanyAdmin(role);
}

export function roleLabel(role) {
  if (role === 'COMPANY_ADMIN' || role === 'ADMIN') return 'Company Admin';
  if (role === 'SUPERADMIN') return 'Super Admin';
  if (role === 'HR') return 'HR';
  return role || '';
}

export const SUPERADMIN_COMPANY_KEY = 'hr_superadmin_company_id';

export function getSuperAdminCompanyId() {
  try {
    const raw = localStorage.getItem(SUPERADMIN_COMPANY_KEY);
    return raw ? Number(raw) : null;
  } catch {
    return null;
  }
}

export function setSuperAdminCompanyId(companyId) {
  try {
    if (companyId) localStorage.setItem(SUPERADMIN_COMPANY_KEY, String(companyId));
    else localStorage.removeItem(SUPERADMIN_COMPANY_KEY);
  } catch {
    /* ignore */
  }
}
