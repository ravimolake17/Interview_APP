import { useEffect, useRef } from 'react';
import { SlidersHorizontal } from 'lucide-react';

function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
        active
          ? 'bg-blue-600 text-white'
          : 'border border-col text-muted hover:bg-slate-50 dark:hover:bg-slate-800'
      }`}
    >
      {children}
    </button>
  );
}

export default function ListFiltersMenu({
  open,
  onOpenChange,
  activeCount = 0,
  jobFilter,
  onJobFilter,
  jobOptions = [],
  minScore,
  onMinScore,
  extra = null,
  onClear,
}) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        onOpenChange(false);
      }
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open, onOpenChange]);

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
          open || activeCount > 0
            ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800'
            : 'text-muted hover:bg-slate-100 dark:hover:bg-slate-800 border-col'
        }`}
      >
        <SlidersHorizontal size={12} />
        Filters
        {activeCount > 0 && (
          <span className="ml-0.5 min-w-[16px] h-4 px-1 rounded-full bg-blue-600 text-white text-[10px] leading-4 text-center">
            {activeCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-30 w-72 card p-4 shadow-lg space-y-4">
          <div>
            <label className="text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5">
              Applied job
            </label>
            <select
              value={jobFilter}
              onChange={(e) => onJobFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-xl border border-col bg-transparent text-col focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            >
              <option value="All">All jobs</option>
              {jobOptions.map((job) => (
                <option key={job} value={job}>{job}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5">
              Min match score: {minScore}%
            </label>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={minScore}
              onChange={(e) => onMinScore(Number(e.target.value))}
              className="w-full accent-blue-600"
            />
          </div>

          {extra}

          <div className="flex items-center justify-between pt-1 border-t border-col">
            <button
              type="button"
              onClick={onClear}
              className="text-xs font-medium text-muted hover:text-col"
            >
              Clear filters
            </button>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 text-white"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function FilterChips({ label, value, options, onChange }) {
  return (
    <div>
      <label className="text-xs font-semibold text-muted uppercase tracking-wider block mb-1.5">
        {label}
      </label>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <Chip
            key={option}
            active={value === option}
            onClick={() => onChange(option)}
          >
            {option}
          </Chip>
        ))}
      </div>
    </div>
  );
}
