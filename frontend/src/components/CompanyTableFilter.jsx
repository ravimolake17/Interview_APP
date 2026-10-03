import { Building2 } from 'lucide-react';

export default function CompanyTableFilter({
  value,
  onChange,
  companies = [],
  className = '',
}) {
  return (
    <div className={`relative min-w-[220px] ${className}`}>
      <Building2 size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label="Filter by company"
        className="appearance-none w-full pl-9 pr-9 py-2 text-sm rounded-xl border border-col bg-transparent text-col focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all cursor-pointer"
      >
        <option value="all">All companies</option>
        {companies.map((company) => (
          <option key={company.id} value={String(company.id)}>
            {company.name}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted text-xs">▾</span>
    </div>
  );
}

export function companyLabel(row) {
  return row?.company?.name || row?.company_name || (row?.role === 'SUPERADMIN' ? 'All companies' : '—');
}

export function matchesCompanyFilter(row, companyFilter) {
  if (!companyFilter || companyFilter === 'all') return true;
  const selected = Number(companyFilter);
  if (!selected) return true;
  const rowId = row?.company_id ?? row?.company?.id ?? null;
  return Number(rowId) === selected;
}
