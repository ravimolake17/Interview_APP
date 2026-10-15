import { useState, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Bot,
  Play,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import FileUploader from '../../components/ui/FileUploader';
import EmptyState from '../../components/ui/EmptyState';
import { CandidateResultCard } from '../../components/screening/CandidateResultCard';
import { useApp } from '../../context/AppContext';
import { useScreeningQueue } from '../../context/ScreeningQueueContext';

export default function Screening() {
  const {
    screeningResults,
    setScreeningResults,
    addToast,
    jobs,
  } = useApp();
  const { enqueueScreeningJob, activeCount } = useScreeningQueue();
  const [jdFile, setJdFile] = useState(null);
  const [jdText, setJdText] = useState('');
  const [selectedJobId, setSelectedJobId] = useState('');
  const [jdMode, setJdMode] = useState('saved');
  const [resumeFiles, setResumeFiles] = useState([]);
  const [step, setStep] = useState(0);
  const [sendInviteEmail, setSendInviteEmail] = useState(true);
  const [storeJd, setStoreJd] = useState(true);
  const [uploaderKey, setUploaderKey] = useState(0);

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

  const handleStartScreening = useCallback(() => {
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

    const label =
      jdMode === 'saved' && selectedJob?.title
        ? selectedJob.title
        : jdMode === 'upload' && jdFile?.name
          ? jdFile.name
          : 'Pasted JD';

    // Enqueue immediately with raw files — JD parse/store happens when this job
    // reaches the front of the queue (so other running jobs don't block add).
    enqueueScreeningJob({
      label,
      resumeFiles: [...resumeFiles],
      jdFile: jdMode === 'upload' ? jdFile : null,
      jdText: jdMode === 'paste' ? jdText.trim() : '',
      selectedJob: jdMode === 'saved' ? selectedJob : null,
      sendInviteEmail,
      storeJd: jdMode !== 'saved' && storeJd,
      jdMode,
    });

    addToast(
      `Added to screening queue (${resumeFiles.length} resume${resumeFiles.length === 1 ? '' : 's'}). Watch the Queue tab.`,
      'success',
    );

    setJdFile(null);
    setJdText('');
    setSelectedJobId('');
    setResumeFiles([]);
    setJdMode('saved');
    setSendInviteEmail(true);
    setStoreJd(true);
    setUploaderKey((key) => key + 1);
  }, [
    jdMode,
    jdFile,
    jdText,
    jdReady,
    resumeFiles,
    selectedJob,
    storeJd,
    sendInviteEmail,
    enqueueScreeningJob,
    addToast,
  ]);

  const handleReset = () => {
    setStep(0);
    setJdFile(null);
    setJdText('');
    setSelectedJobId('');
    setJdMode('saved');
    setResumeFiles([]);
    setUploaderKey((key) => key + 1);
    setScreeningResults([]);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-col">AI Screening</h2>
          <p className="text-sm text-muted">
            Upload JD and resumes to start intelligent candidate matching
            {activeCount > 0
              ? ` · ${activeCount} job${activeCount === 1 ? '' : 's'} running in the side queue`
              : ''}
          </p>
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
                key={`jd-uploader-${uploaderKey}`}
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
                    Selected by default. When this queue job runs, the JD is parsed and saved first. If the same JD/title already exists, you choose Replace, Rename, or Cancel.
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
              key={`resume-uploader-${uploaderKey}`}
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
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white text-orange-600 font-semibold hover:bg-orange-50 transition-all hover:shadow-lg hover:-translate-y-0.5 flex-shrink-0"
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
    </div>
  );
}
