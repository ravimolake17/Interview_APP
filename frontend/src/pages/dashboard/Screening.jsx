import { useState, useCallback, useMemo, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Bot,
  Play,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Briefcase,
  GraduationCap,
  Mail,
  Phone,
  ExternalLink,
  Star,
} from 'lucide-react';
import FileUploader from '../../components/ui/FileUploader';
import DuplicateJobDialog from '../../components/ui/DuplicateJobDialog';
import { MatchScore, SkillBadge, RecommendationBadge, StatusBadge } from '../../components/ui/Badges';
import { LoadingOverlay } from '../../components/ui/LoadingOverlay';
import EmptyState from '../../components/ui/EmptyState';
import { useApp } from '../../context/AppContext';
import { runBatchScreening, uploadJobDescription } from '../../services/screeningApi';
import { checkJobDuplicate, getScreeningFileUrl } from '../../services/api';
import { mapEvaluationToScreeningResult } from '../../utils/hrMappers';
import { nextAvailableJobTitle, duplicateJobDetail } from '../../utils/jobTitle';

function SectionCard({ title, children, action }) {
  return (
    <div className="rounded-xl border border-col bg-slate-50/50 dark:bg-slate-800/30 overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-col bg-white/80 dark:bg-slate-900/40">
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">{title}</h4>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function ScoreBreakdownBar({ label, value, weight }) {
  const score = Number(value) || 0;
  const max = Number(weight);
  const hasMax = Number.isFinite(max) && max > 0;
  const percent = hasMax ? Math.min(100, (score / max) * 100) : Math.min(100, score);
  const displayValue = Number.isInteger(score) ? score : score.toFixed(1);

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-1">
        <p className="text-sm text-col">{label}</p>
        <p className="text-sm font-semibold text-col">
          {displayValue}
          {hasMax ? (
            <span className="text-xs font-normal text-muted"> / {max}</span>
          ) : null}
        </p>
      </div>
      <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
        <div
          className="h-full rounded-full bg-primary-accent transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function CandidateResultCard({ candidate: c, delay }) {
  const statusLabel =
    c.shortlistStatus === 'Shortlisted'
      ? 'Shortlisted'
      : c.shortlistStatus === 'Rejected'
        ? 'Rejected'
        : 'Needs Review';

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: 'spring', stiffness: 200, damping: 20 }}
      className="card overflow-hidden"
    >
      <div className="px-6 py-5 border-b border-col bg-gradient-to-br from-orange-50 to-slate-50 dark:from-orange-900/10 dark:to-slate-800/20">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4 min-w-0">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-white font-bold text-lg flex-shrink-0"
              style={{ background: c.avatarColor }}
            >
              {c.avatar}
            </div>
            <div className="min-w-0">
              <h3 className="text-lg font-bold text-col truncate">{c.name}</h3>
              {c.contact ? (
                <p className="text-sm text-muted truncate mt-0.5">{c.contact}</p>
              ) : (
                <div className="flex flex-wrap gap-3 mt-1 text-sm text-muted">
                  {c.email && (
                    <span className="inline-flex items-center gap-1">
                      <Mail size={12} /> {c.email}
                    </span>
                  )}
                  {c.phone && (
                    <span className="inline-flex items-center gap-1">
                      <Phone size={12} /> {c.phone}
                    </span>
                  )}
                </div>
              )}
              <p className="text-xs text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="inline-flex items-center gap-1">
                  <Briefcase size={12} /> {c.experience}
                </span>
                <span className="inline-flex items-center gap-1">
                  <GraduationCap size={12} /> {c.education}
                </span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <StatusBadge status={statusLabel} />
            <RecommendationBadge recommendation={c.recommendation} />
            <MatchScore score={c.matchScore} size="lg" />
          </div>
        </div>

        {c.summary && (
          <div className="mt-4 rounded-xl border border-amber-100 dark:border-amber-900/40 bg-amber-50/70 dark:bg-amber-900/10 px-4 py-3 text-sm text-col leading-relaxed flex gap-2">
            <Star size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
            <p>{c.summary}</p>
          </div>
        )}
      </div>

      <div className="p-6 space-y-5">
        {c.scoreBreakdown?.length > 0 && (
          <SectionCard title="Score breakdown">
            <div className="space-y-3">
              {c.scoreBreakdown.map((row) => (
                <ScoreBreakdownBar
                  key={row.label}
                  label={row.label}
                  value={row.value}
                  weight={row.weight}
                />
              ))}
            </div>
          </SectionCard>
        )}

        <SectionCard title="JD-relevant experience match">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
            <div>
              <p className="text-xs text-muted mb-1">JD requirement</p>
              <p className="text-sm font-medium text-col">{c.experienceAssessment.jdRequirement}</p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Professional experience</p>
              <p className="text-sm font-medium text-col">
                {c.experienceAssessment.professionalYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Relevant internship</p>
              <p className="text-sm font-medium text-col">
                {c.experienceAssessment.internshipYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Relevant projects</p>
              <p className="text-sm font-medium text-col">
                {c.experienceAssessment.projectYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Total relevant (professional)</p>
              <p className="text-sm font-medium text-col">
                {c.experienceAssessment.professionalYears || c.experienceAssessment.relevantYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Supporting exposure (intern/projects)</p>
              <p className="text-sm font-medium text-col">
                {c.experienceAssessment.supportingYears || '—'}
              </p>
              <p className="text-[11px] text-muted mt-0.5">
                Not added to total relevant; shown separately
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Years toward JD requirement</p>
              <p className="text-sm font-medium text-col">
                {c.experienceAssessment.yearsTowardRequirement || '—'}
                {c.experienceAssessment.requirementKind
                  ? ` (${String(c.experienceAssessment.requirementKind).replace(/_/g, ' ')})`
                  : ''}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">JD allows internship toward req.</p>
              <p className="text-sm font-medium text-col">
                {c.experienceAssessment.allowsInternship ? 'YES' : 'NO / NOT SPECIFIED'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Hard requirements</p>
              <p className="text-sm font-medium text-col">
                {c.hardRequirementStatus || 'N/A'}
              </p>
            </div>
            <div className="sm:col-span-2 lg:col-span-3">
              <p className="text-xs text-muted mb-1">Experience result</p>
              <p className="text-sm font-medium text-col">{c.experienceAssessment.result}</p>
            </div>
          </div>

          {c.hardRequirementReasons?.length > 0 && (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
              <p className="text-xs font-semibold text-amber-800 uppercase tracking-wider mb-1">
                Hard requirement gaps
              </p>
              <ul className="space-y-1 text-sm text-amber-900">
                {c.hardRequirementReasons.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {c.experienceAssessment.counted?.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Counted experience</p>
              <ul className="space-y-1.5 text-sm text-col">
                {c.experienceAssessment.counted.map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {c.experienceAssessment.excluded?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                Excluded from relevant experience
              </p>
              <ul className="space-y-1.5 text-sm text-col">
                {c.experienceAssessment.excluded.map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <XCircle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </SectionCard>

        <div className="grid sm:grid-cols-2 gap-4">
          <SectionCard title="Matched skills">
            {c.skills.length ? (
              <div className="flex flex-wrap gap-1.5">
                {c.skills.map((skill) => (
                  <SkillBadge key={skill} skill={skill} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">No matched skills.</p>
            )}
          </SectionCard>
          <SectionCard title="Missing skills">
            {c.missingSkills.length ? (
              <div className="flex flex-wrap gap-1.5">
                {c.missingSkills.map((skill) => (
                  <SkillBadge key={skill} skill={skill} missing />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">No missing skills.</p>
            )}
          </SectionCard>
        </div>

        {(c.strengths.length > 0 || c.concerns.length > 0) && (
          <div className="grid sm:grid-cols-2 gap-4">
            {c.strengths.length > 0 && (
              <SectionCard title="Strengths">
                <ul className="space-y-1.5 text-sm text-col">
                  {c.strengths.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}
            {c.concerns.length > 0 && (
              <SectionCard title="Concerns">
                <ul className="space-y-1.5 text-sm text-col">
                  {c.concerns.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <AlertCircle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}
          </div>
        )}

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SectionCard title="Education">
            <p className="text-sm text-col leading-relaxed">{c.education}</p>
            {c.certifications?.length > 0 && (
              <div className="mt-3">
                <p className="text-xs text-muted mb-1.5">Certifications</p>
                <div className="flex flex-wrap gap-1.5">
                  {c.certifications.map((item) => (
                    <span
                      key={item}
                      className="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-col"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </SectionCard>
          <SectionCard title="Job title">
            <p className="text-sm font-medium text-col">{c.jobTitle}</p>
          </SectionCard>
          <SectionCard title="Required skill match">
            <p className="text-2xl font-bold text-col">{c.requiredMatchRatio}%</p>
          </SectionCard>
          <SectionCard title="Preferred skill match">
            <p className="text-2xl font-bold text-col">{c.preferredMatchRatio}%</p>
          </SectionCard>
        </div>

        {c.resumeFileUrl && (
          <div className="flex justify-end">
            <a
              href={getScreeningFileUrl(c.resumeFileUrl)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-accent hover:opacity-80"
            >
              <ExternalLink size={14} />
              Open resume file
            </a>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default function Screening() {
  const {
    isScreening,
    setIsScreening,
    screeningResults,
    setScreeningResults,
    addToast,
    refreshData,
    jobs,
    addJob,
  } = useApp();
  const [jdFile, setJdFile] = useState(null);
  const [jdText, setJdText] = useState('');
  const [selectedJobId, setSelectedJobId] = useState('');
  const [jdMode, setJdMode] = useState('saved');
  const [resumeFiles, setResumeFiles] = useState([]);
  const [step, setStep] = useState(0);
  const [screeningProgress, setScreeningProgress] = useState('');
  const [sendInviteEmail, setSendInviteEmail] = useState(true);
  const [storeJd, setStoreJd] = useState(true);
  const [duplicatePrompt, setDuplicatePrompt] = useState(null);
  const duplicateWaiter = useRef(null);

  const savedJobs = useMemo(
    () => (jobs || []).filter((job) => job.parsedJd || job.jdText?.trim()),
    [jobs],
  );

  const selectedJob = useMemo(
    () => savedJobs.find((job) => String(job.id) === String(selectedJobId)) || null,
    [savedJobs, selectedJobId],
  );

  const MIN_JD_CHARS = 80;

  const jdReady = jdMode === 'saved'
    ? Boolean(selectedJob)
    : jdMode === 'upload'
      ? Boolean(jdFile)
      : jdText.trim().length >= MIN_JD_CHARS;

  const handleResumeFiles = useCallback((files) => {
    setResumeFiles(Array.isArray(files) ? files : files ? [files] : []);
  }, []);

  const handleJdFile = useCallback((file) => {
    setJdFile(Array.isArray(file) ? file[0] : file);
  }, []);

  const askDuplicateDecision = useCallback((existing, reason, suggestedTitle) => {
    return new Promise((resolve) => {
      duplicateWaiter.current = resolve;
      setDuplicatePrompt({ existing, reason, suggestedTitle });
    });
  }, []);

  const closeDuplicatePrompt = useCallback((result) => {
    const resolve = duplicateWaiter.current;
    duplicateWaiter.current = null;
    setDuplicatePrompt(null);
    resolve?.(result);
  }, []);

  const persistJdToJobs = useCallback(async (jdPayload) => {
    const parsed = jdPayload?.parsed_jd || {};
    const parsedTitle = String(parsed.job_title || '').trim();
    const title = parsedTitle && parsedTitle !== 'Open Position' ? parsedTitle : '';
    const required = parsed.required_skills?.normalized || parsed.required_skills?.raw || [];
    const preferred = parsed.preferred_skills?.normalized || parsed.preferred_skills?.raw || [];
    const skills = [...new Set([...(required || []), ...(preferred || [])].map(String))];
    let check = { data: { duplicate: false } };
    try {
      check = await checkJobDuplicate({
        title: title || undefined,
        jdFileUrl: jdPayload?.stored_file_url,
      });
    } catch {
      check = { data: { duplicate: false } };
    }
    let onDuplicate = 'error';
    let finalTitle = title;
    if (check.data?.duplicate && check.data.existing) {
      const suggested = nextAvailableJobTitle(title || check.data.existing.title || 'Open Position', jobs);
      const choice = await askDuplicateDecision(
        check.data.existing,
        check.data.reason,
        suggested,
      );
      if (!choice) {
        const error = new Error('Job save cancelled.');
        error.cancelled = true;
        throw error;
      }
      if (choice.action === 'replace') onDuplicate = 'replace';
      if (choice.action === 'rename') {
        onDuplicate = 'rename';
        finalTitle = choice.title;
      }
    }
    const payload = {
      title: finalTitle || title || 'Open Position',
      department: parsed.department || 'Hiring',
      location: parsed.location || 'India',
      description: jdPayload?.jd_text || jdText,
      skills,
      jdOriginalFilename: jdPayload?.original_filename,
      jdFileUrl: jdPayload?.stored_file_url,
      jdText: jdPayload?.jd_text || jdText.trim() || undefined,
      parsedJd: jdPayload?.parsed_jd,
      onDuplicate,
    };
    try {
      await addJob(payload);
    } catch (error) {
      const dup = duplicateJobDetail(error);
      if (!dup) throw error;
      const suggested = nextAvailableJobTitle(finalTitle, jobs);
      const choice = await askDuplicateDecision(dup.existing, dup.reason, suggested);
      if (!choice) {
        const cancelled = new Error('Job save cancelled.');
        cancelled.cancelled = true;
        throw cancelled;
      }
      await addJob({
        ...payload,
        title: choice.action === 'rename' ? choice.title : payload.title,
        onDuplicate: choice.action,
      });
    }
  }, [addJob, askDuplicateDecision, jobs, jdText]);

  const handleStartScreening = useCallback(async () => {
    if (!jdReady) {
      addToast(
        jdMode === 'saved'
          ? 'Please select a saved job from the Jobs tab.'
          : jdMode === 'paste' && jdText.trim()
            ? 'This job description is too short to score against. Paste a complete JD with skills, experience, and responsibilities.'
            : 'Please upload or paste a job description first.',
        'error',
      );
      return;
    }
    if (resumeFiles.length === 0) {
      addToast('Please upload at least one resume.', 'error');
      return;
    }

    setIsScreening(true);
    setScreeningProgress('');
    try {
      let preparedJd = null;
      if (jdMode !== 'saved') {
        if (jdMode === 'upload' && jdFile) {
          setScreeningProgress('Uploading job description…');
          preparedJd = await uploadJobDescription(jdFile);
        } else if (jdMode === 'paste' && jdText.trim()) {
          preparedJd = { jd_text: jdText.trim() };
        }
        if (storeJd && preparedJd) {
          setScreeningProgress('Saving job description to Jobs…');
          await persistJdToJobs(preparedJd);
        }
      }
      const batch = await runBatchScreening({
        resumeFiles,
        jdFile: jdMode === 'upload' && !preparedJd ? jdFile : null,
        jdText: jdMode === 'paste' ? jdText.trim() : '',
        selectedJob: jdMode === 'saved' ? selectedJob : null,
        preparedJd,
        sendInviteEmail,
        onProgress: (current, total, name, stage) => {
          const label =
            stage === 'scoring' ? 'Scoring' : stage === 'uploading' ? 'Uploading' : 'Extracting';
          setScreeningProgress(`${label} resume ${current} of ${total}: ${name}`);
        },
      });
      const mapped = batch.results.map(({ extraction, result }, index) =>
        mapEvaluationToScreeningResult(result, extraction, index),
      );
      setScreeningResults(mapped);
      setStep(1);
      await refreshData({ silent: true, force: true });
      if (batch.failures.length) {
        const details = batch.failures
          .map(({ name, message }) => `${name}: ${message}`)
          .join('\n');
        addToast(
          mapped.length
            ? `Screened ${mapped.length} of ${resumeFiles.length} resumes.\n${details}`
            : details,
          'error',
        );
      } else {
        addToast(`AI screening complete — ${mapped.length} candidate(s) saved to database.`, 'success');
      }
    } catch (error) {
      if (error.cancelled) {
        addToast('Screening not started. Store the JD with Replace or Rename, or uncheck Store JD into Jobs.', 'info');
      } else {
        addToast(error.message || 'Screening failed.', 'error');
      }
    } finally {
      setIsScreening(false);
      setScreeningProgress('');
    }
  }, [jdMode, jdFile, jdText, jdReady, resumeFiles, selectedJob, storeJd, sendInviteEmail, persistJdToJobs, setIsScreening, setScreeningResults, addToast, refreshData]);

  const handleReset = () => {
    setStep(0);
    setJdFile(null);
    setJdText('');
    setSelectedJobId('');
    setJdMode('saved');
    setResumeFiles([]);
    setScreeningResults([]);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {isScreening && (
        <LoadingOverlay
          message={
            screeningProgress
              || 'AI is parsing resumes and saving results to the database…'
          }
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-col">AI Screening</h2>
          <p className="text-sm text-muted">Upload JD and resumes to start intelligent candidate matching</p>
        </div>
        {step === 1 && (
          <button onClick={handleReset} className="px-4 py-2 rounded-xl border border-col text-sm font-medium text-muted hover:text-col hover:bg-slate-50 dark:hover:bg-slate-800 transition-all">
            New Screening
          </button>
        )}
      </div>

      {step === 0 ? (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center">
                <Bot size={18} className="text-blue-500" />
              </div>
              <div>
                <h3 className="font-semibold text-col text-sm">Job Description</h3>
                <p className="text-xs text-muted">Select a saved job or provide a new JD</p>
              </div>
              {jdReady && <CheckCircle2 size={16} className="text-green-500 ml-auto" />}
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              {[
                { id: 'saved', label: 'Saved job' },
                { id: 'upload', label: 'Upload JD' },
                { id: 'paste', label: 'Paste JD' },
              ].map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => {
                    setJdMode(id);
                    if (id === 'saved') {
                      setJdFile(null);
                      setJdText('');
                    } else if (id === 'upload') {
                      setSelectedJobId('');
                      setJdText('');
                    } else {
                      setSelectedJobId('');
                      setJdFile(null);
                    }
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                    jdMode === id
                      ? 'bg-primary-accent text-white border-primary-accent'
                      : 'border-col text-muted hover:text-col'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {jdMode === 'saved' ? (
              <div className="space-y-2">
                <label htmlFor="saved-job-select" className="text-xs font-medium text-muted">
                  Saved jobs (from Jobs tab)
                </label>
                <select
                  id="saved-job-select"
                  value={selectedJobId}
                  onChange={(e) => setSelectedJobId(e.target.value)}
                  className="w-full rounded-xl border border-col bg-transparent px-3 py-2.5 text-sm text-col focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                >
                  <option value="">Select a saved job…</option>
                  {savedJobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.title}
                      {job.department ? ` · ${job.department}` : ''}
                    </option>
                  ))}
                </select>
                {savedJobs.length === 0 ? (
                  <p className="text-xs text-muted">
                    No saved jobs with JD content yet. Create one manually in the Jobs tab, or upload/paste a JD here.
                  </p>
                ) : selectedJob ? (
                  <p className="text-xs text-muted">
                    Using saved JD for <span className="font-medium text-col">{selectedJob.title}</span>.
                    Screening will not create a new job entry.
                  </p>
                ) : null}
              </div>
            ) : jdMode === 'upload' ? (
              <FileUploader
                accept=".pdf,.doc,.docx"
                label="Drop Job Description here"
                hint="PDF or DOCX · Max 10MB"
                onFiles={handleJdFile}
              />
            ) : (
              <textarea
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                rows={6}
                placeholder="Paste a complete job description (skills, experience, responsibilities)…"
                className="w-full rounded-xl border border-col bg-transparent px-3 py-2 text-sm text-col placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            )}
            {jdMode === 'paste' && jdText.trim() && jdText.trim().length < MIN_JD_CHARS && (
              <p className="mt-2 text-xs text-amber-600">
                This text is too short to score. Paste a full JD ({MIN_JD_CHARS}+ characters).
              </p>
            )}
            {jdMode !== 'saved' && (
              <label className="mt-4 flex items-start gap-2.5 text-sm text-col cursor-pointer">
                <input
                  type="checkbox"
                  checked={storeJd}
                  onChange={(e) => setStoreJd(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-col accent-orange-500"
                />
                <span>
                  <span className="font-medium">Store JD into Jobs</span>
                  <span className="block text-xs text-muted mt-0.5">
                    Selected by default. Uncheck to screen without saving this JD. Duplicate JDs will ask to replace or rename.
                  </span>
                </span>
              </label>
            )}
          </div>

          <div className="card p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-xl bg-violet-50 dark:bg-violet-900/20 flex items-center justify-center">
                <Bot size={18} className="text-violet-500" />
              </div>
              <div>
                <h3 className="font-semibold text-col text-sm">Candidate Resumes</h3>
                <p className="text-xs text-muted">Upload one or many resumes</p>
              </div>
              {resumeFiles.length > 0 && (
                <span className="ml-auto text-xs font-semibold text-green-500 bg-green-50 dark:bg-green-900/20 px-2 py-0.5 rounded-full">
                  {resumeFiles.length} file{resumeFiles.length > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <FileUploader
              key={`resume-uploader-${step}`}
              accept=".pdf,.doc,.docx"
              label="Drop Resumes here"
              hint="PDF or DOCX · Multiple files supported"
              multiple
              onFiles={handleResumeFiles}
            />
          </div>

          <div className="lg:col-span-2 card p-6 bg-gradient-to-r from-orange-500 to-amber-600 border-0">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="font-bold text-white text-lg">Ready to Screen?</h3>
                <p className="text-orange-100 text-sm mt-1">
                  Our AI agent will analyse each resume against the JD and generate a detailed match report.
                </p>
                <div className="flex flex-wrap gap-4 mt-3">
                  {[
                    {
                      label: jdMode === 'saved'
                        ? (selectedJob ? `Job: ${selectedJob.title}` : 'Saved job')
                        : jdMode === 'upload'
                          ? 'JD uploaded'
                          : 'JD pasted',
                      ok: jdReady,
                    },
                    { label: `${resumeFiles.length} Resume${resumeFiles.length !== 1 ? 's' : ''}`, ok: resumeFiles.length > 0 },
                  ].map(({ label, ok }) => (
                    <div key={label} className="flex items-center gap-1.5 text-sm">
                      {ok
                        ? <CheckCircle2 size={14} className="text-green-300" />
                        : <AlertCircle size={14} className="text-orange-200" />}
                      <span className={ok ? 'text-white' : 'text-orange-200'}>{label}</span>
                    </div>
                  ))}
                </div>
                <label className="mt-4 inline-flex items-start gap-2.5 text-sm text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={sendInviteEmail}
                    onChange={(e) => setSendInviteEmail(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-white/40 accent-white"
                  />
                  <span>
                    <span className="font-semibold">Send email</span>
                    <span className="block text-xs text-orange-100 mt-0.5">
                      Selected by default. Uncheck to skip automatic invite emails so HR can send them later.
                    </span>
                  </span>
                </label>
              </div>
              <button
                onClick={handleStartScreening}
                disabled={isScreening}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white text-orange-600 font-semibold hover:bg-orange-50 transition-all hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
              >
                <Play size={16} fill="currentColor" />
                Start AI Screening
              </button>
            </div>
          </div>
        </motion.div>
      ) : (
        <div className="space-y-5">
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            className="card p-5 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/10 dark:to-emerald-900/10 border-green-100 dark:border-green-800"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <CheckCircle2 size={20} className="text-green-500" />
              </div>
              <div>
                <h3 className="font-semibold text-col">Screening Complete</h3>
                <p className="text-sm text-muted">
                  {screeningResults.length} candidates analysed ·
                  Avg score: {screeningResults.length ? Math.round(screeningResults.reduce((s, c) => s + c.matchScore, 0) / screeningResults.length) : 0}% ·
                  {screeningResults.filter(c => c.matchScore >= 80).length} highly recommended
                </p>
              </div>
            </div>
          </motion.div>

          <div className="space-y-5">
            {screeningResults.map((c, i) => (
              <CandidateResultCard key={c.id} candidate={c} delay={i * 0.08} />
            ))}
          </div>

          {screeningResults.length === 0 && (
            <EmptyState icon={Bot} title="No results" description="Run a screening to see AI-generated candidate reports." />
          )}
        </div>
      )}
      <DuplicateJobDialog
        open={Boolean(duplicatePrompt)}
        existing={duplicatePrompt?.existing}
        reason={duplicatePrompt?.reason}
        suggestedTitle={duplicatePrompt?.suggestedTitle}
        onCancel={() => closeDuplicatePrompt(null)}
        onReplace={() => closeDuplicatePrompt({ action: 'replace' })}
        onRename={(title) => {
          if (!title) {
            addToast('Enter a new job title to rename this JD.', 'error');
            return;
          }
          closeDuplicatePrompt({ action: 'rename', title });
        }}
      />
    </div>
  );
}
