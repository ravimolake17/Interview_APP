import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Building2, Check, ChevronDown } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { isSuperAdmin } from '../../utils/roles';
import { companyLogoSrc } from '../../utils/companyBranding';

export default function CompanySwitcher({ onOpen }) {
  const { user } = useAuth();
  const { companies, workingCompany, switchWorkingCompany, addToast } = useApp();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!isSuperAdmin(user?.role)) return null;

  const selectable = companies.filter((company) => company.status === 'active');
  const logo = companyLogoSrc(workingCompany);

  const handleSelect = (company) => {
    if (company.id === workingCompany?.id) {
      setOpen(false);
      return;
    }
    switchWorkingCompany(company.id);
    setOpen(false);
    addToast(`Switched to ${company.name}.`, 'success');
  };

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => {
          onOpen?.();
          setOpen((current) => !current);
        }}
        className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-xl border border-col hover:bg-slate-100 dark:hover:bg-slate-800 transition-all max-w-[220px]"
        aria-label="Switch company"
        aria-expanded={open}
      >
        {logo ? (
          <img src={logo} alt="" className="h-7 w-auto max-w-[44px] rounded-lg object-contain logo-on-white" />
        ) : (
          <div className="w-7 h-7 rounded-lg bg-slate-800 text-white flex items-center justify-center">
            <Building2 size={14} />
          </div>
        )}
        <div className="hidden sm:block text-left min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-muted leading-tight">Switch company</p>
          <p className="text-xs font-medium text-col leading-tight truncate">
            {workingCompany?.name || 'Select company'}
          </p>
        </div>
        <ChevronDown size={14} className="text-muted flex-shrink-0" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-12 w-64 card z-50 overflow-hidden py-1"
          >
            <p className="px-3 py-2 text-[10px] uppercase tracking-wider text-muted font-semibold">
              Work in company
            </p>
            {selectable.length === 0 ? (
              <p className="px-4 py-3 text-sm text-muted">No companies available.</p>
            ) : (
              selectable.map((company) => {
                const selected = company.id === workingCompany?.id;
                const src = companyLogoSrc(company);
                return (
                  <button
                    key={company.id}
                    type="button"
                    onClick={() => handleSelect(company)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors ${
                      selected ? 'bg-orange-50/70 dark:bg-orange-900/20' : ''
                    }`}
                  >
                    {src ? (
                      <img src={src} alt="" className="h-7 w-auto max-w-[44px] rounded-md object-contain logo-on-white flex-shrink-0" />
                    ) : (
                      <div className="h-7 w-7 rounded-md bg-slate-800 text-white flex items-center justify-center flex-shrink-0 text-[10px] font-bold">
                        {(company.code || company.name || '?').slice(0, 2)}
                      </div>
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium text-col truncate">{company.name}</span>
                      <span className="block text-xs text-muted truncate">{company.code}</span>
                    </span>
                    {selected && <Check size={16} className="text-primary-accent flex-shrink-0" />}
                  </button>
                );
              })
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
