import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Bot,
  CalendarDays,
  CheckCircle2,
  Clock,
  ExternalLink,
  ClipboardCheck,
  FileText,
  Link2,
  Loader2,
  Mail,
  Mic,
  MessageSquarePlus,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Sparkles,
  Video,
  AlertCircle,
  SlidersHorizontal,
  Volume2,
  Gauge,
  Square,
  Shield,
  Trash2,
} from 'lucide-react';
import EvaluationDetailPanels from '../../components/ui/EvaluationDetailPanels';
import { MatchScore, StatusBadge, RecommendationBadge } from '../../components/ui/Badges';
import LoadingSpinner from '../../components/LoadingSpinner';
import EmptyState from '../../components/ui/EmptyState';
import Modal from '../../components/ui/Modal';
import {
  getHRCandidateDetail,
  getCandidateBlueprint,
  generateCandidateBlueprint,
  resendCandidateInvite,
  getScreeningFileUrl,
  getInterviewAgentStatus,
  generateInterviewQuestions,
  addInterviewQuestion,
  updateInterviewQuestion,
  deleteInterviewQuestion,
  generateInterviewFollowups,
  transcribeInterviewAudio,
  startInterviewSession,
  submitInterviewSessionAnswer,
  speakInterviewText,
  prepareInterviewTTS,
  getEvaluationAgentStatus,
  listInterviewEvaluations,
  getOralAnswerAudio,
  getRecommendationAgentStatus,
  generateRecommendationReport,
  getFraudAgentStatus,
  getFraudAgentReport,
  getInterviewRoomRuntime,
  controlInterviewRoom,
  getInterviewAvailability,
} from '../../services/api';
import { mapCandidateFromBackend } from '../../utils/hrMappers';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { isSuperAdmin } from '../../utils/roles';
import { useAutoRefresh } from '../../hooks/useAutoRefresh';

const CANDIDATE_LEVELS = ['Fresher', 'Entry-level', 'Junior', 'Mid-level', 'Senior'];
const DEFAULT_DURATION_MINUTES = 30;
const QUESTION_CATEGORIES = [
  { id: 'introductory_questions', name: 'Introductory Questions' },
  { id: 'experience_questions', name: 'Experience Questions' },
  { id: 'skills_jd_keyword_questions', name: 'Skills & JD Keyword-Related Questions' },
  { id: 'project_related_questions', name: 'Project-Related Questions' },
  { id: 'education_courses_questions', name: 'Education & Courses Questions' },
];

function formatDateLabel(value) {
  if (!value) return '—';
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatTimeLabel(value) {
  if (!value) return '—';
  const raw = String(value);
  const match = raw.match(/^(\d{1,2}):(\d{2})/);
  if (!match) return raw.slice(0, 5);
  const hours = Number(match[1]);
  const minutes = match[2];
  const suffix = hours >= 12 ? 'PM' : 'AM';
  const hour12 = ((hours + 11) % 12) + 1;
  return `${hour12}:${minutes} ${suffix}`;
}

function formatApiError(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return err?.message || fallback;
}

function agent5CardStatus(agent5, joinLink, loading) {
  if (loading) return { label: 'Loading', tone: 'pending' };
  const raw = String(agent5?.session_status || agent5?.verification_status || '').toLowerCase();
  if (raw === 'completed') return { label: 'Completed', tone: 'ready' };
  if (raw === 'terminated') return { label: 'Terminated', tone: 'error' };
  if (raw === 'active' || raw === 'terminating') return { label: 'Interview live', tone: 'ready' };
  if (raw === 'ready' || raw.includes('verified')) return { label: 'Identity verified', tone: 'ready' };
  if (agent5?.agent5_session_id) {
    if (raw.includes('device') || raw.includes('enroll') || raw.includes('face') || raw.includes('voice')) {
      return { label: 'Checks in progress', tone: 'pending' };
    }
    return { label: 'Session started', tone: 'pending' };
  }
  if (joinLink) return { label: 'Awaiting candidate join', tone: 'pending' };
  return { label: 'Not scheduled', tone: 'missing' };
}

/** Build interviewer (HR/Admin) room link from the candidate hashed join URL (skips identity gates). */
function toInterviewerJoinLink(joinLink) {
  if (!joinLink) return null;
  try {
    const url = new URL(joinLink, window.location.origin);
    if (/\/(interview|join)\/hr\//.test(url.pathname)) return url.toString();
    url.pathname = url.pathname
      .replace(/\/interview\//, '/interview/hr/')
      .replace(/\/join\//, '/join/hr/');
    return url.toString();
  } catch {
    return String(joinLink)
      .replace('/interview/', '/interview/hr/')
      .replace('/join/', '/join/hr/');
  }
}

function answerKindLabel(kind) {
  if (kind === 'mcq') return 'MCQ';
  if (kind === 'followup') return 'Oral follow-up';
  return 'Oral';
}

function answerStatusLabel(status) {
  if (status === 'answered') return 'Answered';
  if (status === 'skipped') return 'Skipped';
  return 'Not answered';
}

function OralAnswerAudio({ candidateId, questionId, hasAudio }) {
  const [src, setSrc] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!hasAudio || !candidateId || !questionId) return undefined;
    let objectUrl = '';
    let cancelled = false;
    (async () => {
      try {
        const { data } = await getOralAnswerAudio(candidateId, questionId);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(data);
        setSrc(objectUrl);
      } catch {
        if (!cancelled) setError('Voice clip could not be loaded.');
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [candidateId, questionId, hasAudio]);

  if (!hasAudio) return null;
  if (error) return <p className="text-[11px] text-muted">{error}</p>;
  if (!src) return <p className="text-[11px] text-muted">Loading voice answer…</p>;
  return (
    <audio controls preload="metadata" className="w-full mt-1">
      <source src={src} type="audio/webm" />
    </audio>
  );
}

function AgentCard({ agent, title, subtitle, status, statusTone, children, actions }) {
  const tone = {
    ready: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    missing: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
    error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  }[statusTone || 'missing'];
  const agentNumber = String(agent || '').match(/Agent\s+(\d+)/i)?.[1];

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="card overflow-hidden flex flex-col min-h-0 h-[calc(100vh-16rem)] min-h-[32rem]"
    >
      <div className="px-5 py-3.5 border-b border-col flex items-start justify-between gap-3 shrink-0">
        <div className="min-w-0 flex items-start gap-2.5">
          {agentNumber ? (
            <span className="mt-0.5 w-7 h-7 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-900 text-xs font-bold flex items-center justify-center shrink-0">
              {agentNumber}
            </span>
          ) : null}
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-0.5">
              {agent}
            </p>
            <h3 className="text-base font-bold text-col">{title}</h3>
            {subtitle ? <p className="text-xs text-muted mt-0.5 truncate">{subtitle}</p> : null}
          </div>
        </div>
        {status ? (
          <span className={`shrink-0 px-2.5 py-1 rounded-full text-[11px] font-semibold ${tone}`}>
            {status}
          </span>
        ) : null}
      </div>
      <div className="p-4 flex-1 min-h-0 overflow-y-auto overscroll-contain space-y-4">
        {children}
      </div>
      {actions ? (
        <div className="px-4 py-3 border-t border-col bg-slate-50/60 dark:bg-slate-900/20 flex flex-wrap gap-2 shrink-0">
          {actions}
        </div>
      ) : null}
    </motion.section>
  );
}

function MetaRow({ icon: Icon, label, value, href }) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-muted shrink-0">
        <Icon size={14} />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-muted font-semibold">{label}</p>
        {href && value && value !== '—' ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-blue-600 dark:text-blue-400 hover:underline break-all inline-flex items-center gap-1"
          >
            {value}
            <ExternalLink size={12} />
          </a>
        ) : (
          <p className="text-sm text-col break-words">{value || '—'}</p>
        )}
      </div>
    </div>
  );
}

export default function CandidateAgentsDashboard() {
  const { candidateId } = useParams();
  const navigate = useNavigate();
  const { addToast, refreshData, workingCompanyId } = useApp();
  const { user } = useAuth();
  const showInterviewLab = isSuperAdmin(user?.role);

  const [candidate, setCandidate] = useState(null);
  const [blueprint, setBlueprint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [blueprintLoading, setBlueprintLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState('');
  const [editLevel, setEditLevel] = useState('Entry-level');
  const [editDuration, setEditDuration] = useState(DEFAULT_DURATION_MINUTES);
  const [defaultDuration, setDefaultDuration] = useState(DEFAULT_DURATION_MINUTES);
  const [agent4, setAgent4] = useState(null);
  const [agent4Loading, setAgent4Loading] = useState(false);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [followups, setFollowups] = useState([]);
  const [followupLoading, setFollowupLoading] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [transcribing, setTranscribing] = useState(false);
  const [selectedQuestionId, setSelectedQuestionId] = useState(null);
  const [questionEditor, setQuestionEditor] = useState(null);
  const [savingQuestion, setSavingQuestion] = useState(false);
  const [session, setSession] = useState(null);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [agent6, setAgent6] = useState(null);
  const [agent6Loading, setAgent6Loading] = useState(false);
  const [agent5, setAgent5] = useState(null);
  const [agent5Loading, setAgent5Loading] = useState(false);
  const [agent5Report, setAgent5Report] = useState(null);
  const [agent5ReportLoading, setAgent5ReportLoading] = useState(false);
  const [agent5ReportOpen, setAgent5ReportOpen] = useState(false);
  const [roomRuntime, setRoomRuntime] = useState(null);
  const [roomBusy, setRoomBusy] = useState(false);
  const [evaluations, setEvaluations] = useState([]);
  const [agent7, setAgent7] = useState(null);
  const [agent7Loading, setAgent7Loading] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [activeAgent, setActiveAgent] = useState(1);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [liveTranscribing, setLiveTranscribing] = useState(false);
  const [recordPreviewUrl, setRecordPreviewUrl] = useState(null);

  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const recordChunksRef = useRef([]);
  const recordTimerRef = useRef(null);
  const streamTimerRef = useRef(null);
  const streamInFlightRef = useRef(false);
  const lastPartialBlobSizeRef = useRef(0);
  const recordMimeTypeRef = useRef('audio/webm');
  const transcriptRef = useRef('');
  const recordPreviewUrlRef = useRef(null);
  const autoQuestionsRef = useRef(false);
  const autoPlanRef = useRef(false);

  const STREAM_INTERVAL_MS = 3000;
  const MIN_PARTIAL_BYTES = 8000;
  const MIN_GROWTH_BYTES = 4000;

  const syncPlanEditors = useCallback((data) => {
    const planData = data?.blueprint;
    const duration =
      planData?.time_allocation?.total_duration_minutes ??
      data?.default_duration_minutes ??
      DEFAULT_DURATION_MINUTES;
    const level = data?.candidate_level || planData?.candidate_level || 'Entry-level';
    setEditLevel(level);
    setEditDuration(Number(duration) || DEFAULT_DURATION_MINUTES);
    if (data?.default_duration_minutes) {
      setDefaultDuration(Number(data.default_duration_minutes) || DEFAULT_DURATION_MINUTES);
    }
  }, []);

  const loadAll = useCallback(async (options = {}) => {
    if (!candidateId) return;
    const silent = Boolean(options.silent);
    if (!silent) {
      setLoading(true);
      setError('');
    }
    try {
      const { data } = await getHRCandidateDetail(candidateId);
      setCandidate(mapCandidateFromBackend(data, data));

      setBlueprintLoading(true);
      try {
        const [blueprintRes, availabilityRes] = await Promise.allSettled([
          getCandidateBlueprint(candidateId),
          getInterviewAvailability(),
        ]);
        const availabilityMinutes = Number(availabilityRes.status === 'fulfilled'
          ? availabilityRes.value.data?.slot_minutes
          : NaN);
        if (Number.isFinite(availabilityMinutes) && availabilityMinutes > 0) {
          setDefaultDuration(availabilityMinutes);
        }
        if (blueprintRes.status === 'fulfilled') {
          setBlueprint(blueprintRes.value.data);
          syncPlanEditors({
            ...blueprintRes.value.data,
            default_duration_minutes: Number.isFinite(availabilityMinutes)
              ? availabilityMinutes
              : blueprintRes.value.data?.default_duration_minutes,
          });
        } else if (blueprintRes.reason?.response?.status === 404) {
          setBlueprint(null);
          setEditLevel('Entry-level');
          setEditDuration(
            Number.isFinite(availabilityMinutes) ? availabilityMinutes : DEFAULT_DURATION_MINUTES,
          );
          if (!autoPlanRef.current) {
            autoPlanRef.current = true;
            try {
              const generated = await generateCandidateBlueprint(candidateId, { force: false });
              setBlueprint(generated.data);
              syncPlanEditors({
                ...generated.data,
                default_duration_minutes: Number.isFinite(availabilityMinutes)
                  ? availabilityMinutes
                  : generated.data?.default_duration_minutes,
              });
            } catch {
              autoPlanRef.current = false;
            }
          }
        } else {
          throw blueprintRes.reason;
        }
      } finally {
        setBlueprintLoading(false);
      }

      setAgent4Loading(true);
      try {
        const statusRes = await getInterviewAgentStatus(candidateId);
        setAgent4(statusRes.data);
        const qs = statusRes.data?.question_set?.questions || [];
        if (qs.length) {
          setSelectedQuestionId(qs[0].id);
        } else if (statusRes.data?.blueprint_ready && !autoQuestionsRef.current) {
          autoQuestionsRef.current = true;
          setGeneratingQuestions(true);
          try {
            const { data } = await generateInterviewQuestions(candidateId, false);
            setAgent4((prev) => ({
              ...(prev || {}),
              blueprint_ready: true,
              questions_ready: true,
              speak_ready: Boolean(data.tts_ready),
              question_set: data,
            }));
            if (data.questions?.length) setSelectedQuestionId(data.questions[0].id);
          } catch {
            autoQuestionsRef.current = false;
          } finally {
            setGeneratingQuestions(false);
          }
        }
      } catch {
        setAgent4(null);
      } finally {
        setAgent4Loading(false);
      }

      setAgent6Loading(true);
      try {
        const [statusRes, evalRes] = await Promise.all([
          getEvaluationAgentStatus(candidateId),
          listInterviewEvaluations(candidateId),
        ]);
        setAgent6(statusRes.data);
        setEvaluations(evalRes.data?.evaluations || []);
        if (evalRes.data?.report || statusRes.data?.report) {
          setAgent6((prev) => ({ ...(prev || statusRes.data || {}), report: evalRes.data?.report || statusRes.data?.report }));
        }
      } catch {
        setAgent6(null);
        setEvaluations([]);
      } finally {
        setAgent6Loading(false);
      }

      setAgent7Loading(true);
      try {
        const recRes = await getRecommendationAgentStatus(candidateId);
        setAgent7(recRes.data);
      } catch {
        setAgent7(null);
      } finally {
        setAgent7Loading(false);
      }

      setAgent5Loading(true);
      try {
        const fraudRes = await getFraudAgentStatus(candidateId);
        setAgent5(fraudRes.data);
      } catch {
        setAgent5(null);
      } finally {
        setAgent5Loading(false);
      }
      try {
        const runtimeRes = await getInterviewRoomRuntime(candidateId);
        setRoomRuntime(runtimeRes.data);
      } catch {
        setRoomRuntime(null);
      }
    } catch (err) {
      if (!silent) {
        setError(err.response?.data?.detail || 'Failed to load candidate agents dashboard.');
        setCandidate(null);
        setBlueprint(null);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [candidateId, syncPlanEditors]);

  useEffect(() => {
    autoQuestionsRef.current = false;
    autoPlanRef.current = false;
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!candidate?.companyId || !workingCompanyId) return;
    if (Number(candidate.companyId) !== Number(workingCompanyId)) {
      navigate('/candidates', { replace: true });
    }
  }, [candidate?.companyId, workingCompanyId, navigate]);

  useAutoRefresh(async () => {
    if (!candidateId) return;
    try {
      const { data } = await getHRCandidateDetail(candidateId);
      setCandidate(mapCandidateFromBackend(data, data));
    } catch {
      // Keep the currently rendered candidate if a background refresh fails.
    }
    try {
      const runtimeRes = await getInterviewRoomRuntime(candidateId);
      setRoomRuntime(runtimeRes.data);
    } catch {
      // Runtime is optional during background refresh.
    }
  });

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  useEffect(() => {
    return () => {
      if (recordTimerRef.current) clearInterval(recordTimerRef.current);
      if (streamTimerRef.current) clearInterval(streamTimerRef.current);
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      if (recordPreviewUrlRef.current) {
        URL.revokeObjectURL(recordPreviewUrlRef.current);
      }
    };
  }, []);

  const setRecordPreview = useCallback((url) => {
    if (recordPreviewUrlRef.current) {
      URL.revokeObjectURL(recordPreviewUrlRef.current);
    }
    recordPreviewUrlRef.current = url;
    setRecordPreviewUrl(url);
  }, []);

  const transcribeAudioFile = useCallback(
    async (file, { partial = false, priorText } = {}) => {
      if (!partial) setTranscribing(true);
      try {
        const { data } = await transcribeInterviewAudio(candidateId, file, {
          questionId: selectedQuestionId || undefined,
          partial,
          priorText,
        });
        setTranscript(data.text || '');
        if (partial) return data;

        if (data.resume_corrected) {
          const fixes = (data.corrections || [])
            .slice(0, 3)
            .map((c) => `${c.from || c.from_text} → ${c.to}`)
            .join(', ');
          addToast(
            fixes
              ? `Transcript corrected using resume: ${fixes}`
              : 'Transcript refined using resume context.',
            'success',
          );
        } else {
          addToast('Audio transcribed with Whisper STT.', 'success');
        }
        return data;
      } catch (err) {
        if (!partial) {
          addToast(err.response?.data?.detail || 'Transcription failed.', 'error');
        }
        throw err;
      } finally {
        if (!partial) setTranscribing(false);
      }
    },
    [candidateId, selectedQuestionId, addToast],
  );

  const streamPartialTranscript = useCallback(async () => {
    if (
      streamInFlightRef.current ||
      mediaRecorderRef.current?.state !== 'recording' ||
      !recordChunksRef.current.length
    ) {
      return;
    }

    const blobType = recordMimeTypeRef.current || 'audio/webm';
    const blob = new Blob(recordChunksRef.current, { type: blobType });
    if (
      blob.size < MIN_PARTIAL_BYTES ||
      blob.size - lastPartialBlobSizeRef.current < MIN_GROWTH_BYTES
    ) {
      return;
    }

    streamInFlightRef.current = true;
    setLiveTranscribing(true);
    try {
      const ext = blobType.includes('ogg') ? 'ogg' : blobType.includes('mp4') ? 'm4a' : 'webm';
      const file = new File([blob], `partial-${Date.now()}.${ext}`, { type: blobType });
      await transcribeAudioFile(file, {
        partial: true,
        priorText: transcriptRef.current,
      });
      lastPartialBlobSizeRef.current = blob.size;
    } catch {
      // Partial failures are silent; final pass on stop will retry.
    } finally {
      streamInFlightRef.current = false;
      setLiveTranscribing(false);
    }
  }, [transcribeAudioFile]);

  const handleGeneratePlan = async ({ useDefaults = false } = {}) => {
    const duration = Number(editDuration);
    if (!useDefaults && (!Number.isFinite(duration) || duration < 10 || duration > 120)) {
      addToast('Interview time must be between 10 and 120 minutes.', 'error');
      return;
    }

    setGenerating(true);
    try {
      const options = useDefaults
        ? { force: true }
        : {
            force: true,
            candidateLevel: editLevel,
            totalDurationMinutes: duration,
          };
      const { data } = await generateCandidateBlueprint(candidateId, options);
      setBlueprint(data);
      syncPlanEditors(data);
      try {
        const questionsRes = await generateInterviewQuestions(candidateId, true);
        setAgent4((prev) => ({
          ...(prev || {}),
          blueprint_ready: true,
          questions_ready: true,
          speak_ready: Boolean(questionsRes.data.tts_ready),
          question_set: questionsRes.data,
        }));
        if (questionsRes.data.questions?.length) {
          setSelectedQuestionId(questionsRes.data.questions[0].id);
        }
      } catch (questionErr) {
        addToast(
          questionErr.response?.data?.detail
            || 'Plan saved, but interview questions still need to be regenerated.',
          'warning',
        );
      }
      addToast(
        useDefaults
          ? 'Interview plan regenerated with default settings and applied to this interview.'
          : 'Interview plan updated. Timing and level now apply to this interview.',
        'success',
      );
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to generate interview plan.', 'error');
    } finally {
      setGenerating(false);
    }
  };

  const handleResendInvite = async () => {
    setResending(true);
    try {
      await resendCandidateInvite(candidateId);
      addToast('Interview invite resent.', 'success');
      await Promise.all([loadAll(), refreshData({ silent: true, force: true })]);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Cannot resend invite.', 'error');
    } finally {
      setResending(false);
    }
  };

  const loadAgent5Report = async () => {
    if (!agent5?.agent5_session_id) {
      addToast('No Agent 5 session exists for this candidate yet.', 'warning');
      return;
    }
    setAgent5ReportOpen(true);
    setAgent5ReportLoading(true);
    try {
      const { data } = await getFraudAgentReport(candidateId);
      const report = data.report || null;
      setAgent5Report(report);
      if (!report) addToast(data.message || 'No proctoring report is available yet.', 'info');
    } catch (err) {
      setAgent5Report(null);
      addToast(formatApiError(err, 'Failed to load Agent 5 report.'), 'error');
    } finally {
      setAgent5ReportLoading(false);
    }
  };

  const handleGenerateQuestions = async (force = false) => {
    setGeneratingQuestions(true);
    try {
      const { data } = await generateInterviewQuestions(candidateId, force);
      setAgent4((prev) => ({
        ...(prev || {}),
        blueprint_ready: true,
        questions_ready: true,
        speak_ready: Boolean(data.tts_ready),
        question_set: data,
      }));
      if (data.questions?.length) setSelectedQuestionId(data.questions[0].id);
      addToast(
        data.tts_ready
          ? `Generated ${data.total_questions} questions — speak mode ready.`
          : `Generated ${data.total_questions} questions. Preparing speak audio…`,
        'success',
      );
      setGeneratingQuestions(false);

      // Live poll: backend commits after each clip, so count rises 1/16 → 2/16…
      if (!data.tts_ready) {
        let lastReady = data.tts_ready_count || 0;
        for (let i = 0; i < 180; i += 1) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
          try {
            const statusRes = await getInterviewAgentStatus(candidateId);
            const qs = statusRes.data?.question_set;
            setAgent4(statusRes.data);
            const ready = qs?.tts_ready_count || 0;
            if (ready > lastReady) lastReady = ready;
            if (statusRes.data?.speak_ready || qs?.tts_ready) {
              addToast('Speak mode ready — all question audio cached.', 'success');
              break;
            }
            // Stop polling if preparation clearly stalled / finished partial.
            if (qs && !qs.tts_preparing && ready > 0 && ready < (qs.total_questions || 0)) {
              break;
            }
          } catch {
            break;
          }
        }
      }
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to generate questions.', 'error');
      setGeneratingQuestions(false);
    }
  };

  const applyQuestionSet = (data) => {
    setAgent4((prev) => ({
      ...(prev || {}),
      blueprint_ready: Boolean(prev?.blueprint_ready),
      questions_ready: Boolean(data?.questions?.length),
      speak_ready: Boolean(data?.tts_ready),
      question_set: data,
    }));
    return data?.questions || [];
  };

  const liveSessionStatuses = ['IN_PROGRESS', 'AWAITING_ANSWER', 'TURN_COMPLETE', 'CANDIDATE_QNA', 'COMPLETED'];
  const planLocked = Boolean(
    blueprint?.plan_locked
    || liveSessionStatuses.includes(String(session?.status || '').toUpperCase())
    || ['AI_INTERVIEW_ACTIVE', 'HR_INTERVENTION', 'COMPLETED', 'ENDED'].includes(String(roomRuntime?.state || ''))
  );
  const questionsLocked = agent4?.question_edits?.allowed === false || planLocked;
  const questionsLockReason = agent4?.question_edits?.reason
    || 'Questions can be changed only until 10 minutes before the interview.';

  const openAddQuestion = (insertAt) => {
    if (questionsLocked) {
      addToast(questionsLockReason, 'warning');
      return;
    }
    const questions = agent4?.question_set?.questions || [];
    const maxPos = questions.length + 1;
    const position = Math.max(1, Math.min(Number(insertAt) || maxPos, maxPos));
    const selected = questions.find((q) => q.id === selectedQuestionId);
    setQuestionEditor({
      mode: 'add',
      questionId: null,
      insertAt: position,
      text: '',
      categoryId: selected?.category_id || 'skills_jd_keyword_questions',
      difficulty: 'medium',
    });
  };

  const openEditQuestion = (question) => {
    if (questionsLocked) {
      addToast(questionsLockReason, 'warning');
      return;
    }
    if (!question) return;
    setSelectedQuestionId(question.id);
    setQuestionEditor({
      mode: 'edit',
      questionId: question.id,
      insertAt: question.order || 1,
      text: question.question_text || '',
      categoryId: question.category_id || 'skills_jd_keyword_questions',
      difficulty: question.difficulty || 'medium',
    });
  };

  const handleSaveQuestion = async (event) => {
    event.preventDefault();
    if (!questionEditor || !candidateId) return;
    const text = String(questionEditor.text || '').trim();
    if (text.length < 8) {
      addToast('Enter a question of at least 8 characters.', 'error');
      return;
    }
    const category = QUESTION_CATEGORIES.find((item) => item.id === questionEditor.categoryId)
      || QUESTION_CATEGORIES[2];
    const payload = {
      question_text: text,
      insert_at: Number(questionEditor.insertAt) || 1,
      category_id: category.id,
      category_name: category.name,
      difficulty: questionEditor.difficulty || 'medium',
      prepare_tts: true,
    };
    setSavingQuestion(true);
    try {
      const { data } = questionEditor.mode === 'edit' && questionEditor.questionId
        ? await updateInterviewQuestion(candidateId, questionEditor.questionId, payload)
        : await addInterviewQuestion(candidateId, payload);
      const questions = applyQuestionSet(data);
      const placed = questions.find((q) => q.order === payload.insert_at) || questions[payload.insert_at - 1];
      if (placed?.id) setSelectedQuestionId(placed.id);
      setQuestionEditor(null);
      addToast(
        questionEditor.mode === 'edit'
          ? `Question saved at #${payload.insert_at}.`
          : `Question added at #${payload.insert_at}.`,
        'success',
      );
    } catch (err) {
      addToast(err.response?.data?.detail || 'Could not save the question.', 'error');
    } finally {
      setSavingQuestion(false);
    }
  };

  const handleDeleteQuestion = async (question) => {
    if (questionsLocked) {
      addToast(questionsLockReason, 'warning');
      return;
    }
    if (!question?.id || !candidateId) return;
    const ok = window.confirm(`Remove question ${question.order} from this interview?`);
    if (!ok) return;
    setSavingQuestion(true);
    try {
      const { data } = await deleteInterviewQuestion(candidateId, question.id);
      const questions = applyQuestionSet(data);
      if (selectedQuestionId === question.id) {
        setSelectedQuestionId(questions[0]?.id || null);
      }
      addToast('Question removed.', 'success');
    } catch (err) {
      addToast(err.response?.data?.detail || 'Could not remove the question.', 'error');
    } finally {
      setSavingQuestion(false);
    }
  };

  const handleGenerateHrReport = async (force = true) => {
    setGeneratingReport(true);
    try {
      const { data } = await generateRecommendationReport(candidateId, force);
      setAgent7({
        candidate_id: candidateId,
        llama_ready: Boolean(data.capabilities?.meta_llama),
        report_ready: true,
        latest: data,
        capabilities: data.capabilities,
      });
      addToast(
        `Agent 7 recommended ${data.report?.decision || 'HOLD'} (${Number(data.report?.overall_score || 0).toFixed(0)}).`,
        'success',
      );
    } catch (err) {
      addToast(err.response?.data?.detail || 'Could not generate the HR recommendation.', 'error');
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleTranscribe = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    await transcribeAudioFile(file);
  };

  const handleStartRecording = async () => {
    if (isRecording || transcribing) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      addToast('Microphone recording is not supported in this browser.', 'error');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      recordChunksRef.current = [];
      lastPartialBlobSizeRef.current = 0;
      setTranscript('');
      transcriptRef.current = '';

      const preferredTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
      ];
      const mimeType = preferredTypes.find((type) => MediaRecorder.isTypeSupported(type)) || '';
      recordMimeTypeRef.current = mimeType || 'audio/webm';
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordChunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        if (streamTimerRef.current) {
          clearInterval(streamTimerRef.current);
          streamTimerRef.current = null;
        }

        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;

        const blobType = recorder.mimeType || mimeType || 'audio/webm';
        const blob = new Blob(recordChunksRef.current, { type: blobType });
        recordChunksRef.current = [];

        if (!blob.size) {
          addToast('No audio captured. Try recording again.', 'error');
          return;
        }

        while (streamInFlightRef.current) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }

        setRecordPreview(URL.createObjectURL(blob));
        const ext = blobType.includes('ogg') ? 'ogg' : blobType.includes('mp4') ? 'm4a' : 'webm';
        const file = new File([blob], `answer-${Date.now()}.${ext}`, { type: blobType });
        await transcribeAudioFile(file, { priorText: transcriptRef.current });
      };

      mediaRecorderRef.current = recorder;
      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);
      recordTimerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
      streamTimerRef.current = setInterval(() => {
        void streamPartialTranscript();
      }, STREAM_INTERVAL_MS);
      addToast('Recording started — live transcription active.', 'success');
    } catch (err) {
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      addToast(
        err?.name === 'NotAllowedError'
          ? 'Microphone permission denied. Allow mic access and try again.'
          : 'Could not start recording.',
        'error',
      );
    }
  };

  const handleStopRecording = () => {
    if (!isRecording) return;
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    if (streamTimerRef.current) {
      clearInterval(streamTimerRef.current);
      streamTimerRef.current = null;
    }
    setIsRecording(false);
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const formatRecordingTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
  };

  const handleFollowups = async () => {
    const questions = agent4?.question_set?.questions || [];
    const selected =
      questions.find((q) => q.id === selectedQuestionId) || questions[0];
    if (!selected) {
      addToast('Generate questions first.', 'error');
      return;
    }
    if (!transcript.trim()) {
      addToast('Add or transcribe an answer first.', 'error');
      return;
    }
    setFollowupLoading(true);
    try {
      const { data } = await generateInterviewFollowups(candidateId, {
        question_id: selected.id,
        question_text: selected.question_text,
        candidate_answer: transcript,
        max_followups: 2,
      });
      setFollowups(data.follow_ups || []);
      addToast('Follow-up questions ready.', 'success');
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to generate follow-ups.', 'error');
    } finally {
      setFollowupLoading(false);
    }
  };

  const handleRoomControl = async (action) => {
    setRoomBusy(true);
    try {
      const { data } = await controlInterviewRoom(
        candidateId,
        action,
        action === 'join_conversation' ? 'HR has joined the conversation. The AI interviewer is paused.' : undefined,
      );
      setRoomRuntime(data);
      addToast(
        action === 'join_conversation'
          ? 'AI paused. Candidate can hear that HR has joined.'
          : 'Returned control to the AI interviewer.',
        'success',
      );
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to update interview room.', 'error');
    } finally {
      setRoomBusy(false);
    }
  };

  const handleStartSession = async () => {
    setSessionBusy(true);
    try {
      const { data } = await startInterviewSession(candidateId, false);
      setSession(data);
      if (data.current_question?.id) setSelectedQuestionId(data.current_question.id);
      addToast('LangGraph interview session started.', 'success');
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to start session.', 'error');
    } finally {
      setSessionBusy(false);
    }
  };

  const handleSubmitSessionAnswer = async () => {
    if (!transcript.trim()) {
      addToast('Provide an answer transcript first.', 'error');
      return;
    }
    setSessionBusy(true);
    try {
      const { data } = await submitInterviewSessionAnswer(candidateId, transcript.trim());
      setSession(data);
      setFollowups(data.follow_ups || []);
      setTranscript('');
      if (data.current_question?.id) setSelectedQuestionId(data.current_question.id);
      if (data.latest_evaluation) {
        setEvaluations((prev) => [
          {
            id: `live-${Date.now()}`,
            score: data.latest_evaluation.score,
            verdict: data.latest_evaluation.verdict,
            evaluation: data.latest_evaluation,
            question_text: data.turn_history?.at?.(-1)?.question?.question_text,
            created_at: new Date().toISOString(),
          },
          ...prev,
        ]);
        setAgent6((prev) => ({
          ...(prev || {}),
          latest: data.latest_evaluation,
          evaluations_count: (prev?.evaluations_count || 0) + 1,
        }));
      }
      addToast(
        data.status === 'COMPLETED'
          ? 'Interview session completed.'
          : 'Agent 6 evaluated; Agent 4 prepared the next turn.',
        'success',
      );
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to submit answer.', 'error');
    } finally {
      setSessionBusy(false);
    }
  };

  const handleSpeakQuestion = async () => {
    const selected =
      session?.current_question ||
      agent4?.question_set?.questions?.find((q) => q.id === selectedQuestionId) ||
      agent4?.question_set?.questions?.[0];
    const questionId = selected?.id;
    const text = selected?.question_text;
    if (!questionId && !text) {
      addToast('No question text to speak.', 'error');
      return;
    }
    setSpeaking(true);
    try {
      const { data, headers } = await speakInterviewText(candidateId, {
        questionId,
        text,
      });
      const url = URL.createObjectURL(data);
      const audio = new Audio(url);
      await audio.play();
      audio.onended = () => URL.revokeObjectURL(url);
      const cached = String(headers?.['x-tts-cached'] || '') === '1';
      addToast(
        cached ? 'Playing cached TTS audio.' : 'Playing live TTS.',
        'success',
      );
    } catch (err) {
      addToast(err.response?.data?.detail || 'TTS failed.', 'error');
    } finally {
      setSpeaking(false);
    }
  };

  if (loading) {
    return <LoadingSpinner message="Loading agents dashboard..." />;
  }

  if (error || !candidate) {
    return (
      <div className="max-w-3xl mx-auto py-16">
        <EmptyState
          icon={AlertCircle}
          title="Candidate not found"
          description={error || 'This candidate could not be loaded.'}
          action={
            <button type="button" onClick={() => navigate('/candidates')} className="btn-primary px-4 py-2 text-sm">
              Back to candidates
            </button>
          }
        />
      </div>
    );
  }

  const hasScreening = Boolean(candidate.evaluationSnapshot) || candidate.matchScore > 0;
  const hasSchedule = Boolean(candidate.scheduledDate || candidate.meetingLink || candidate.interviewScheduled);
  const agent5Status = agent5CardStatus(agent5, candidate.joinLink, agent5Loading);
  const agent5Closed = ['terminated', 'completed'].includes(
    String(agent5?.session_status || agent5?.verification_status || '').toLowerCase(),
  );
  const interviewerJoinLink = toInterviewerJoinLink(candidate?.joinLink);
  const plan = blueprint?.blueprint;
  const report = plan?.human_readable_report;
  const difficulty = plan?.difficulty_distribution;
  const pipeline = [
    { n: 1, label: 'Screening', ready: hasScreening },
    { n: 2, label: 'Scheduler', ready: hasSchedule },
    { n: 3, label: 'Planning', ready: Boolean(plan) },
    { n: 4, label: 'Interview', ready: Boolean(agent4?.questions_ready) },
    { n: 5, label: 'Proctoring', ready: Boolean(agent5?.agent5_session_id) },
    { n: 6, label: 'Evaluation', ready: evaluations.length > 0 },
    { n: 7, label: 'HR report', ready: Boolean(agent7?.latest?.report) },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <div className="flex items-center gap-3 shrink-0">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="w-9 h-9 rounded-xl border border-col flex items-center justify-center text-muted hover:text-col hover:bg-slate-50 dark:hover:bg-slate-800"
          aria-label="Go back"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted">
            <Link to="/candidates" className="hover:text-blue-500">
              Candidates
            </Link>
            <span className="mx-1.5">/</span>
            Agents dashboard
          </p>
          <h2 className="text-xl font-bold text-col truncate">{candidate.name}</h2>
        </div>
        <button
          type="button"
          onClick={loadAll}
          className="btn-secondary flex items-center gap-2 px-3 py-2 text-sm"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      <div className="card px-4 py-3.5 shrink-0">
        <div className="flex flex-col lg:flex-row lg:items-center gap-3">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0"
              style={{ background: candidate.avatarColor }}
            >
              {candidate.avatar}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-bold text-col truncate">{candidate.name}</h3>
                <StatusBadge status={candidate.status} />
              </div>
              <p className="text-xs text-muted truncate mt-0.5">
                {candidate.appliedJob}
                {candidate.experience ? ` · ${candidate.experience}` : ''}
              </p>
              <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-muted">
                {candidate.email ? (
                  <a href={`mailto:${candidate.email}`} className="inline-flex items-center gap-1 hover:text-blue-500">
                    <Mail size={12} />
                    {candidate.email}
                  </a>
                ) : null}
                {candidate.phone && candidate.phone !== '—' ? (
                  <span className="inline-flex items-center gap-1">
                    <Phone size={12} />
                    {candidate.phone}
                  </span>
                ) : null}
                {candidate.resumeFileUrl ? (
                  <a
                    href={getScreeningFileUrl(candidate.resumeFileUrl)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    <FileText size={12} />
                    {candidate.resumeOriginalFilename || 'Resume'}
                  </a>
                ) : null}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <MatchScore score={candidate.matchScore || 0} size="lg" />
            {candidate.recommendation ? (
              <RecommendationBadge recommendation={candidate.recommendation} />
            ) : null}
          </div>
        </div>
      </div>

      <div className="card px-2 py-2">
        <div className="flex items-center gap-1 overflow-x-auto">
          {pipeline.map((step, index) => (
            <div key={step.n} className="flex items-center flex-1 min-w-0">
              <button
                type="button"
                onClick={() => setActiveAgent(step.n)}
                aria-pressed={activeAgent === step.n}
                className={`flex items-center gap-2 min-w-0 w-full px-2.5 py-2 rounded-xl text-left transition-colors ${
                  activeAgent === step.n
                    ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-sm'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <span
                  className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${
                    activeAgent === step.n
                      ? 'bg-white/20 text-current'
                      : step.ready
                        ? 'bg-emerald-500 text-white'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                  }`}
                >
                  {step.n}
                </span>
                <span className={`text-xs font-semibold truncate ${activeAgent === step.n ? '' : 'text-col'}`}>
                  {step.label}
                </span>
              </button>
              {index < pipeline.length - 1 ? (
                <div className="hidden sm:block w-4 h-px mx-0.5 bg-[var(--color-border)] shrink-0" />
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <section>
        {activeAgent === 1 && (
        <AgentCard
          agent="Agent 1 · Screening"
          title="Match & evaluation"
          subtitle="ATS score, skills, and recommendation"
          status={hasScreening ? 'Ready' : 'No output'}
          statusTone={hasScreening ? 'ready' : 'missing'}
        >
          {hasScreening ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 p-3">
                  <p className="text-[11px] text-muted uppercase tracking-wider">Match score</p>
                  <p className="text-2xl font-bold text-col mt-1">{candidate.matchScore}%</p>
                </div>
                <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 p-3">
                  <p className="text-[11px] text-muted uppercase tracking-wider">Required skills</p>
                  <p className="text-2xl font-bold text-col mt-1">
                    {candidate.requiredMatchRatio != null ? `${candidate.requiredMatchRatio}%` : '—'}
                  </p>
                </div>
              </div>
              {candidate.summary ? (
                <p className="text-sm text-col leading-relaxed">{candidate.summary}</p>
              ) : null}
              <EvaluationDetailPanels data={candidate} />
            </>
          ) : (
            <p className="text-sm text-muted">No screening evaluation is stored for this candidate yet.</p>
          )}
        </AgentCard>
        )}

        {activeAgent === 2 && (
        <AgentCard
          agent="Agent 2 · Scheduler"
          title="Interview scheduling"
          subtitle="Invite status, slot, and in-app interview room"
          status={hasSchedule ? 'Scheduled' : candidate.canResendInvite ? 'Invite pending' : 'Not scheduled'}
          statusTone={hasSchedule ? 'ready' : candidate.canResendInvite ? 'pending' : 'missing'}
          actions={
            candidate.canResendInvite ? (
              <button
                type="button"
                onClick={handleResendInvite}
                disabled={resending}
                className="btn-secondary flex items-center gap-2 px-3 py-2 text-sm disabled:opacity-60"
              >
                {resending ? <Loader2 size={14} className="animate-spin" /> : <Mail size={14} />}
                Resend invite
              </button>
            ) : null
          }
        >
          {hasSchedule ? (
            <div className="space-y-4">
              <MetaRow icon={CalendarDays} label="Date" value={formatDateLabel(candidate.scheduledDate)} />
              <MetaRow icon={Clock} label="Time" value={formatTimeLabel(candidate.scheduledTime)} />
              {candidate.joinLink && !agent5Closed ? (
                <>
                  <MetaRow
                    icon={Link2}
                    label="Candidate interview URL"
                    value={candidate.joinLink}
                    href={candidate.joinLink}
                  />
                  {interviewerJoinLink ? (
                    <MetaRow
                      icon={Video}
                      label="HR / Admin join link (skip checks → room)"
                      value={interviewerJoinLink}
                      href={interviewerJoinLink}
                    />
                  ) : null}
                </>
              ) : agent5Closed ? (
                <p className="text-sm text-muted">
                  The interview session is {agent5Status.label.toLowerCase()}. The candidate join link is no longer active.
                </p>
              ) : null}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted">
                {candidate.backendStatus === 'SHORTLISTED' || candidate.canResendInvite
                  ? 'Invite sent — waiting for the candidate to pick a slot.'
                  : 'No interview has been scheduled for this candidate yet.'}
              </p>
              {candidate.canResendInvite ? (
                <p className="text-xs text-muted">Use Resend invite if the scheduling email was missed.</p>
              ) : null}
            </div>
          )}
        </AgentCard>
        )}

        {activeAgent === 3 && (
        <AgentCard
          agent="Agent 3 · Planning"
          title="Interview blueprint"
          subtitle="Level, question plan, and flow"
          status={plan ? 'Ready' : blueprintLoading ? 'Loading' : 'Missing'}
          statusTone={plan ? 'ready' : blueprintLoading ? 'pending' : 'missing'}
        >
          {blueprintLoading ? (
            <p className="text-sm text-muted flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" />
              Loading blueprint…
            </p>
          ) : (
            <div className="space-y-5">
              <div className="rounded-2xl border border-col overflow-hidden">
                <div className="px-4 py-3 bg-gradient-to-r from-orange-50 to-slate-50 dark:from-orange-950/25 dark:to-slate-900/40 border-b border-col flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-white/90 dark:bg-slate-900/60 border border-col flex items-center justify-center text-orange-600 dark:text-orange-300">
                    <SlidersHorizontal size={14} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-col">Adjust plan</p>
                    <p className="text-[11px] text-muted">
                      {planLocked
                        ? 'Locked after the interview starts. HR and Admin can edit only before start.'
                        : 'HR and Admin can change level or duration for this interview before it starts'}
                    </p>
                  </div>
                </div>

                <div className="p-4 space-y-4 bg-white dark:bg-slate-900/20">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted mb-2">Level</p>
                    <div className="flex flex-wrap gap-1.5">
                      {CANDIDATE_LEVELS.map((level) => {
                        const active = editLevel === level;
                        return (
                          <button
                            key={level}
                            type="button"
                            onClick={() => !planLocked && setEditLevel(level)}
                            disabled={planLocked}
                            className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                              active
                                ? 'bg-orange-500 border-orange-500 text-white shadow-sm'
                                : 'border-col text-muted hover:text-col hover:bg-slate-50 dark:hover:bg-slate-800'
                            } ${planLocked ? 'opacity-60 cursor-not-allowed' : ''}`}
                          >
                            {level}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
                        Interview length
                      </p>
                      <span className="text-sm font-semibold text-col tabular-nums">
                        {editDuration}
                        <span className="text-xs font-medium text-muted ml-1">min</span>
                      </span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={120}
                      step={5}
                      value={editDuration}
                      disabled={planLocked}
                      onChange={(e) => setEditDuration(Number(e.target.value))}
                      className={`w-full accent-orange-500 h-1.5 ${planLocked ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                    />
                    <div className="flex justify-between text-[10px] text-muted mt-1.5">
                      <span>10 min</span>
                      <span>Default {defaultDuration} min (Interview hours)</span>
                      <span>120 min</span>
                    </div>
                    <p className="text-[11px] text-muted mt-2 leading-relaxed">
                      Default length comes from Settings → Interview hours. Change it here only for this candidate, then Apply changes. Use defaults to restore the company slot length.
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => handleGeneratePlan({ useDefaults: false })}
                      disabled={generating || !hasScreening || planLocked}
                      className="btn-primary flex items-center gap-2 px-3.5 py-2 text-sm disabled:opacity-60"
                    >
                      {generating ? <Loader2 size={14} className="animate-spin" /> : plan ? <RefreshCw size={14} /> : <Sparkles size={14} />}
                      {plan ? 'Apply changes' : 'Generate plan'}
                    </button>
                    {plan ? (
                      <button
                        type="button"
                        onClick={() => handleGeneratePlan({ useDefaults: true })}
                        disabled={generating || planLocked}
                        className="btn-secondary flex items-center gap-2 px-3.5 py-2 text-sm disabled:opacity-60"
                      >
                        {generating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                        Use defaults
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>

              {!plan ? (
                <div className="rounded-xl border border-dashed border-col px-4 py-5 text-center">
                  <Bot size={20} className="mx-auto text-muted mb-2" />
                  <p className="text-sm text-col font-medium">No blueprint yet</p>
                  <p className="text-xs text-muted mt-1 max-w-[240px] mx-auto">
                    Set level and length above, then generate a plan for this candidate.
                  </p>
                  {!hasScreening ? (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-3">
                      Screening output is required first.
                    </p>
                  ) : null}
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 px-3 py-3 text-center">
                      <p className="text-[10px] text-muted uppercase tracking-wider font-semibold">Level</p>
                      <p className="text-sm font-semibold text-col mt-1 truncate">
                        {blueprint.candidate_level || plan.candidate_level}
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 px-3 py-3 text-center">
                      <p className="text-[10px] text-muted uppercase tracking-wider font-semibold">Questions</p>
                      <p className="text-sm font-semibold text-col mt-1">
                        {blueprint.total_questions ?? plan.total_questions}
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-800/40 px-3 py-3 text-center">
                      <p className="text-[10px] text-muted uppercase tracking-wider font-semibold">Duration</p>
                      <p className="text-sm font-semibold text-col mt-1">
                        {plan.time_allocation?.total_duration_minutes ?? '—'}
                        <span className="text-[11px] font-medium text-muted ml-0.5">min</span>
                      </p>
                    </div>
                  </div>

                  {difficulty ? (
                    <div>
                      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-2">Difficulty</p>
                      <div className="grid grid-cols-3 gap-2">
                        {[
                          ['Easy', difficulty.easy, 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300'],
                          ['Medium', difficulty.medium, 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300'],
                          ['Hard', difficulty.hard, 'bg-rose-50 text-rose-700 dark:bg-rose-900/20 dark:text-rose-300'],
                        ].map(([label, value, tone]) => (
                          <div key={label} className={`rounded-xl px-3 py-2.5 text-center ${tone}`}>
                            <p className="text-[10px] uppercase tracking-wider font-semibold opacity-80">{label}</p>
                            <p className="text-base font-bold mt-0.5">{value ?? 0}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {Array.isArray(plan.category_breakdown) && plan.category_breakdown.length > 0 ? (
                    <div>
                      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-2">Categories</p>
                      <ul className="divide-y divide-[var(--color-border)] rounded-xl border border-col overflow-hidden">
                        {plan.category_breakdown.map((cat) => (
                          <li
                            key={cat.category_id || cat.category_name}
                            className="flex items-center justify-between gap-3 px-3.5 py-2.5 text-sm bg-white/50 dark:bg-slate-900/20"
                          >
                            <span className="text-col truncate">{cat.category_name}</span>
                            <span className="text-muted shrink-0 text-xs font-medium tabular-nums">
                              {cat.question_count}q · {cat.estimated_minutes || 0}m
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {report?.summary ? (
                    <div className="rounded-xl bg-slate-50 dark:bg-slate-800/30 px-3.5 py-3">
                      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-1.5">Summary</p>
                      <p className="text-sm text-col leading-relaxed">{report.summary}</p>
                    </div>
                  ) : null}

                  {Array.isArray(report?.interviewer_notes) && report.interviewer_notes.length > 0 ? (
                    <div>
                      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-2">Interviewer notes</p>
                      <ul className="space-y-2">
                        {report.interviewer_notes.slice(0, 5).map((note) => (
                          <li key={note} className="text-sm text-col flex items-start gap-2">
                            <CheckCircle2 size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                            <span>{note}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {Array.isArray(plan.interview_flow) && plan.interview_flow.length > 0 ? (
                    <div>
                      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-2">Interview flow</p>
                      <ol className="space-y-2">
                        {plan.interview_flow.map((step) => (
                          <li
                            key={`${step.step_order}-${step.stage_name}`}
                            className="flex gap-3 rounded-xl border border-col px-3 py-2.5"
                          >
                            <span className="w-6 h-6 rounded-lg bg-orange-500 text-white text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                              {step.step_order}
                            </span>
                            <div className="min-w-0">
                              <p className="font-medium text-col text-sm">{step.stage_name}</p>
                              <p className="text-xs text-muted mt-0.5">
                                {step.question_count} questions · {step.estimated_minutes} min
                              </p>
                            </div>
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          )}
        </AgentCard>
        )}

        {activeAgent === 4 && (
          <AgentCard
            agent="Agent 4 · Interview"
            title="Live AI interviewer"
            subtitle="Meta Llama · Whisper STT · Edge/Parler TTS · Agent 6 feedback loop"
            status={
              agent4Loading
                ? 'Loading'
                : agent4?.questions_ready
                  ? 'Ready'
                  : agent4?.blueprint_ready
                    ? 'Awaiting questions'
                    : 'Needs blueprint'
            }
            statusTone={
              agent4?.questions_ready
                ? 'ready'
                : agent4?.blueprint_ready
                  ? 'pending'
                  : 'missing'
            }
          >
            {agent4Loading ? (
              <p className="text-sm text-muted flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Loading interview agent…
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    {
                      icon: Bot,
                      label: 'Meta Llama',
                      ok: Boolean(agent4?.capabilities?.meta_llama),
                    },
                    {
                      icon: Mic,
                      label: 'Whisper STT',
                      ok: Boolean(agent4?.capabilities?.whisper_stt),
                    },
                    {
                      icon: Volume2,
                      label: 'TTS',
                      ok: Boolean(agent4?.capabilities?.tts),
                    },
                    {
                      icon: Gauge,
                      label: 'Agent 6 loop',
                      ok: Boolean(agent4?.capabilities?.agent6_parallel),
                    },
                  ].map(({ icon: Icon, label, ok }) => (
                    <div
                      key={label}
                      className={`rounded-xl px-2.5 py-3 text-center border ${
                        ok
                          ? 'border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/40 dark:bg-emerald-900/20'
                          : 'border-col bg-slate-50 dark:bg-slate-800/40'
                      }`}
                    >
                      <Icon
                        size={16}
                        className={`mx-auto mb-1 ${ok ? 'text-emerald-600' : 'text-muted'}`}
                      />
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                        {label}
                      </p>
                      <p className="text-[11px] font-medium text-col mt-0.5">
                        {ok ? 'Enabled' : 'Setup needed'}
                      </p>
                    </div>
                  ))}
                </div>

                {agent4?.capabilities?.llama_model ? (
                  <p className="text-[11px] text-muted">
                    Llama: {agent4.capabilities.llama_model} · STT:{' '}
                    {agent4.capabilities.stt_model || 'whisper-large-v3'} · TTS:{' '}
                    {agent4.capabilities.tts_model || 'en-IN-NeerjaNeural'}
                    {agent4?.question_set
                      ? ` · Audio ${agent4.question_set.tts_ready_count || 0}/${
                          agent4.question_set.total_questions || 0
                        } cached`
                      : ''}
                  </p>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => handleGenerateQuestions(Boolean(agent4?.questions_ready))}
                    disabled={
                      generatingQuestions
                      || !agent4?.blueprint_ready
                      || (questionsLocked && Boolean(agent4?.questions_ready))
                    }
                    className="btn-primary flex items-center gap-2 px-3.5 py-2 text-sm disabled:opacity-60"
                  >
                    {generatingQuestions ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Sparkles size={14} />
                    )}
                    {agent4?.questions_ready ? 'Regenerate questions' : 'Generate questions'}
                  </button>
                  <button
                    type="button"
                    onClick={() => openAddQuestion((agent4?.question_set?.questions?.length || 0) + 1)}
                    disabled={savingQuestion || questionsLocked}
                    className="btn-secondary flex items-center gap-2 px-3.5 py-2 text-sm disabled:opacity-60"
                  >
                    <Plus size={14} />
                    Add question
                  </button>
                  {showInterviewLab ? (
                    <button
                      type="button"
                      onClick={handleStartSession}
                      disabled={sessionBusy || !agent4?.blueprint_ready}
                      className="btn-secondary flex items-center gap-2 px-3.5 py-2 text-sm disabled:opacity-60"
                    >
                      {sessionBusy ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
                      Start LangGraph session
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={handleSpeakQuestion}
                    disabled={speaking}
                    className="btn-secondary flex items-center gap-2 px-3.5 py-2 text-sm disabled:opacity-60"
                  >
                    {speaking ? <Loader2 size={14} className="animate-spin" /> : <Volume2 size={14} />}
                    {agent4?.speak_ready || agent4?.question_set?.tts_ready
                      ? 'Speak (cached)'
                      : 'Speak question'}
                  </button>
                  {agent4?.question_set?.tts_preparing ? (
                    <p className="text-xs text-amber-600 dark:text-amber-400 self-center">
                      Preparing speak audio… {agent4.question_set.tts_ready_count || 0}/
                      {agent4.question_set.total_questions || 0}
                    </p>
                  ) : null}
                  {!agent4?.blueprint_ready ? (
                    <p className="text-xs text-amber-600 dark:text-amber-400 self-center">
                      Generate Agent 3 blueprint first.
                    </p>
                  ) : null}
                </div>
                {questionsLocked ? (
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    {questionsLockReason}
                  </p>
                ) : null}

                {showInterviewLab && session ? (
                  <div className="rounded-xl border border-col px-3.5 py-3 space-y-2 bg-slate-50/80 dark:bg-slate-800/30">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold">
                        LangGraph session
                      </p>
                      <span className="text-[11px] font-semibold text-col">{session.status}</span>
                    </div>
                    {session.current_question ? (
                      <p className="text-sm text-col leading-relaxed">
                        Q{session.current_index + 1}: {session.current_question.question_text}
                      </p>
                    ) : (
                      <p className="text-xs text-muted">
                        {session.status === 'COMPLETED'
                          ? 'All questions completed.'
                          : 'Waiting for next turn.'}
                      </p>
                    )}
                    {session.agent6_feedback ? (
                      <p className="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">
                        Agent 6 → Agent 4: {session.agent6_feedback}
                      </p>
                    ) : null}
                    {session.latest_evaluation ? (
                      <p className="text-[11px] text-muted">
                        Last score {Number(session.latest_evaluation.score || 0).toFixed(0)} ·{' '}
                        {session.latest_evaluation.verdict}
                      </p>
                    ) : null}
                    <p className="text-[11px] text-muted">
                      {session.remaining_questions} remaining · checkpoint{' '}
                      {agent4?.capabilities?.checkpointer || '—'}
                    </p>
                    {session.status === 'AWAITING_ANSWER' ? (
                      <button
                        type="button"
                        onClick={handleSubmitSessionAnswer}
                        disabled={sessionBusy || !transcript.trim()}
                        className="btn-primary flex items-center gap-2 px-3 py-2 text-sm disabled:opacity-60"
                      >
                        {sessionBusy ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <MessageSquarePlus size={14} />
                        )}
                        Submit answer (Agent 4 ∥ Agent 6)
                      </button>
                    ) : null}
                  </div>
                ) : null}

                {agent4?.question_set?.questions?.length ? (
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <p className="text-[11px] uppercase tracking-wider text-muted font-semibold">
                        Question bank ({agent4.question_set.total_questions})
                      </p>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-muted">
                          {agent4.question_set.candidate_level || '—'}
                          {agent4.question_set.total_duration_minutes
                            ? ` · ${agent4.question_set.total_duration_minutes}m`
                            : ''}
                        </span>
                        <button
                          type="button"
                          onClick={() => openAddQuestion((agent4.question_set.questions?.length || 0) + 1)}
                          disabled={questionsLocked}
                          className="text-[11px] font-semibold text-orange-600 dark:text-orange-400 inline-flex items-center gap-1 disabled:opacity-40 disabled:pointer-events-none"
                        >
                          <Plus size={12} />
                          Add
                        </button>
                      </div>
                    </div>
                    <ul className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                      {agent4.question_set.questions.map((q, index) => (
                        <li key={q.id} className="space-y-1">
                          {index === 0 && !questionsLocked ? (
                            <button
                              type="button"
                              onClick={() => openAddQuestion(1)}
                              className="w-full text-[10px] font-medium text-muted hover:text-orange-600 py-0.5"
                            >
                              + Insert at #1
                            </button>
                          ) : null}
                          <div
                            className={`rounded-xl border px-3 py-2.5 transition-colors ${
                              selectedQuestionId === q.id
                                ? 'border-orange-400 bg-orange-50/80 dark:bg-orange-950/20'
                                : 'border-col hover:bg-slate-50 dark:hover:bg-slate-800/40'
                            }`}
                          >
                            <button
                              type="button"
                              onClick={() => setSelectedQuestionId(q.id)}
                              className="w-full text-left"
                            >
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted truncate">
                                  {q.order}. {q.category_name}
                                </span>
                                <span className="text-[10px] font-medium text-muted capitalize shrink-0 flex items-center gap-1.5">
                                  {q.audio_ready ? (
                                    <span className="text-emerald-600 dark:text-emerald-400">Audio</span>
                                  ) : null}
                                  {q.difficulty}
                                </span>
                              </div>
                              <p className="text-xs text-col leading-relaxed line-clamp-2">
                                {q.question_text}
                              </p>
                            </button>
                            {!questionsLocked ? (
                            <div className="flex items-center justify-end gap-1 mt-1.5">
                              <button
                                type="button"
                                onClick={() => openAddQuestion(q.order + 1)}
                                className="p-1 rounded-md text-muted hover:text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950/30"
                                title={`Insert after #${q.order}`}
                              >
                                <Plus size={13} />
                              </button>
                              <button
                                type="button"
                                onClick={() => openEditQuestion(q)}
                                className="p-1 rounded-md text-muted hover:text-col hover:bg-slate-100 dark:hover:bg-slate-800"
                                title="Edit question"
                              >
                                <Pencil size={13} />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteQuestion(q)}
                                disabled={savingQuestion}
                                className="p-1 rounded-md text-muted hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 disabled:opacity-50"
                                title="Remove question"
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                            ) : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-col px-4 py-5 text-center">
                    <Bot size={18} className="mx-auto text-muted mb-2" />
                    <p className="text-sm text-col font-medium">
                      {generatingQuestions ? 'Generating interview questions…' : 'No live questions yet'}
                    </p>
                    <p className="text-xs text-muted mt-1">
                      {generatingQuestions
                        ? 'Agent 4 is building questions from the Agent 3 plan. This runs automatically.'
                        : 'Questions generate automatically after the Agent 3 plan is ready, or add one now at any number.'}
                    </p>
                    <button
                      type="button"
                      onClick={() => openAddQuestion(1)}
                      disabled={questionsLocked}
                      className="btn-secondary mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs disabled:opacity-50"
                    >
                      <Plus size={12} />
                      Add question
                    </button>
                  </div>
                )}

                {showInterviewLab ? (
                <div className="rounded-2xl border border-col overflow-hidden">
                  <div className="px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800/40 border-b border-col flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <Mic size={14} className="text-orange-500 shrink-0" />
                      <p className="text-xs font-semibold text-col truncate">
                        Whisper STT — live while speaking
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {!isRecording ? (
                        <button
                          type="button"
                          onClick={handleStartRecording}
                          disabled={transcribing}
                          className="btn-secondary px-2.5 py-1 text-[11px] inline-flex items-center gap-1.5 disabled:opacity-60"
                        >
                          {transcribing ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Mic size={12} />
                          )}
                          Record
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={handleStopRecording}
                          className="px-2.5 py-1 text-[11px] inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300"
                        >
                          <Square size={12} className="fill-current" />
                          Stop {formatRecordingTime(recordingSeconds)}
                        </button>
                      )}
                      <label className="btn-secondary px-2.5 py-1 text-[11px] cursor-pointer inline-flex items-center gap-1.5">
                        {transcribing ? <Loader2 size={12} className="animate-spin" /> : <Mic size={12} />}
                        Upload
                        <input
                          type="file"
                          accept="audio/*,.wav,.mp3,.m4a,.webm,.ogg,.flac"
                          className="hidden"
                          onChange={handleTranscribe}
                          disabled={transcribing || isRecording}
                        />
                      </label>
                    </div>
                  </div>
                  <div className="p-3 space-y-2.5">
                    {isRecording ? (
                      <div className="rounded-xl border border-red-200 bg-red-50/70 dark:border-red-900/40 dark:bg-red-950/20 px-3 py-2 flex items-center gap-2">
                        <span className="relative flex h-2.5 w-2.5 shrink-0">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
                        </span>
                        <p className="text-xs text-red-700 dark:text-red-300 font-medium min-w-0">
                          Listening & transcribing live… {formatRecordingTime(recordingSeconds)}
                          {liveTranscribing ? (
                            <Loader2 size={12} className="inline ml-1.5 animate-spin align-[-2px]" />
                          ) : null}
                        </p>
                      </div>
                    ) : null}
                    {recordPreviewUrl && !isRecording ? (
                      <audio controls src={recordPreviewUrl} className="w-full h-9" />
                    ) : null}
                    <textarea
                      value={transcript}
                      onChange={(e) => setTranscript(e.target.value)}
                      rows={3}
                      readOnly={isRecording}
                      placeholder={
                        isRecording
                          ? 'Live transcript appears here as you speak…'
                          : 'Candidate answer transcript (record, upload audio, or paste text)…'
                      }
                      className={`w-full rounded-xl border border-col bg-white dark:bg-slate-900 px-3 py-2 text-sm text-col placeholder:text-muted resize-none ${
                        isRecording ? 'opacity-90 cursor-default' : ''
                      }`}
                    />
                    <button
                      type="button"
                      onClick={handleFollowups}
                      disabled={followupLoading || !agent4?.questions_ready}
                      className="btn-secondary flex items-center gap-2 px-3 py-2 text-sm disabled:opacity-60"
                    >
                      {followupLoading ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <MessageSquarePlus size={14} />
                      )}
                      Generate follow-ups
                    </button>
                    {followups.length > 0 ? (
                      <ul className="space-y-2">
                        {followups.map((fu) => (
                          <li
                            key={fu.id}
                            className="rounded-xl bg-slate-50 dark:bg-slate-800/40 px-3 py-2.5"
                          >
                            <p className="text-[10px] uppercase tracking-wider text-muted font-semibold mb-1">
                              Follow-up · {fu.difficulty}
                            </p>
                            <p className="text-sm text-col leading-relaxed">{fu.question_text}</p>
                            {fu.reason ? (
                              <p className="text-[11px] text-muted mt-1">{fu.reason}</p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </div>
                ) : null}
              </div>
            )}
          </AgentCard>
        )}

        {activeAgent === 5 && (
          <AgentCard
            agent="Agent 5 · Fraud Detection"
            title="Live proctoring gate"
            subtitle="Candidate verifies identity, then the AI interview runs in our room"
            status={agent5Status.label}
            statusTone={agent5Status.tone}
            actions={
              <button
                type="button"
                onClick={loadAgent5Report}
                disabled={agent5ReportLoading || !agent5?.agent5_session_id}
                className="btn-secondary flex items-center gap-2 px-3 py-2 text-sm disabled:opacity-60"
              >
                {agent5ReportLoading ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Shield size={14} />
                )}
                Open report
              </button>
            }
          >
            {agent5Loading ? (
              <p className="text-sm text-muted flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Checking Agent 5…
              </p>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-muted">
                  Use the candidate link for full device + photo + voice verification. Use the HR / Admin join link to open the interview room directly (checks skipped). Both HR and Admin portal users can use that link.
                </p>
                {candidate?.joinLink && !agent5Closed ? (
                  <>
                    <MetaRow
                      icon={Link2}
                      label="Candidate join link"
                      value={candidate.joinLink}
                      href={candidate.joinLink}
                    />
                    {interviewerJoinLink ? (
                      <MetaRow
                        icon={Video}
                        label="HR / Admin join link"
                        value={interviewerJoinLink}
                        href={interviewerJoinLink}
                      />
                    ) : null}
                  </>
                ) : agent5Closed ? (
                  <p className="text-sm text-muted">
                    This session is {agent5Status.label.toLowerCase()} and cannot be reopened from the join link.
                  </p>
                ) : null}
                {agent5?.agent5_session_id ? (
                  <>
                    <MetaRow
                      icon={Shield}
                      label="Verification status"
                      value={agent5.verification_status || agent5.session_status || 'created'}
                    />
                    <MetaRow
                      icon={Shield}
                      label="Risk score"
                      value={
                        agent5.risk_score != null
                          ? `${Math.round(agent5.risk_score)} (${agent5.risk_classification || 'low'})`
                          : '—'
                      }
                    />
                    <p className="text-xs text-muted">
                      Open report shows identity checks, risk, voice attempts, and the event timeline for this session.
                    </p>
                  </>
                ) : (
                  <p className="text-xs text-muted">
                    Agent5 session is created automatically when the candidate opens the join link.
                  </p>
                )}
                {roomRuntime ? (
                  <div className="rounded-xl border border-col p-4 space-y-3">
                    <p className="text-sm text-col"><strong>Room state:</strong> {roomRuntime.state}</p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-secondary px-3 py-2 text-sm disabled:opacity-60"
                        disabled={roomBusy || roomRuntime.hr_speaking}
                        onClick={() => void handleRoomControl('join_conversation')}
                      >
                        Join conversation
                      </button>
                      <button
                        type="button"
                        className="btn-secondary px-3 py-2 text-sm disabled:opacity-60"
                        disabled={roomBusy || !roomRuntime.hr_speaking}
                        onClick={() => void handleRoomControl('return_to_ai')}
                      >
                        Return to AI
                      </button>
                    </div>
                    <p className="text-xs text-muted">
                      Watch the live Agent 4/6 session on this dashboard. Join conversation pauses the AI interviewer. Browser JavaScript cannot lock the OS; a kiosk browser or dedicated desktop app is required for a fully locked exam environment.
                    </p>
                  </div>
                ) : null}
              </div>
            )}
          </AgentCard>
        )}

        {activeAgent === 6 && (
          <AgentCard
            agent="Agent 6 · Evaluation"
            title="Answer evaluation"
            subtitle="Meta Llama · resume · JD · web research → feedback to Agent 4"
            status={
              agent6Loading
                ? 'Loading'
                : agent6?.report?.questions_total
                  ? `${agent6.report.questions_answered || 0}/${agent6.report.questions_total}`
                  : agent6?.llama_ready
                    ? evaluations.length
                      ? 'Evaluating'
                      : 'Ready'
                    : 'Needs GROQ key'
            }
            statusTone={
              agent6?.llama_ready ? (evaluations.length ? 'ready' : 'pending') : 'missing'
            }
          >
            {agent6Loading ? (
              <p className="text-sm text-muted flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Loading evaluation agent…
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: 'Meta Llama', ok: Boolean(agent6?.capabilities?.meta_llama) },
                    { label: 'Resume + JD', ok: Boolean(agent6?.capabilities?.resume_jd_context) },
                    { label: 'Web research', ok: Boolean(agent6?.capabilities?.web_research) },
                    { label: 'Chroma memory', ok: Boolean(agent6?.capabilities?.chroma_memory) },
                    {
                      label: 'Parallel w/ A4',
                      ok: Boolean(agent6?.capabilities?.parallel_with_agent4),
                    },
                  ].map(({ label, ok }) => (
                    <div
                      key={label}
                      className={`rounded-xl px-3 py-2.5 border text-center ${
                        ok
                          ? 'border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/40 dark:bg-emerald-900/20'
                          : 'border-col bg-slate-50 dark:bg-slate-800/40'
                      }`}
                    >
                      <p className="text-[10px] uppercase tracking-wider text-muted font-semibold">
                        {label}
                      </p>
                      <p className="text-xs font-medium text-col mt-0.5">
                        {ok ? 'On' : 'Off'}
                      </p>
                    </div>
                  ))}
                </div>

                <p className="text-xs text-muted leading-relaxed">
                  Agent 6 scores every MCQ and oral answer. The interview score is correct answers (and AI marks)
                  against the full planned set — unanswered or skipped questions count as 0.
                </p>

                {agent6?.report ? (
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { label: 'Interview', value: Number(agent6.report.interview_score || 0).toFixed(0) },
                      { label: 'Answered', value: `${agent6.report.questions_answered || 0}/${agent6.report.questions_total || 0}` },
                      { label: 'MCQ', value: `${agent6.report.mcq_correct || 0}/${agent6.report.mcq_total || 0}` },
                    ].map((item) => (
                      <div key={item.label} className="rounded-xl border border-col px-3 py-2 text-center">
                        <p className="text-[10px] uppercase tracking-wider text-muted font-semibold">{item.label}</p>
                        <p className="text-sm font-bold text-col">{item.value}</p>
                      </div>
                    ))}
                  </div>
                ) : null}

                {agent6?.report?.left_early ? (
                  <p className="text-xs text-amber-700 dark:text-amber-300 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/80 dark:bg-amber-900/20 px-3 py-2">
                    Candidate left the interview before finishing. Remaining questions are scored as 0.
                  </p>
                ) : null}

                {Array.isArray(agent6?.report?.items) && agent6.report.items.length ? (
                  <ul className="space-y-2">
                    {agent6.report.items.map((row, index) => (
                      <li
                        key={`${row.kind}-${row.question_id || index}`}
                        className="rounded-xl border border-col px-3 py-2.5 bg-white/60 dark:bg-slate-900/40 space-y-1.5"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] uppercase tracking-wider font-semibold text-muted">
                            {answerKindLabel(row.kind)} · {answerStatusLabel(row.status)}
                          </span>
                          <span className="text-[11px] font-semibold text-col">
                            {Number(row.score || 0).toFixed(0)} / {Number(row.max_score || 100).toFixed(0)}
                            {row.verdict ? ` · ${row.verdict}` : ''}
                          </span>
                        </div>
                        <p className="text-sm text-col font-medium whitespace-pre-wrap">{row.question_text || '—'}</p>
                        <p className="text-xs text-col">
                          <span className="font-semibold">Answer: </span>
                          {row.answer_text || 'Not answered'}
                        </p>
                        {row.has_audio && row.question_id ? (
                          <OralAnswerAudio
                            candidateId={candidateId}
                            questionId={row.question_id}
                            hasAudio
                          />
                        ) : row.kind !== 'mcq' && row.status === 'answered' ? (
                          <p className="text-[11px] text-muted">
                            Voice clip is saved for new answers. This turn was stored as transcript text only.
                          </p>
                        ) : null}
                        {row.kind === 'mcq' && row.correct_answer ? (
                          <p className="text-[11px] text-muted">Correct option: {row.correct_answer}</p>
                        ) : null}
                        {row.feedback ? <p className="text-[11px] text-muted leading-relaxed">{row.feedback}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="rounded-xl border border-dashed border-col px-4 py-5 text-center">
                    <Gauge size={18} className="mx-auto text-muted mb-2" />
                    <p className="text-sm text-col font-medium">No evaluations yet</p>
                    <p className="text-xs text-muted mt-1">
                      MCQ and oral questions appear here as the candidate answers, or as unanswered if they quit mid-interview.
                    </p>
                  </div>
                )}
              </div>
            )}
          </AgentCard>
        )}

        {activeAgent === 7 && (
          <AgentCard
            agent="Agent 7 · Recommendation"
            title="Final HR report"
            subtitle="Screening + interview scores + similar past cases from Chroma"
            status={
              agent7Loading
                ? 'Loading'
                : !(agent7?.interview_ready || agent6?.report?.interview_attempted) && agent7?.latest?.report
                  ? 'Hold — no interview'
                : agent7?.latest?.report
                  ? agent7.latest.report.decision
                  : 'Awaiting report'
            }
            statusTone={
              !(agent7?.interview_ready || agent6?.report?.interview_attempted) && agent7?.latest?.report
                ? 'pending'
                : agent7?.latest?.report?.decision === 'HIRE'
                ? 'ready'
                : agent7?.latest?.report?.decision === 'REJECT'
                  ? 'error'
                  : agent7?.latest?.report
                    ? 'pending'
                    : 'missing'
            }
          >
            {agent7Loading ? (
              <p className="text-sm text-muted flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Loading recommendation agent…
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: 'Meta Llama', ok: Boolean(agent7?.capabilities?.meta_llama) },
                    { label: 'Chroma memory', ok: Boolean(agent7?.capabilities?.chroma_memory) },
                    { label: 'LangGraph', ok: Boolean(agent7?.capabilities?.langgraph) },
                    { label: 'Interview scores', ok: Boolean(agent7?.interview_ready || agent7?.evaluations_count || agent6?.report?.interview_attempted) },
                  ].map(({ label, ok }) => (
                    <div
                      key={label}
                      className={`rounded-xl px-3 py-2.5 border text-center ${
                        ok
                          ? 'border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/40 dark:bg-emerald-900/20'
                          : 'border-col bg-slate-50 dark:bg-slate-800/40'
                      }`}
                    >
                      <p className="text-[10px] uppercase tracking-wider text-muted font-semibold">
                        {label}
                      </p>
                      <p className="text-xs font-medium text-col mt-0.5">{ok ? 'On' : 'Off'}</p>
                    </div>
                  ))}
                </div>

                <p className="text-xs text-muted leading-relaxed">
                  Agent 7 writes the hire / consider / reject recommendation after Agent 6 has interview evidence.
                  Unanswered questions count as 0. Screening-only scores cannot produce Consider or Hire.
                </p>

                {agent7?.left_early || agent6?.report?.left_early ? (
                  <p className="text-xs text-amber-700 dark:text-amber-300 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/80 dark:bg-amber-900/20 px-3 py-2">
                    Candidate quit mid-interview. This HR report uses the questions they answered plus zeros for the rest.
                  </p>
                ) : null}

                {agent7?.latest?.report ? (
                  (() => {
                    const report = agent7.latest.report;
                    return (
                      <div className="space-y-3">
                        <div className="grid grid-cols-3 gap-2">
                          {[
                            { label: 'Overall', value: Number(report.overall_score || 0).toFixed(0) },
                            { label: 'Screening', value: Number(report.screening_score || 0).toFixed(0) },
                            { label: 'Interview', value: Number(report.interview_score || 0).toFixed(0) },
                          ].map((item) => (
                            <div key={item.label} className="rounded-xl border border-col px-3 py-2 text-center">
                              <p className="text-[10px] uppercase tracking-wider text-muted font-semibold">
                                {item.label}
                              </p>
                              <p className="text-lg font-bold text-col">{item.value}</p>
                            </div>
                          ))}
                        </div>
                        <p className="text-sm text-col leading-relaxed">{report.executive_summary}</p>
                        {report.chroma_recommendation ? (
                          <p className="text-xs text-muted leading-relaxed">{report.chroma_recommendation}</p>
                        ) : null}
                        {Array.isArray(report.strengths) && report.strengths.length ? (
                          <div>
                            <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-1">
                              Strengths
                            </p>
                            <ul className="text-xs text-col list-disc pl-4 space-y-0.5">
                              {report.strengths.slice(0, 4).map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {Array.isArray(report.risks) && report.risks.length ? (
                          <div>
                            <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-1">
                              Risks
                            </p>
                            <ul className="text-xs text-col list-disc pl-4 space-y-0.5">
                              {report.risks.slice(0, 4).map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {Array.isArray(report.next_steps) && report.next_steps.length ? (
                          <p className="text-xs text-col">
                            <span className="font-semibold">Next: </span>
                            {report.next_steps[0]}
                          </p>
                        ) : null}
                        {Array.isArray(report.similar_past_cases) && report.similar_past_cases.length ? (
                          <ul className="space-y-1.5">
                            {report.similar_past_cases.slice(0, 3).map((item, index) => (
                              <li
                                key={`${item.candidate_id || 'case'}-${index}`}
                                className="rounded-lg bg-slate-50 dark:bg-slate-800/40 px-3 py-2 text-[11px] text-muted"
                              >
                                <span className="font-semibold text-col">
                                  {item.decision || 'Case'}
                                  {item.score != null ? ` · ${item.score}` : ''}
                                </span>
                                {item.excerpt ? ` — ${item.excerpt}` : ''}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    );
                  })()
                ) : (
                  <div className="rounded-xl border border-dashed border-col px-4 py-5 text-center">
                    <ClipboardCheck size={18} className="mx-auto text-muted mb-2" />
                    <p className="text-sm text-col font-medium">No HR report yet</p>
                    <p className="text-xs text-muted mt-1">
                      Generate now, or wait until the live interview completes.
                    </p>
                  </div>
                )}

                {agent7?.latest?.report && !agent7?.interview_ready && Number(agent7.latest.report.interview_score || 0) === 0 ? (
                  <p className="text-xs text-amber-700 dark:text-amber-300 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/80 dark:bg-amber-900/20 px-3 py-2">
                    This report was generated before interview scores existed. It should not be used for hiring. Generate again after Agent 6 has results.
                  </p>
                ) : null}

                <button
                  type="button"
                  onClick={() => handleGenerateHrReport(true)}
                  disabled={generatingReport || !(agent7?.interview_ready || agent6?.report?.interview_attempted)}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 text-white text-sm font-semibold py-2.5 disabled:opacity-50"
                >
                  {generatingReport ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  {agent7?.latest?.report ? 'Regenerate report' : 'Generate HR report'}
                </button>
                {!(agent7?.interview_ready || agent6?.report?.interview_attempted) ? (
                  <p className="text-[11px] text-muted text-center">
                    Wait for Agent 6 interview scores, or until the candidate leaves or completes the interview.
                  </p>
                ) : null}
              </div>
            )}
          </AgentCard>
        )}
      </section>

      <Modal
        open={Boolean(questionEditor)}
        onClose={() => !savingQuestion && setQuestionEditor(null)}
        title={questionEditor?.mode === 'edit' ? 'Edit interview question' : 'Add interview question'}
        size="md"
      >
        {questionEditor ? (
          <form onSubmit={handleSaveQuestion} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                Insert at number
              </label>
              <input
                type="number"
                min={1}
                max={
                  questionEditor.mode === 'edit'
                    ? Math.max(agent4?.question_set?.questions?.length || 1, 1)
                    : (agent4?.question_set?.questions?.length || 0) + 1
                }
                value={questionEditor.insertAt}
                onChange={(e) => setQuestionEditor((prev) => (
                  prev ? { ...prev, insertAt: Number(e.target.value) || 1 } : prev
                ))}
                className="w-full rounded-xl border border-col bg-white dark:bg-slate-900 px-3 py-2 text-sm text-col"
              />
              <p className="text-[11px] text-muted mt-1">
                Use 1 for the first question. A number in the middle pushes later questions down.
              </p>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                Category
              </label>
              <select
                value={questionEditor.categoryId}
                onChange={(e) => setQuestionEditor((prev) => (
                  prev ? { ...prev, categoryId: e.target.value } : prev
                ))}
                className="w-full rounded-xl border border-col bg-white dark:bg-slate-900 px-3 py-2 text-sm text-col"
              >
                {QUESTION_CATEGORIES.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                Difficulty
              </label>
              <select
                value={questionEditor.difficulty}
                onChange={(e) => setQuestionEditor((prev) => (
                  prev ? { ...prev, difficulty: e.target.value } : prev
                ))}
                className="w-full rounded-xl border border-col bg-white dark:bg-slate-900 px-3 py-2 text-sm text-col"
              >
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-muted mb-1.5">
                Question
              </label>
              <textarea
                value={questionEditor.text}
                onChange={(e) => setQuestionEditor((prev) => (
                  prev ? { ...prev, text: e.target.value } : prev
                ))}
                rows={4}
                required
                minLength={8}
                placeholder="Type the question the interviewer should ask…"
                className="w-full rounded-xl border border-col bg-white dark:bg-slate-900 px-3 py-2 text-sm text-col placeholder:text-muted resize-none"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setQuestionEditor(null)}
                disabled={savingQuestion}
                className="btn-secondary px-3 py-2 text-sm disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingQuestion}
                className="btn-primary px-3 py-2 text-sm inline-flex items-center gap-2 disabled:opacity-60"
              >
                {savingQuestion ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                {questionEditor.mode === 'edit' ? 'Save question' : 'Add question'}
              </button>
            </div>
          </form>
        ) : null}
      </Modal>

      <Modal
        open={agent5ReportOpen}
        onClose={() => setAgent5ReportOpen(false)}
        title="Agent 5 proctoring report"
        size="xl"
      >
        {agent5ReportLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted py-8 justify-center">
            <Loader2 size={16} className="animate-spin" />
            Loading report…
          </div>
        ) : agent5Report ? (
          <div className="space-y-5 text-sm">
            <div className="grid sm:grid-cols-2 gap-3">
              <p><strong>Session:</strong> {agent5Report.session?.id || agent5?.agent5_session_id}</p>
              <p><strong>Status:</strong> {agent5Report.session?.status || '—'}</p>
              <p>
                <strong>Risk:</strong>{' '}
                {agent5Report.risk?.score != null
                  ? `${Math.round(agent5Report.risk.score)} (${agent5Report.risk.classification || 'low'})`
                  : '—'}
              </p>
              <p><strong>Tab switches:</strong> {agent5Report.session?.tab_switch_count ?? 0}</p>
              <p><strong>Events:</strong> {(agent5Report.timeline || agent5Report.events || []).length}</p>
              <p><strong>Voice attempts:</strong> {(agent5Report.voice_sentence_attempts || []).length}</p>
            </div>
            {agent5Report.session?.termination_reason ? (
              <p className="text-red-600 dark:text-red-400">
                <strong>Termination reason:</strong> {agent5Report.session.termination_reason}
              </p>
            ) : null}
            <div className="rounded-xl border border-col p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Identity checks</p>
              <div className="grid sm:grid-cols-2 gap-2">
                <p>Face enrolled: {agent5Report.initial_verification?.face_enrolled ? 'Yes' : 'No'}</p>
                <p>Face verified: {agent5Report.initial_verification?.face_verified ? 'Yes' : 'No'}</p>
                <p>Voice enrolled: {agent5Report.initial_verification?.voice_enrolled ? 'Yes' : 'No'}</p>
                <p>Voice verified: {agent5Report.initial_verification?.voice_verified ? 'Yes' : 'No'}</p>
                <p>Camera: {agent5Report.device_checks?.camera_ok ? 'OK' : '—'}</p>
                <p>Microphone: {agent5Report.device_checks?.microphone_ok ? 'OK' : '—'}</p>
              </div>
            </div>
            {(agent5Report.voice_sentence_attempts || []).length > 0 ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Voice attempts</p>
                <ul className="space-y-2 max-h-40 overflow-y-auto">
                  {agent5Report.voice_sentence_attempts.slice(0, 8).map((attempt) => (
                    <li key={attempt.id} className="rounded-lg border border-col px-3 py-2">
                      <p className="font-medium text-col">
                        {attempt.stage || 'attempt'} · {attempt.passed ? 'Passed' : 'Failed'}
                        {attempt.completion_percentage != null
                          ? ` · ${Math.round(attempt.completion_percentage)}%`
                          : ''}
                      </p>
                      {attempt.recognized_transcript ? (
                        <p className="text-xs text-muted mt-1">{attempt.recognized_transcript}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {(agent5Report.timeline || []).length > 0 ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Event timeline</p>
                <ul className="space-y-2 max-h-48 overflow-y-auto">
                  {agent5Report.timeline.slice(0, 12).map((event) => (
                    <li key={event.id} className="rounded-lg border border-col px-3 py-2">
                      <p className="font-medium text-col">
                        {event.type?.replaceAll('_', ' ') || 'event'}
                        {event.risk_contribution ? ` · +${Number(event.risk_contribution).toFixed(1)} risk` : ''}
                      </p>
                      {event.explanation ? (
                        <p className="text-xs text-muted mt-1">{event.explanation}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-muted">No fraud events were recorded for this session.</p>
            )}
            <a
              href="/monitor/"
              className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"
            >
              <ExternalLink size={14} />
              Open full review workspace
            </a>
          </div>
        ) : (
          <p className="text-sm text-muted py-6">No proctoring report is available yet for this candidate.</p>
        )}
      </Modal>
    </div>
  );
}
