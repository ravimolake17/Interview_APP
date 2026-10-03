import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import {
  getAuditLogs,
  getDashboardStats,
  getHRCandidates,
  getHRCandidateDetail,
  getJobs,
  createJob as createJobApi,
  updateJob as updateJobApi,
  deleteJob as deleteJobApi,
  rejectCandidate,
  shortlistCandidate,
  getSettings,
  updatePreferenceSettings,
  getDepartments,
  getCompanies,
} from '../services/api';
import { useAuth } from './AuthContext';
import {
  getSuperAdminCompanyId,
  isStaffAdmin,
  isSuperAdmin,
  setSuperAdminCompanyId,
} from '../utils/roles';
import {
  mapAuditToActivity,
  mapCandidateFromBackend,
} from '../utils/hrMappers';
import {
  applyAppearance,
  loadAppearanceSettings,
  saveAppearanceSettings,
} from '../utils/theme';
import {
  buildNotifications,
  filterDismissedNotifications,
  filterNotificationPreferences,
  loadDismissedIds,
  saveDismissedIds,
} from '../utils/notifications';

const AppContext = createContext(null);

function mapJobFromBackend(job) {
  return {
    id: job.id,
    title: job.title,
    department: job.department || 'Hiring',
    experience: job.experience || 'As per JD',
    location: job.location || 'India',
    description: job.description || '',
    skills: job.skills || [],
    applicants: job.applicants || 0,
    applicantList: job.applicant_list || [],
    status: job.status || 'Active',
    created: job.created_at ? String(job.created_at).slice(0, 10) : '',
    jdOriginalFilename: job.jd_original_filename,
    jdFileUrl: job.jd_file_url,
    jdText: job.jd_text,
    parsedJd: job.parsed_jd || null,
  };
}

const EMPTY_STATS = {
  total_candidates: 0,
  active_jobs: 0,
  ai_screened: 0,
  pending_reviews: 0,
  shortlisted: 0,
  rejected: 0,
  interview_scheduled: 0,
  interview_completed: 0,
  average_match_score: 0,
  status_distribution: [],
  applications_per_job: [],
  match_trend: [],
  top_skills: [],
  hiring_funnel: [],
  invite_delivery: {
    issued: 0,
    not_issued: 0,
    awaiting_booking: 0,
    booked: 0,
    candidates: [],
  },
};

const DEFAULT_NOTIFICATION_PREFERENCES = {
  new_candidate_uploaded: true,
  ai_screening_complete: true,
  candidate_shortlisted: true,
  job_application_received: true,
  weekly_report: true,
};

export function AppProvider({ children }) {
  const { isAuthenticated, user } = useAuth();
  const [appearance, setAppearance] = useState(() => loadAppearanceSettings(null));
  const [notificationPreferences, setNotificationPreferences] = useState(
    DEFAULT_NOTIFICATION_PREFERENCES,
  );
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [stats, setStats] = useState(EMPTY_STATS);
  const [activity, setActivity] = useState([]);
  const [auditEntries, setAuditEntries] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [dismissedNotificationIds, setDismissedNotificationIds] = useState(() => loadDismissedIds(null));
  const [toasts, setToasts] = useState([]);
  const [screeningResults, setScreeningResults] = useState([]);
  const [isScreening, setIsScreening] = useState(false);
  const [loadingData, setLoadingData] = useState(true);
  const [dataError, setDataError] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [workingCompanyId, setWorkingCompanyId] = useState(() => {
    if (isSuperAdmin(user?.role)) return getSuperAdminCompanyId();
    return user?.company_id || null;
  });
  const hasLoadedRef = useRef(false);
  const lastRefreshAtRef = useRef(0);
  const refreshGenerationRef = useRef(0);

  const darkMode = appearance.theme === 'dark';

  useLayoutEffect(() => {
    applyAppearance(appearance);
  }, [appearance]);

  useEffect(() => {
    setDismissedNotificationIds(loadDismissedIds(user?.id ?? null));
  }, [user?.id]);

  useEffect(() => {
    const saved = loadAppearanceSettings(user?.id ?? null);
    setAppearance(saved);
  }, [user?.id]);

  useEffect(() => {
    if (!isAuthenticated) {
      setCompanies([]);
      setWorkingCompanyId(null);
      return;
    }
    if (!isSuperAdmin(user?.role)) {
      setCompanies(user?.company ? [user.company] : []);
      setWorkingCompanyId(user?.company_id || null);
      return;
    }

    let cancelled = false;
    getCompanies()
      .then(({ data }) => {
        if (cancelled) return;
        const rows = (data.companies || []).filter((company) => company.status !== 'inactive');
        const allRows = data.companies || [];
        setCompanies(allRows);
        const saved = getSuperAdminCompanyId();
        const match =
          allRows.find((company) => company.id === saved && company.status === 'active')
          || rows[0]
          || allRows[0]
          || null;
        if (match) {
          setSuperAdminCompanyId(match.id);
          setWorkingCompanyId(match.id);
        }
      })
      .catch(() => {
        if (!cancelled) setCompanies([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, user?.role, user?.company_id, user?.company]);

  const workingCompany = useMemo(
    () => companies.find((company) => company.id === workingCompanyId) || user?.company || null,
    [companies, workingCompanyId, user?.company],
  );

  const switchWorkingCompany = useCallback((companyId) => {
    const nextId = Number(companyId);
    if (!nextId || nextId === workingCompanyId) return;
    setSuperAdminCompanyId(nextId);
    refreshGenerationRef.current += 1;
    hasLoadedRef.current = false;
    lastRefreshAtRef.current = 0;
    setCandidates([]);
    setJobs([]);
    setDepartments([]);
    setStats(EMPTY_STATS);
    setActivity([]);
    setAuditEntries([]);
    setScreeningResults([]);
    setDataError(null);
    setLoadingData(true);
    setWorkingCompanyId(nextId);
  }, [workingCompanyId]);

  const reloadCompanies = useCallback(async () => {
    if (!isSuperAdmin(user?.role)) return [];
    const { data } = await getCompanies();
    const rows = data.companies || [];
    setCompanies(rows);
    return rows;
  }, [user?.role]);

  useEffect(() => {
    if (!isAuthenticated || !isStaffAdmin(user?.role)) return;
    if (isSuperAdmin(user?.role) && !workingCompanyId) return;
    getSettings()
      .then(({ data }) => {
        const remoteAppearance = data.preferences?.appearance;
        if (remoteAppearance) {
          const mapped = {
            theme: remoteAppearance.theme,
            primaryColorId: remoteAppearance.primary_color_id,
          };
          setAppearance(mapped);
          saveAppearanceSettings(user.id, mapped);
        }
        setNotificationPreferences(
          data.preferences?.notifications || DEFAULT_NOTIFICATION_PREFERENCES,
        );
      })
      .catch(() => {
        // Keep local preferences when the settings API is unavailable.
      });
  }, [isAuthenticated, user?.id, user?.role, workingCompanyId]);

  const notifications = useMemo(() => {
    const built = buildNotifications({
      auditEntries,
      candidates,
      isAdmin: isStaffAdmin(user?.role),
    });
    return filterDismissedNotifications(
      filterNotificationPreferences(built, notificationPreferences),
      dismissedNotificationIds,
    );
  }, [
    auditEntries,
    candidates,
    user?.role,
    dismissedNotificationIds,
    notificationPreferences,
  ]);

  const dismissNotification = useCallback((notificationId) => {
    setDismissedNotificationIds((current) => {
      const next = new Set(current);
      next.add(notificationId);
      saveDismissedIds(user?.id ?? null, next);
      return next;
    });
  }, [user?.id]);

  const clearAllNotifications = useCallback((notificationIds = []) => {
    if (!notificationIds.length) return;
    setDismissedNotificationIds((current) => {
      const next = new Set(current);
      notificationIds.forEach((id) => next.add(id));
      saveDismissedIds(user?.id ?? null, next);
      return next;
    });
  }, [user?.id]);

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts((current) => [...current, { id, message, type }]);
    const durationMs = type === 'error' || type === 'warning' ? 9000 : 4000;
    setTimeout(() => {
      setToasts((current) => current.filter((item) => item.id !== id));
    }, durationMs);
  }, []);

  const setTheme = useCallback((theme) => {
    setAppearance((current) => ({ ...current, theme }));
  }, []);

  const setPrimaryColorId = useCallback((primaryColorId) => {
    setAppearance((current) => ({ ...current, primaryColorId }));
  }, []);

  const saveAppearance = useCallback(async () => {
    saveAppearanceSettings(user?.id ?? null, appearance);
    if (user?.id) {
      await updatePreferenceSettings({
        appearance: {
          theme: appearance.theme,
          primary_color_id: appearance.primaryColorId,
        },
        notifications: notificationPreferences,
      });
    }
    addToast('Appearance settings saved.', 'success');
  }, [appearance, notificationPreferences, user?.id, addToast]);

  const saveNotificationPreferences = useCallback(async (next) => {
    await updatePreferenceSettings({
      appearance: {
        theme: appearance.theme,
        primary_color_id: appearance.primaryColorId,
      },
      notifications: next,
    });
    setNotificationPreferences(next);
  }, [appearance]);

  const toggleDark = useCallback(() => {
    setAppearance((current) => {
      const next = { ...current, theme: current.theme === 'dark' ? 'light' : 'dark' };
      saveAppearanceSettings(user?.id ?? null, next);
      return next;
    });
  }, [user?.id]);

  const removeToast = useCallback((id) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const refreshData = useCallback(async (options = {}) => {
    const silent = Boolean(options.silent);
    const force = Boolean(options.force);
    const now = Date.now();

    if (!isAuthenticated) {
      setCandidates([]);
      setJobs([]);
      setDepartments([]);
      setStats(EMPTY_STATS);
      setActivity([]);
      setAuditEntries([]);
      hasLoadedRef.current = false;
      lastRefreshAtRef.current = 0;
      setLoadingData(false);
      return;
    }

    if (isSuperAdmin(user?.role) && !workingCompanyId) {
      return;
    }

    if (
      silent
      && !force
      && hasLoadedRef.current
      && now - lastRefreshAtRef.current < 2500
    ) {
      return;
    }

    lastRefreshAtRef.current = now;
    const generation = ++refreshGenerationRef.current;
    const showSpinner = !silent || !hasLoadedRef.current;
    if (showSpinner) {
      setLoadingData(true);
      setDataError(null);
    }

    try {
      const requests = [
        getHRCandidates('all'),
        getDashboardStats(),
        getJobs(),
        getDepartments(),
      ];
      if (isSuperAdmin(user?.role)) {
        requests.push(getAuditLogs(100));
      }

      const results = await Promise.all(requests);
      if (generation !== refreshGenerationRef.current) return;

      const candidatesRes = results[0];
      const statsRes = results[1];
      const jobsRes = results[2];
      const departmentsRes = results[3];
      const auditRes = isSuperAdmin(user?.role) ? results[4] : null;

      const rawCandidates = candidatesRes.data.candidates || [];
      setCandidates(rawCandidates.map((candidate) => mapCandidateFromBackend(candidate)));
      setJobs((jobsRes.data.jobs || []).map(mapJobFromBackend));
      setDepartments((departmentsRes.data.departments || []).map((item) => item.name));
      setStats(statsRes.data || EMPTY_STATS);
      setActivity(auditRes ? (auditRes.data.entries || []).map(mapAuditToActivity) : []);
      setAuditEntries(auditRes ? auditRes.data.entries || [] : []);
      hasLoadedRef.current = true;
    } catch (error) {
      if (generation !== refreshGenerationRef.current) return;
      setDataError(error.response?.data?.detail || 'Failed to load dashboard data.');
      if (!silent) {
        addToast('Could not load data from backend.', 'error');
      }
    } finally {
      if (generation === refreshGenerationRef.current && showSpinner) {
        setLoadingData(false);
      }
    }
  }, [isAuthenticated, user?.role, workingCompanyId, addToast]);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  useAutoRefresh(
    () => refreshData({ silent: true }),
    { enabled: isAuthenticated, intervalMs: 15000 },
  );

  const addJob = useCallback(async (job) => {
    const { data } = await createJobApi({
      title: job.title,
      department: job.department,
      experience: job.experience,
      location: job.location,
      description: job.description,
      skills: job.skills || [],
      status: job.status || 'Active',
      jd_original_filename: job.jdOriginalFilename,
      jd_file_url: job.jdFileUrl,
      jd_text: job.jdText,
      parsed_jd: job.parsedJd,
      on_duplicate: job.onDuplicate || 'error',
    });
    const mapped = mapJobFromBackend(data);
    setJobs((current) => [mapped, ...current.filter((item) => item.id !== mapped.id)]);
    refreshData({ silent: true, force: true });
    return mapped;
  }, [refreshData]);

  const updateJob = useCallback(async (jobId, patch) => {
    const { data } = await updateJobApi(jobId, {
      title: patch.title,
      department: patch.department,
      experience: patch.experience,
      location: patch.location,
      description: patch.description,
      skills: patch.skills,
      status: patch.status,
      jd_original_filename: patch.jdOriginalFilename,
      jd_file_url: patch.jdFileUrl,
      jd_text: patch.jdText,
      parsed_jd: patch.parsedJd,
    });
    const mapped = mapJobFromBackend(data);
    setJobs((current) => current.map((item) => (item.id === mapped.id ? mapped : item)));
    refreshData({ silent: true, force: true });
    return mapped;
  }, [refreshData]);

  const removeJob = useCallback(async (jobId) => {
    await deleteJobApi(jobId);
    setJobs((current) => current.filter((item) => item.id !== jobId));
    refreshData({ silent: true, force: true });
  }, [refreshData]);

  const updateCandidateStatus = useCallback(
    async (candidateId, status) => {
      try {
        if (status === 'Shortlisted') {
          await shortlistCandidate(candidateId);
          addToast('Candidate shortlisted and invite sent.', 'success');
        } else if (status === 'Rejected') {
          await rejectCandidate(candidateId);
          addToast('Candidate rejected.', 'success');
        }
        await refreshData({ silent: true, force: true });
      } catch (error) {
        addToast(error.response?.data?.detail || 'Failed to update candidate.', 'error');
        throw error;
      }
    },
    [addToast, refreshData],
  );

  const loadCandidateDetail = useCallback(async (candidateId) => {
    const { data } = await getHRCandidateDetail(candidateId);
    return mapCandidateFromBackend(data, data);
  }, []);

  const value = useMemo(
    () => ({
      darkMode,
      appearance,
      setTheme,
      setPrimaryColorId,
      saveAppearance,
      toggleDark,
      sidebarCollapsed,
      setSidebarCollapsed,
      jobs,
      departments,
      addJob,
      updateJob,
      removeJob,
      candidates,
      setCandidates,
      updateCandidateStatus,
      loadCandidateDetail,
      stats,
      activity,
      auditEntries,
      notifications,
      notificationPreferences,
      saveNotificationPreferences,
      dismissNotification,
      clearAllNotifications,
      loadingData,
      dataError,
      refreshData,
      toasts,
      addToast,
      removeToast,
      screeningResults,
      setScreeningResults,
      isScreening,
      setIsScreening,
      companies,
      workingCompanyId,
      workingCompany,
      switchWorkingCompany,
      reloadCompanies,
    }),
    [
      darkMode,
      appearance,
      setTheme,
      setPrimaryColorId,
      saveAppearance,
      toggleDark,
      sidebarCollapsed,
      jobs,
      departments,
      addJob,
      updateJob,
      removeJob,
      candidates,
      updateCandidateStatus,
      loadCandidateDetail,
      stats,
      activity,
      auditEntries,
      notifications,
      notificationPreferences,
      saveNotificationPreferences,
      dismissNotification,
      clearAllNotifications,
      loadingData,
      dataError,
      refreshData,
      toasts,
      addToast,
      removeToast,
      screeningResults,
      isScreening,
      companies,
      workingCompanyId,
      workingCompany,
      switchWorkingCompany,
      reloadCompanies,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export const useApp = () => useContext(AppContext);
