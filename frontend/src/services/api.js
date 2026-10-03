import axios from 'axios';
import { getSuperAdminCompanyId } from '../utils/roles';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

/** Backend origin for stored resume/JD files (filesystem, not in DB). */
const BACKEND_ORIGIN = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, '');

const ACCESS_KEY = 'hr_access_token';
const REFRESH_KEY = 'hr_refresh_token';

/**
 * Resolve a stored screening file URL from the database.
 * Files live on disk under backend/agents/screening_agent/uploads/ and are served at /screening-files/...
 */
export function getScreeningFileUrl(storedPath) {
  if (!storedPath) return '';
  if (/^https?:\/\//i.test(storedPath)) return storedPath;
  const path = storedPath.startsWith('/') ? storedPath : `/${storedPath}`;
  if (BACKEND_ORIGIN) return `${BACKEND_ORIGIN}${path}`;
  return path;
}

export const AUTH_SESSION_CLEARED_EVENT = 'hr-auth-session-cleared';

export function getStoredAuth() {
  const accessToken = localStorage.getItem(ACCESS_KEY);
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!accessToken) return null;
  return { accessToken, refreshToken };
}

export function setAuthTokens(accessToken, refreshToken) {
  localStorage.setItem(ACCESS_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearAuthTokens() {
  const hadSession = Boolean(localStorage.getItem(ACCESS_KEY) || localStorage.getItem(REFRESH_KEY));
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  if (hadSession && typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_SESSION_CLEARED_EVENT));
  }
}

function headerValue(headers, name) {
  if (!headers) return '';
  if (typeof headers.get === 'function') {
    return headers.get(name) || headers.get(name.toLowerCase()) || '';
  }
  return headers[name] || headers[name.toLowerCase()] || '';
}

function bearerFromConfig(config) {
  const header = headerValue(config?.headers, 'Authorization');
  return String(header).replace(/^Bearer\s+/i, '').trim();
}

function isAuthUrl(url) {
  const path = String(url || '');
  return path.includes('/auth/login') || path.includes('/auth/refresh');
}

let refreshPromise = null;

async function requestNewAccessToken() {
  const stored = getStoredAuth();
  if (!stored?.refreshToken) {
    clearAuthTokens();
    throw new Error('No refresh token');
  }

  try {
    const { data } = await axios.post(
      `${API_BASE}/auth/refresh`,
      { refresh_token: stored.refreshToken },
      { timeout: 15000 },
    );
    setAuthTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch (error) {
    const latest = getStoredAuth();
    // Another request already rotated the session; keep the new tokens.
    if (latest?.accessToken && latest.refreshToken !== stored.refreshToken) {
      return latest.accessToken;
    }
    if (latest?.accessToken && latest.accessToken !== stored.accessToken) {
      return latest.accessToken;
    }
    clearAuthTokens();
    throw error;
  }
}

export function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = requestNewAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

const KEEP_ALIVE_AHEAD_MS = 2 * 60 * 1000;
const KEEP_ALIVE_TICK_MS = 30 * 1000;

export function getAccessTokenExpiryMs(accessToken) {
  try {
    const segment = String(accessToken || '').split('.')[1];
    if (!segment) return 0;
    const padded = segment.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(padded));
    return Number(payload.exp) * 1000;
  } catch {
    return 0;
  }
}

/** Refresh the access token before it expires so the UI never waits on a 401 storm. */
export function startAuthKeepAlive() {
  const tick = () => {
    const stored = getStoredAuth();
    if (!stored?.accessToken || !stored.refreshToken) return;
    const expiresAt = getAccessTokenExpiryMs(stored.accessToken);
    if (!expiresAt) return;
    if (Date.now() >= expiresAt - KEEP_ALIVE_AHEAD_MS) {
      refreshAccessToken().catch(() => {});
    }
  };
  tick();
  return window.setInterval(tick, KEEP_ALIVE_TICK_MS);
}

export function attachAuthInterceptors(client) {
  client.interceptors.request.use((config) => {
    const stored = getStoredAuth();
    if (stored?.accessToken) {
      config.headers.Authorization = `Bearer ${stored.accessToken}`;
    }
    try {
      const cached = JSON.parse(sessionStorage.getItem('hr_user_cache') || 'null');
      if (cached?.role === 'SUPERADMIN') {
        const companyId = getSuperAdminCompanyId();
        if (companyId) config.headers['X-Company-Id'] = String(companyId);
      }
    } catch {
      /* ignore */
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const original = error.config;
      if (!original || original._retry) return Promise.reject(error);
      if (error.response?.status !== 401 || isAuthUrl(original.url)) {
        return Promise.reject(error);
      }

      const stored = getStoredAuth();
      const failedAccess = bearerFromConfig(original);
      if (stored?.accessToken && stored.accessToken !== failedAccess) {
        original._retry = true;
        original.headers.Authorization = `Bearer ${stored.accessToken}`;
        return client(original);
      }

      if (!stored?.refreshToken) {
        clearAuthTokens();
        return Promise.reject(error);
      }

      try {
        const newAccess = await refreshAccessToken();
        original._retry = true;
        original.headers.Authorization = `Bearer ${newAccess}`;
        return client(original);
      } catch {
        return Promise.reject(error);
      }
    },
  );
  return client;
}

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

attachAuthInterceptors(api);

export const login = (email, password) => api.post('/auth/login', { email, password });
export const logout = (refreshToken) => api.post('/auth/logout', { refresh_token: refreshToken });
export const getMe = () => api.get('/auth/me');

export const validateToken = (token) => api.get(`/interview/token/${token}`);
export const getAvailableSlots = () => api.get('/interview/available-slots');
export const bookSlot = (token, slotId) =>
  api.post('/interview/book-slot', { token, slot_id: slotId });
export const joinInterview = (token, role) =>
  api.get(`/interview/join/${encodeURIComponent(token)}`, {
    params: role ? { role } : undefined,
  });
export const getInterviewDetails = (candidateId) =>
  api.get(`/interview/details/${candidateId}`);
export const getInterviewCalendar = (weekStart) =>
  api.get('/interview/calendar', { params: weekStart ? { week_start: weekStart } : {} });

export const getCandidateBlueprint = (candidateId) =>
  api.get(`/interview/blueprint/candidates/${candidateId}`);
export const generateCandidateBlueprint = (candidateId, options = {}) => {
  const {
    force = false,
    candidateLevel = undefined,
    totalDurationMinutes = undefined,
  } = typeof options === 'boolean' ? { force: options } : options;
  const body = { force };
  if (candidateLevel) body.candidate_level = candidateLevel;
  if (totalDurationMinutes != null && totalDurationMinutes !== '') {
    body.total_duration_minutes = Number(totalDurationMinutes);
  }
  return api.post(`/interview/blueprint/candidates/${candidateId}`, body);
};

export const getInterviewAgentStatus = (candidateId) =>
  api.get(`/interview/agent4/candidates/${candidateId}/status`);
export const getInterviewQuestions = (candidateId) =>
  api.get(`/interview/agent4/candidates/${candidateId}/questions`);
export const generateInterviewQuestions = (candidateId, force = false) =>
  api.post(`/interview/agent4/candidates/${candidateId}/questions`, { force });
export const addInterviewQuestion = (candidateId, payload) =>
  api.post(`/interview/agent4/candidates/${candidateId}/questions/manual`, payload);
export const updateInterviewQuestion = (candidateId, questionId, payload) =>
  api.patch(`/interview/agent4/candidates/${candidateId}/questions/manual/${questionId}`, payload);
export const deleteInterviewQuestion = (candidateId, questionId) =>
  api.delete(`/interview/agent4/candidates/${candidateId}/questions/manual/${questionId}`);
export const generateInterviewFollowups = (candidateId, payload) =>
  api.post(`/interview/agent4/candidates/${candidateId}/followups`, payload);
export const transcribeInterviewAudio = (
  candidateId,
  file,
  { questionId, partial = false, priorText } = {},
) => {
  const form = new FormData();
  form.append('file', file);
  if (questionId) form.append('question_id', questionId);
  if (partial) form.append('partial', 'true');
  if (priorText) form.append('prior_text', priorText);
  return api.post(`/interview/agent4/candidates/${candidateId}/transcribe`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const startInterviewSession = (candidateId, forceQuestions = false) =>
  api.post(`/interview/agent4/candidates/${candidateId}/session/start`, {
    force_questions: forceQuestions,
  });
export const submitInterviewSessionAnswer = (candidateId, answerText) =>
  api.post(`/interview/agent4/candidates/${candidateId}/session/answer`, {
    answer_text: answerText,
  });
export const getInterviewSession = (candidateId) =>
  api.get(`/interview/agent4/candidates/${candidateId}/session`);
export const speakInterviewText = (candidateId, { text, questionId } = {}) =>
  api.post(
    `/interview/agent4/candidates/${candidateId}/speak`,
    {
      ...(text ? { text } : {}),
      ...(questionId ? { question_id: questionId } : {}),
    },
    { responseType: 'blob' }
  );
export const prepareInterviewTTS = (candidateId, questionSetId) =>
  api.post(`/interview/agent4/candidates/${candidateId}/questions/${questionSetId}/prepare-tts`);

export const getEvaluationAgentStatus = (candidateId) =>
  api.get(`/interview/agent6/candidates/${candidateId}/status`);
export const evaluateInterviewAnswer = (candidateId, payload) =>
  api.post(`/interview/agent6/candidates/${candidateId}/evaluate`, payload);
export const listInterviewEvaluations = (candidateId) =>
  api.get(`/interview/agent6/candidates/${candidateId}/evaluations`);
export const getOralAnswerAudio = (candidateId, questionId) =>
  api.get(
    `/interview/agent6/candidates/${candidateId}/answers/${encodeURIComponent(questionId)}/audio`,
    {
      responseType: 'blob',
      timeout: 60000,
      headers: { Accept: 'audio/webm,audio/*,*/*' },
    },
  );

export const getRecommendationAgentStatus = (candidateId) =>
  api.get(`/interview/agent7/candidates/${candidateId}/status`);
export const getRecommendationReport = (candidateId) =>
  api.get(`/interview/agent7/candidates/${candidateId}/report`);
export const generateRecommendationReport = (candidateId, force = false) =>
  api.post(`/interview/agent7/candidates/${candidateId}/generate`, { force });
export const listHrRecommendationReports = () =>
  api.get('/interview/agent7/reports');

export const getFraudAgentReady = () => api.get('/interview/agent5/ready');
export const getFraudAgentStatus = (candidateId) =>
  api.get(`/interview/agent5/candidates/${candidateId}/status`);
export const bootstrapFraudSession = (candidateId) =>
  api.post(`/interview/agent5/candidates/${candidateId}/bootstrap`);
export const getFraudAgentReport = (candidateId) =>
  api.get(`/interview/agent5/candidates/${candidateId}/report`);
export const getInterviewRoomRuntime = (candidateId) =>
  api.get(`/interview/room/candidates/${candidateId}/runtime`);
export const controlInterviewRoom = (candidateId, action, message) =>
  api.post(`/interview/room/candidates/${candidateId}/control`, {
    action,
    ...(message ? { message } : {}),
  });

export const getHRCandidates = (status = 'all') =>
  api.get('/hr/candidates', { params: { status } });
export const getHRCandidateDetail = (candidateId) =>
  api.get(`/hr/candidates/${candidateId}`);
export const shortlistCandidate = (candidateId) =>
  api.post(`/hr/candidates/${candidateId}/shortlist`);
export const rejectCandidate = (candidateId) =>
  api.post(`/hr/candidates/${candidateId}/reject`);
export const resendCandidateInvite = (candidateId) =>
  api.post(`/hr/candidates/${candidateId}/resend-invite`);
export const updateCandidateEmail = (candidateId, email) =>
  api.patch(`/hr/candidates/${candidateId}/email`, { email });
export const getAuditLogs = (limit = 100, companyId) =>
  api.get('/hr/audit-logs', {
    params: {
      limit,
      ...(companyId && companyId !== 'all' ? { company_id: companyId } : {}),
    },
  });

export const getDashboardStats = () => api.get('/hr/dashboard/stats');

export const getJobs = () => api.get('/jobs');
export const checkJobDuplicate = ({ title, jdFileUrl } = {}) =>
  api.get('/jobs/duplicates', {
    params: {
      ...(title ? { title } : {}),
      ...(jdFileUrl ? { jd_file_url: jdFileUrl } : {}),
    },
  });
export const createJob = (payload) => api.post('/jobs', payload);
export const updateJob = (jobId, payload) => api.patch(`/jobs/${jobId}`, payload);
export const deleteJob = (jobId) => api.delete(`/jobs/${jobId}`);

export const getUsers = () => api.get('/auth/users');
export const createUser = (payload) => api.post('/auth/users', payload);
export const updateUser = (userId, payload) => api.patch(`/auth/users/${userId}`, payload);

export const getCompanies = () => api.get('/companies');
export const createCompany = (payload) => api.post('/companies', payload);
export const updateCompany = (companyId, payload) => api.patch(`/companies/${companyId}`, payload);
export const createCompanyUser = (companyId, payload) =>
  api.post(`/companies/${companyId}/users`, payload);

export const getDepartments = () => api.get('/departments');
export const getManagedDepartments = (params = {}) => api.get('/departments/manage', { params });
export const createDepartment = (payload) => api.post('/departments', payload);
export const updateDepartment = (departmentId, payload) =>
  api.patch(`/departments/${departmentId}`, payload);
export const getSuperAdminSystem = () => api.get('/superadmin/system');
export const updateSuperAdminCompany = (payload) => api.patch('/superadmin/company', payload);
export const updateScreeningPolicy = (payload) => api.patch('/superadmin/screening-policy', payload);
export const getDatabaseTables = () => api.get('/superadmin/database/tables');
export const getDatabaseRows = (schema, table, params = {}) =>
  api.get(`/superadmin/database/tables/${schema}/${table}`, { params });
export const getDataCatalog = () => api.get('/superadmin/data/catalog');
export const getDataRecords = (entity, params = {}) =>
  api.get(`/superadmin/data/${entity}`, { params });
export const getDataImpact = (entity, recordId) =>
  api.get(`/superadmin/data/${entity}/${encodeURIComponent(recordId)}/impact`);
export const createDataUser = (payload) => api.post('/superadmin/data/users', payload);
export const updateDataUser = (userId, payload) => api.patch(`/superadmin/data/users/${userId}`, payload);
export const createDataJob = (payload) => api.post('/superadmin/data/jobs', payload);
export const updateDataJob = (jobId, payload) => api.patch(`/superadmin/data/jobs/${jobId}`, payload);
export const deleteDataJob = (jobId) => api.delete(`/superadmin/data/jobs/${jobId}`);
export const createDataDepartment = (payload) => api.post('/superadmin/data/departments', payload);
export const updateDataDepartment = (departmentId, payload) =>
  api.patch(`/superadmin/data/departments/${departmentId}`, payload);
export const deactivateDataDepartment = (departmentId) =>
  api.delete(`/superadmin/data/departments/${departmentId}`);
export const updateDataCandidate = (candidateId, payload) =>
  api.patch(`/superadmin/data/candidates/${encodeURIComponent(candidateId)}`, payload);
export const updateDataCompany = (payload) => api.patch('/superadmin/data/company', payload);

export const getSettings = () => api.get('/settings');
export const updateProfileSettings = (payload) => api.patch('/settings/profile', payload);
export const updateCompanySettings = (payload) => api.patch('/settings/company', payload);
export const updatePreferenceSettings = (payload) => api.patch('/settings/preferences', payload);
export const updateAIModelSettings = (payload) => api.patch('/settings/ai-model', payload);
export const updateIntegrationSettings = (payload) => api.patch('/superadmin/integration', payload);
export const updateCompanySmtp = (companyId, payload) =>
  api.patch(`/superadmin/smtp/${companyId}`, payload);
export const testIntegrationConnection = () => api.post('/settings/integration/test');
export const getInterviewAvailability = () => api.get('/settings/interview-availability');
export const updateInterviewAvailability = (payload) =>
  api.patch('/settings/interview-availability', payload);

export default api;
