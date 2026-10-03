import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, ChevronDown,
  Mail, Phone, Users, FileText, Bot
} from 'lucide-react';
import { MatchScore, StatusBadge, ResultBadge } from '../../components/ui/Badges';
import EmptyState from '../../components/ui/EmptyState';
import LoadingSpinner from '../../components/LoadingSpinner';
import ListFiltersMenu from '../../components/ui/ListFiltersMenu';
import { getScreeningFileUrl } from '../../services/api';
import { useApp } from '../../context/AppContext';
import { matchesCandidate } from '../../utils/search';

const STATUS_TABS = ['All', 'Shortlisted', 'Interview Scheduled', 'Interview Completed'];
const RESULT_FILTERS = ['All', 'Hire', 'Consider', 'Reject', 'Hold'];

export default function Candidates() {
  const navigate = useNavigate();
  const { candidates, loadingData } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get('q') || '');
  const [statusFilter, setStatusFilter] = useState('All');
  const [resultFilter, setResultFilter] = useState('All');
  const [sortField, setSortField] = useState('matchScore');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [jobFilter, setJobFilter] = useState('All');
  const [minScore, setMinScore] = useState(0);
  const resultHeaderRef = useRef(null);
  const resultMenuRef = useRef(null);
  const [resultMenuOpen, setResultMenuOpen] = useState(false);
  const [resultMenuPos, setResultMenuPos] = useState({ top: 0, left: 0 });
  const PER_PAGE = 6;

  useEffect(() => {
    setSearch(searchParams.get('q') || '');
    setPage(1);
  }, [searchParams]);

  useEffect(() => {
    const candidateId = searchParams.get('candidate');
    if (!candidateId) return;
    navigate(`/candidates/${encodeURIComponent(candidateId)}`, { replace: true });
  }, [searchParams, navigate]);

  useEffect(() => {
    const onClickOutside = (event) => {
      if (
        resultHeaderRef.current && !resultHeaderRef.current.contains(event.target)
        && (!resultMenuRef.current || !resultMenuRef.current.contains(event.target))
      ) {
        setResultMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const openAgentsDashboard = (candidate) => {
    if (!candidate?.candidateId) return;
    navigate(`/candidates/${encodeURIComponent(candidate.candidateId)}`);
  };

  const jobOptions = useMemo(() => {
    const jobs = [...new Set(candidates.map((c) => c.appliedJob).filter(Boolean))];
    return jobs.sort((a, b) => a.localeCompare(b));
  }, [candidates]);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (jobFilter !== 'All') count += 1;
    if (minScore > 0) count += 1;
    return count;
  }, [jobFilter, minScore]);

  const handleSearchChange = (value) => {
    setSearch(value);
    setPage(1);
    if (value.trim()) {
      setSearchParams({ q: value.trim() });
    } else {
      setSearchParams({});
    }
  };

  const clearAdvancedFilters = () => {
    setJobFilter('All');
    setMinScore(0);
    setPage(1);
  };

  const sorted = useMemo(() => {
    return [...candidates]
      .filter((c) => {
        const matchSearch = matchesCandidate(c, search);
        const matchStatus =
          statusFilter === 'All' ||
          c.status === statusFilter ||
          (statusFilter === 'Interview Completed' && Boolean(c.interviewCompleted)) ||
          (statusFilter === 'Interview Scheduled' && Boolean(c.interviewScheduled) && !c.interviewCompleted);
        const matchResult = resultFilter === 'All' || c.interviewResult === resultFilter;
        const matchJob = jobFilter === 'All' || c.appliedJob === jobFilter;
        const matchScore = (c.matchScore || 0) >= minScore;
        return matchSearch && matchStatus && matchResult && matchJob && matchScore;
      })
      .sort((a, b) => {
        const val = sortDir === 'asc' ? 1 : -1;
        if (sortField === 'matchScore') return ((a.matchScore || 0) - (b.matchScore || 0)) * val;
        if (sortField === 'experience') {
          const aYears = Number.isFinite(a.experienceYears) ? a.experienceYears : -1;
          const bYears = Number.isFinite(b.experienceYears) ? b.experienceYears : -1;
          return (aYears - bYears) * val;
        }
        if (sortField === 'name') return a.name.localeCompare(b.name) * val;
        if (sortField === 'result') {
          return String(a.interviewResult || '').localeCompare(String(b.interviewResult || '')) * val;
        }
        return 0;
      });
  }, [candidates, search, statusFilter, resultFilter, jobFilter, minScore, sortField, sortDir]);

  const paginated = sorted.slice((page - 1) * PER_PAGE, page * PER_PAGE);
  const totalPages = Math.ceil(sorted.length / PER_PAGE);

  const applyResultFilter = (value) => {
    setResultFilter(value);
    setResultMenuOpen(false);
    setPage(1);
  };

  const toggleResultMenu = (event) => {
    event.stopPropagation();
    if (resultMenuOpen) {
      setResultMenuOpen(false);
      return;
    }
    const rect = resultHeaderRef.current?.getBoundingClientRect();
    if (rect) {
      setResultMenuPos({ top: rect.bottom + 6, left: rect.left });
    }
    setResultMenuOpen(true);
  };

  const toggleSort = (field) => {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortField(field); setSortDir('desc'); }
  };

  const SortTH = ({ field, label }) => (
    <th
      className="text-left px-5 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider cursor-pointer hover:text-col whitespace-nowrap select-none"
      onClick={() => toggleSort(field)}
    >
      <div className="flex items-center gap-1">
        {label}
        {sortField === field && <ChevronDown size={12} className={`transition-transform ${sortDir === 'asc' ? 'rotate-180' : ''}`} />}
      </div>
    </th>
  );

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      {loadingData && !candidates.length ? (
        <LoadingSpinner message="Loading candidates from database..." />
      ) : (
      <>
      <div>
        <h2 className="text-xl font-bold text-col">Candidates</h2>
        <p className="text-sm text-muted">{candidates.length} total candidates</p>
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search candidates…"
            className="pl-9 pr-4 py-2 text-sm rounded-xl border border-col bg-transparent w-full text-col placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
          />
        </div>
        <div className="flex gap-2">
          {STATUS_TABS.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setResultFilter('All'); setPage(1); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                statusFilter === s ? 'bg-blue-600 text-white' : 'text-muted hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <ListFiltersMenu
          open={filtersOpen}
          onOpenChange={setFiltersOpen}
          activeCount={activeFilterCount}
          jobFilter={jobFilter}
          onJobFilter={(value) => { setJobFilter(value); setPage(1); }}
          jobOptions={jobOptions}
          minScore={minScore}
          onMinScore={(value) => { setMinScore(value); setPage(1); }}
          onClear={clearAdvancedFilters}
        />
      </div>

      <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-col">
                  <SortTH field="name" label="Candidate" />
                  <th className="text-left px-5 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Contact</th>
                  <SortTH field="experience" label="Experience" />
                  <th className="text-left px-5 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Applied For</th>
                  <SortTH field="matchScore" label="Match Score" />
                  <th className="text-left px-5 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Status</th>
                  <th
                    ref={resultHeaderRef}
                    className="text-left px-5 py-3.5 text-xs font-semibold uppercase tracking-wider cursor-pointer hover:text-col whitespace-nowrap select-none"
                    onClick={toggleResultMenu}
                    title="Filter by interview result"
                  >
                    <div className={`flex items-center gap-1 ${resultFilter !== 'All' || resultMenuOpen ? 'text-blue-600' : 'text-muted'}`}>
                      Result
                      <ChevronDown size={12} className={`transition-transform ${resultMenuOpen ? 'rotate-180' : ''}`} />
                    </div>
                  </th>
                  <th className="text-left px-5 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {paginated.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-5 py-10">
                      <EmptyState
                        icon={Users}
                        title="No candidates found"
                        description={
                          resultFilter !== 'All'
                            ? `No candidates with result “${resultFilter}”. Choose All in the Result column to see everyone.`
                            : 'Adjust your search or filters to find candidates.'
                        }
                      />
                      {resultFilter !== 'All' && (
                        <div className="mt-3 flex justify-center">
                          <button
                            type="button"
                            onClick={() => applyResultFilter('All')}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 text-white"
                          >
                            Show all results
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ) : (
                <AnimatePresence>
                  {paginated.map((c, i) => (
                    <motion.tr
                      key={c.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: i * 0.04 }}
                      className="border-b border-col last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                      onClick={() => openAgentsDashboard(c)}
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                            style={{ background: c.avatarColor }}
                          >
                            {c.avatar}
                          </div>
                          <div className="min-w-0">
                            <p className="font-medium text-col">{c.name}</p>
                            {c.resumeFileUrl ? (
                              <a
                                href={getScreeningFileUrl(c.resumeFileUrl)}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 inline-flex items-center gap-1 mt-0.5 truncate max-w-[220px]"
                              >
                                <FileText size={11} className="flex-shrink-0" />
                                <span className="truncate">{c.resumeOriginalFilename || 'View resume'}</span>
                              </a>
                            ) : (
                              <span className="text-xs text-muted mt-0.5">No resume file</span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="space-y-0.5">
                          <p className="text-xs text-muted flex items-center gap-1"><Mail size={10} />{c.email}</p>
                          <p className="text-xs text-muted flex items-center gap-1"><Phone size={10} />{c.phone}</p>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-muted max-w-xs">
                        <p className="line-clamp-2 text-sm leading-snug">{c.experience}</p>
                      </td>
                      <td className="px-5 py-4">
                        <span className="text-sm text-col truncate max-w-36 block">{c.appliedJob}</span>
                      </td>
                      <td className="px-5 py-4">
                        <MatchScore score={c.matchScore} />
                      </td>
                      <td className="px-5 py-4"><StatusBadge status={c.status} /></td>
                      <td
                        className="px-5 py-4"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (c.interviewResult) {
                            applyResultFilter(c.interviewResult);
                          }
                        }}
                      >
                        <ResultBadge result={c.interviewResult} />
                      </td>
                      <td className="px-5 py-4">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openAgentsDashboard(c);
                          }}
                          className="flex items-center gap-1.5 text-xs text-blue-500 hover:text-blue-600 font-medium"
                        >
                          <Bot size={12} />Agents
                        </button>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-col">
              <p className="text-xs text-muted">
                Showing {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, sorted.length)} of {sorted.length}
              </p>
              <div className="flex gap-1">
                {Array.from({ length: totalPages }).map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setPage(i + 1)}
                    className={`w-7 h-7 rounded-lg text-xs font-medium transition-all ${
                      page === i + 1 ? 'bg-blue-600 text-white' : 'text-muted hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      {resultMenuOpen && (
        <div
          ref={resultMenuRef}
          className="fixed z-50 w-40 rounded-xl border border-col bg-white dark:bg-slate-900 shadow-lg p-1.5"
          style={{ top: resultMenuPos.top, left: resultMenuPos.left }}
        >
          {RESULT_FILTERS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => applyResultFilter(option)}
              className={`w-full text-left px-3 py-1.5 rounded-lg text-xs font-medium ${
                resultFilter === option
                  ? 'bg-blue-600 text-white'
                  : 'text-col hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {option === 'All' ? 'All results' : option}
            </button>
          ))}
        </div>
      )}
      </>
      )}
    </div>
  );
}
