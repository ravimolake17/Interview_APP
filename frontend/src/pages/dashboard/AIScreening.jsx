import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import {
  Upload, FileText, X, Bot, Play, CheckCircle2,
  AlertCircle, Sparkles, ChevronRight, Eye
} from 'lucide-react';
import {
  PageHeader, MatchScoreRing, SkillBadge, RecommendationBadge,
  ProgressBar, CandidateAvatar, EmptyState
} from '@/components/ui/index';
import CandidateDrawer from '@/components/ui/CandidateDrawer';
import { mockCandidates, mockJobs } from '@/data/mockData';
import { formatFileSize } from '@/utils/helpers';
import toast from 'react-hot-toast';

const PROCESSING_STEPS = [
  'Parsing resume documents…',
  'Extracting skills and experience…',
  'Analyzing job requirements…',
  'Calculating match scores…',
  'Generating AI insights…',
  'Finalizing recommendations…',
];

export default function AIScreening() {
  const [jdFile, setJdFile] = useState(null);
  const [resumeFiles, setResumeFiles] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [results, setResults] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  // JD dropzone
  const { getRootProps: getJdProps, getInputProps: getJdInputProps, isDragActive: isJdDrag } = useDropzone({
    onDrop: (files) => files[0] && setJdFile(files[0]),
    accept: { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] },
    maxFiles: 1,
  });

  // Resumes dropzone
  const { getRootProps: getRsProps, getInputProps: getRsInputProps, isDragActive: isRsDrag } = useDropzone({
    onDrop: (files) => setResumeFiles(prev => [...prev, ...files]),
    accept: { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] },
  });

  const removeResume = (name) => setResumeFiles(prev => prev.filter(f => f.name !== name));

  const simulateScreening = useCallback(async () => {
    if (!selectedJob && !jdFile) {
      toast.error('Please select a job or upload a job description.');
      return;
    }
    if (resumeFiles.length === 0) {
      toast.error('Please upload at least one resume.');
      return;
    }

    setIsProcessing(true);
    setProcessingStep(0);
    setProcessingProgress(0);

    // Simulate progressive processing
    for (let i = 0; i < PROCESSING_STEPS.length; i++) {
      await new Promise(r => setTimeout(r, 700));
      setProcessingStep(i);
      setProcessingProgress(Math.round(((i + 1) / PROCESSING_STEPS.length) * 100));
    }

    await new Promise(r => setTimeout(r, 400));
    setIsProcessing(false);

    // Use mock data as results
    const matched = mockCandidates.slice(0, Math.min(resumeFiles.length, mockCandidates.length));
    setResults(matched.sort((a, b) => b.matchScore - a.matchScore));
    toast.success(`Screening complete! ${matched.length} candidate${matched.length !== 1 ? 's' : ''} analyzed.`);
  }, [selectedJob, jdFile, resumeFiles]);

  const resetScreening = () => {
    setResults(null);
    setJdFile(null);
    setResumeFiles([]);
    setSelectedJob('');
    setProcessingProgress(0);
  };

  return (
    <div>
      <PageHeader
        title="AI Screening"
        subtitle="Upload resumes and let AI rank and analyze candidates automatically"
        actions={
          results && (
            <button onClick={resetScreening} className="btn-secondary flex items-center gap-2 text-sm">
              <X size={14} /> New Screening
            </button>
          )
        }
      />

      <AnimatePresence mode="wait">
        {!results && !isProcessing && (
          <motion.div
            key="upload"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="space-y-5"
          >
            {/* Job Selection */}
            <div className="card p-5">
              <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm mb-4 flex items-center gap-2">
                <Bot size={16} className="text-primary-500" /> Job to Screen Against
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Select Existing Job</label>
                  <select
                    value={selectedJob}
                    onChange={e => setSelectedJob(e.target.value)}
                    className="input"
                  >
                    <option value="">— Choose a job —</option>
                    {mockJobs.filter(j => j.status === 'active').map(j => (
                      <option key={j.id} value={j.id}>{j.title} ({j.department})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Or Upload Job Description</label>
                  <div
                    {...getJdProps()}
                    className={`border-2 border-dashed rounded-xl px-4 py-3 text-center cursor-pointer transition-colors ${
                      isJdDrag
                        ? 'border-primary-400 bg-primary-50 dark:bg-primary-950/20'
                        : 'border-slate-200 dark:border-slate-700 hover:border-primary-300 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                    }`}
                  >
                    <input {...getJdInputProps()} />
                    {jdFile ? (
                      <div className="flex items-center justify-center gap-2 text-sm text-primary-600 dark:text-primary-400">
                        <FileText size={14} />
                        <span className="font-medium truncate max-w-[160px]">{jdFile.name}</span>
                        <button type="button" onClick={e => { e.stopPropagation(); setJdFile(null); }} className="text-slate-400 hover:text-red-500">
                          <X size={13} />
                        </button>
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">
                        <Upload size={14} className="inline mr-1.5 -mt-0.5" />
                        Drop JD here (PDF / DOCX)
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Resume Upload */}
            <div className="card p-5">
              <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm mb-4 flex items-center gap-2">
                <FileText size={16} className="text-primary-500" /> Upload Resumes
              </h3>

              <div
                {...getRsProps()}
                className={`border-2 border-dashed rounded-xl py-10 text-center cursor-pointer transition-colors mb-4 ${
                  isRsDrag
                    ? 'border-primary-400 bg-primary-50 dark:bg-primary-950/20'
                    : 'border-slate-200 dark:border-slate-700 hover:border-primary-300 hover:bg-slate-50 dark:hover:bg-slate-800/40'
                }`}
              >
                <input {...getRsInputProps()} />
                <div className="w-12 h-12 rounded-2xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center mx-auto mb-3">
                  <Upload size={20} className="text-primary-600 dark:text-primary-400" />
                </div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Drag & drop resumes here</p>
                <p className="text-xs text-slate-400 mt-1">or click to browse • PDF, DOCX • Multiple files allowed</p>
              </div>

              {/* File list */}
              {resumeFiles.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{resumeFiles.length} file{resumeFiles.length !== 1 ? 's' : ''} selected</p>
                  {resumeFiles.map((f, i) => (
                    <motion.div
                      key={f.name}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="flex items-center gap-3 px-3 py-2.5 bg-slate-50 dark:bg-slate-800 rounded-xl"
                    >
                      <FileText size={15} className="text-primary-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-700 dark:text-slate-300 truncate">{f.name}</p>
                        <p className="text-xs text-slate-400">{formatFileSize(f.size)}</p>
                      </div>
                      <button onClick={() => removeResume(f.name)} className="text-slate-400 hover:text-red-500 transition-colors p-1">
                        <X size={14} />
                      </button>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>

            {/* Start Button */}
            <button
              onClick={simulateScreening}
              disabled={resumeFiles.length === 0}
              className="btn-primary w-full py-3.5 text-base flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Sparkles size={18} />
              Start AI Screening
              {resumeFiles.length > 0 && <span className="text-primary-200">({resumeFiles.length} resume{resumeFiles.length !== 1 ? 's' : ''})</span>}
            </button>
          </motion.div>
        )}

        {/* Processing State */}
        {isProcessing && (
          <motion.div
            key="processing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center py-24 space-y-6"
          >
            {/* Animated AI icon */}
            <div className="relative">
              <div className="w-20 h-20 rounded-3xl bg-primary-600 flex items-center justify-center shadow-lg">
                <Bot size={32} className="text-white" />
              </div>
              <div className="absolute -inset-2 rounded-3xl border-2 border-primary-300 dark:border-primary-700 opacity-60 animate-ping" />
            </div>

            <div className="text-center space-y-1">
              <h3 className="font-bold text-slate-800 dark:text-slate-200 text-lg">AI is analyzing resumes</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 transition-all">{PROCESSING_STEPS[processingStep]}</p>
            </div>

            <div className="w-full max-w-xs">
              <ProgressBar progress={processingProgress} color="primary" />
            </div>

            <div className="space-y-1.5 w-full max-w-xs">
              {PROCESSING_STEPS.map((step, i) => (
                <div key={step} className={`flex items-center gap-2.5 text-xs transition-all ${i <= processingStep ? 'text-slate-700 dark:text-slate-300' : 'text-slate-300 dark:text-slate-600'}`}>
                  {i < processingStep ? (
                    <CheckCircle2 size={13} className="text-green-500 shrink-0" />
                  ) : i === processingStep ? (
                    <div className="w-3 h-3 rounded-full border-2 border-primary-500 border-t-transparent animate-spin shrink-0" />
                  ) : (
                    <div className="w-3 h-3 rounded-full border border-slate-200 dark:border-slate-700 shrink-0" />
                  )}
                  {step}
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Results */}
        {results && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-950/20 border border-green-100 dark:border-green-900/40 rounded-2xl">
              <CheckCircle2 size={18} className="text-green-600 dark:text-green-400 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-green-800 dark:text-green-300">Screening Complete</p>
                <p className="text-xs text-green-600 dark:text-green-400">AI analyzed {results.length} candidates. Results are ranked by match score.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {results.map((c, i) => (
                <motion.div
                  key={c.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.07 }}
                  className="card p-5 hover:shadow-card-hover transition-shadow"
                >
                  {/* Rank badge */}
                  <div className="flex items-start justify-between mb-4">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                      i === 0 ? 'bg-amber-50 text-amber-600 border border-amber-200' :
                      i === 1 ? 'bg-slate-100 text-slate-600 border border-slate-200' :
                      i === 2 ? 'bg-orange-50 text-orange-600 border border-orange-200' :
                      'bg-slate-50 text-slate-400 border border-slate-200'
                    } dark:bg-opacity-20 dark:border-opacity-30`}>
                      #{i + 1}
                    </div>
                    <MatchScoreRing score={c.matchScore} size={64} />
                  </div>

                  <div className="flex items-center gap-3 mb-3">
                    <CandidateAvatar name={c.name} size="sm" />
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-800 dark:text-slate-200 text-sm">{c.name}</p>
                      <p className="text-xs text-slate-500 truncate">{c.experience} exp.</p>
                    </div>
                  </div>

                  <RecommendationBadge recommendation={c.recommendation} />

                  <div className="mt-3 space-y-2">
                    <div>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1.5">Top Skills</p>
                      <div className="flex flex-wrap gap-1">
                        {c.skills.slice(0, 3).map(s => <SkillBadge key={s} skill={s} variant="success" size="xs" />)}
                      </div>
                    </div>
                    {c.missingSkills?.length > 0 && (
                      <div>
                        <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1.5">Missing</p>
                        <div className="flex flex-wrap gap-1">
                          {c.missingSkills.map(s => <SkillBadge key={s} skill={s} variant="missing" size="xs" />)}
                        </div>
                      </div>
                    )}
                    <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 pt-1">{c.aiSummary}</p>
                  </div>

                  <button
                    onClick={() => setSelectedCandidate(c)}
                    className="mt-4 w-full flex items-center justify-center gap-2 btn-secondary py-2 text-xs"
                  >
                    <Eye size={13} /> View Full Analysis
                  </button>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {selectedCandidate && (
        <CandidateDrawer
          candidate={selectedCandidate}
          onClose={() => setSelectedCandidate(null)}
          onUpdateStatus={() => {}}
        />
      )}
    </div>
  );
}
