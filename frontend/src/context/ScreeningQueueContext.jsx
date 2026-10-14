import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createJob as createJobApi } from '../services/api';
import { runBatchScreening, uploadJobDescription } from '../services/screeningApi';
import { mapEvaluationToScreeningResult } from '../utils/hrMappers';
import { nextAvailableJobTitle, duplicateJobDetail } from '../utils/jobTitle';
import {
  clearJobFiles,
  getJobFiles,
  hasJobFiles,
  setJobFiles,
} from '../utils/screeningQueueFiles';
import {
  loadScreeningQueue,
  saveScreeningQueue,
} from '../utils/screeningQueueStorage';
import { useApp } from './AppContext';
import { useAuth } from './AuthContext';

const ScreeningQueueContext = createContext(null);

function newJobId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `screen-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function prepareJdWhenProcessing(job, jobsCatalog) {
  if (job.jdMode === 'saved') {
    return { preparedJd: null, selectedJob: job.selectedJob || null };
  }

  let preparedJd = job.preparedJd || null;
  const { jdFile } = getJobFiles(job.id);

  if (!preparedJd) {
    if (job.jdMode === 'upload') {
      if (!jdFile) {
        throw new Error('JD file is missing. Re-add this job with the JD attached.');
      }
      preparedJd = await uploadJobDescription(jdFile);
    } else if (job.jdMode === 'paste') {
      const text = String(job.jdText || '').trim();
      if (!text) throw new Error('Pasted JD text is missing.');
      preparedJd = { jd_text: text };
    }
  }

  if (job.storeJd && preparedJd) {
    const parsed = preparedJd.parsed_jd || {};
    const parsedTitle = String(parsed.job_title || '').trim();
    const baseTitle = parsedTitle && parsedTitle !== 'Open Position' ? parsedTitle : 'Open Position';
    const required = parsed.required_skills?.normalized || parsed.required_skills?.raw || [];
    const preferred = parsed.preferred_skills?.normalized || parsed.preferred_skills?.raw || [];
    const skills = [...new Set([...(required || []), ...(preferred || [])].map(String))];
    const payload = {
      title: nextAvailableJobTitle(baseTitle, jobsCatalog),
      department: parsed.department || 'Hiring',
      location: parsed.location || 'India',
      description: preparedJd.jd_text || job.jdText || '',
      skills,
      jd_original_filename: preparedJd.original_filename,
      jd_file_url: preparedJd.stored_file_url,
      jd_text: preparedJd.jd_text || job.jdText || undefined,
      parsed_jd: preparedJd.parsed_jd,
      on_duplicate: 'rename',
    };
    try {
      await createJobApi(payload, { timeout: 120000 });
    } catch (error) {
      const dup = duplicateJobDetail(error);
      if (dup) {
        await createJobApi(
          {
            ...payload,
            title: nextAvailableJobTitle(dup.existing?.title || baseTitle, jobsCatalog),
            on_duplicate: 'rename',
          },
          { timeout: 120000 },
        );
      } else {
        throw error;
      }
    }
  }

  return { preparedJd, selectedJob: null };
}

export function ScreeningQueueProvider({ children }) {
  const { user } = useAuth();
  const { addToast, refreshData, setScreeningResults, jobs: catalogJobs } = useApp();
  const userId = user?.id || user?.email || null;

  const restoredRef = useRef(null);
  if (restoredRef.current?.userId !== userId) {
    restoredRef.current = { userId, ...loadScreeningQueue(userId) };
  }

  const [jobs, setJobs] = useState(() => restoredRef.current.jobs || []);
  const [panelOpen, setPanelOpen] = useState(() => Boolean(restoredRef.current.panelOpen));
  const activeJobIdRef = useRef(null);
  const jobsRef = useRef(jobs);
  jobsRef.current = jobs;
  const catalogRef = useRef(catalogJobs);
  catalogRef.current = catalogJobs;

  useEffect(() => {
    saveScreeningQueue(userId, { jobs, panelOpen });
  }, [userId, jobs, panelOpen]);

  useEffect(() => {
    const saved = loadScreeningQueue(userId);
    restoredRef.current = { userId, ...saved };
    setJobs(saved.jobs || []);
    setPanelOpen(Boolean(saved.panelOpen) && (saved.jobs || []).length > 0);
    activeJobIdRef.current = null;
  }, [userId]);

  const updateJob = useCallback((id, patch) => {
    setJobs((prev) =>
      prev.map((job) => (job.id === id ? { ...job, ...patch } : job)),
    );
  }, []);

  const enqueueScreeningJob = useCallback((payload) => {
    const id = newJobId();
    const resumeFiles = payload.resumeFiles || [];
    const jdFile = payload.jdFile || null;
    setJobFiles(id, { resumeFiles, jdFile });

    const job = {
      id,
      createdAt: Date.now(),
      label: payload.label || 'Screening job',
      resumeCount: resumeFiles.length,
      sendInviteEmail: payload.sendInviteEmail !== false,
      storeJd: Boolean(payload.storeJd),
      jdMode: payload.jdMode || 'saved',
      status: 'queued',
      progress: 'Waiting in queue…',
      results: [],
      failures: [],
      error: null,
      // Persistable JD inputs (File blobs live in screeningQueueFiles).
      preparedJd: null,
      selectedJob: payload.selectedJob || null,
      jdText: payload.jdText || '',
      hasLocalFiles: true,
    };
    setJobs((prev) => [...prev, job]);
    setPanelOpen(true);
    return id;
  }, []);

  const dismissJob = useCallback((id) => {
    clearJobFiles(id);
    setJobs((prev) => prev.filter((job) => job.id !== id));
  }, []);

  const clearFinished = useCallback(() => {
    const busy = jobsRef.current.some(
      (job) => job.status === 'queued' || job.status === 'processing',
    );
    if (busy || activeJobIdRef.current) return;
    setJobs((prev) => {
      const keep = [];
      for (const job of prev) {
        if (job.status === 'completed') {
          clearJobFiles(job.id);
          continue;
        }
        // Keep failed jobs so they remain visible for preview / retry.
        keep.push(job);
      }
      return keep;
    });
  }, []);

  const retryJob = useCallback((id) => {
    const job = jobsRef.current.find((row) => row.id === id);
    if (!job) return;
    if (job.status === 'queued' || job.status === 'processing') return;

    const filesOk =
      job.jdMode === 'saved'
        ? hasJobFiles(id)
        : hasJobFiles(id) || (job.jdMode === 'paste' && String(job.jdText || '').trim());

    if (job.jdMode === 'saved' && !job.selectedJob) {
      addToast('Cannot retry — saved job reference is missing. Add the screening again.', 'error');
      return;
    }
    if (job.jdMode !== 'paste' && !hasJobFiles(id) && job.jdMode !== 'saved') {
      addToast('Cannot retry — uploaded files were lost after refresh. Add the screening again.', 'error');
      return;
    }
    if (job.jdMode === 'saved' && !filesOk) {
      addToast('Cannot retry — resume files were lost after refresh. Add the screening again.', 'error');
      return;
    }
    if (job.jdMode === 'paste' && !String(job.jdText || '').trim()) {
      addToast('Cannot retry — pasted JD text is missing.', 'error');
      return;
    }
    if ((job.jdMode === 'paste' || job.jdMode === 'saved') && !hasJobFiles(id)) {
      addToast('Cannot retry — resume files were lost after refresh. Add the screening again.', 'error');
      return;
    }

    updateJob(id, {
      status: 'queued',
      progress: 'Waiting in queue… (retry)',
      error: null,
      failures: [],
      results: [],
      preparedJd: null,
      hasLocalFiles: hasJobFiles(id),
    });
    setPanelOpen(true);
    addToast(`Retry queued: ${job.label}`, 'success');
  }, [addToast, updateJob]);

  const processJob = useCallback(
    async (job) => {
      const files = getJobFiles(job.id);
      if (!files.resumeFiles?.length) {
        updateJob(job.id, {
          status: 'failed',
          progress: 'Incomplete',
          error:
            'Resume files are not available (often after a page refresh). Keep this entry for reference, or add the screening again.',
          hasLocalFiles: false,
        });
        return;
      }

      updateJob(job.id, {
        status: 'processing',
        progress: 'Preparing JD…',
        error: null,
      });

      try {
        const { preparedJd, selectedJob } = await prepareJdWhenProcessing(
          job,
          catalogRef.current || [],
        );

        updateJob(job.id, {
          preparedJd,
          progress: 'Screening resumes…',
        });

        if (job.storeJd) {
          await refreshData({ silent: true, force: true });
        }

        const batch = await runBatchScreening({
          resumeFiles: files.resumeFiles,
          jdFile: files.jdFile,
          jdText: job.jdText,
          selectedJob: selectedJob || job.selectedJob,
          preparedJd,
          sendInviteEmail: job.sendInviteEmail,
          onProgress: (current, total, name, stage) => {
            const label =
              stage === 'scoring'
                ? 'Scoring'
                : stage === 'uploading'
                  ? 'Uploading'
                  : 'Extracting';
            updateJob(job.id, {
              progress: `${label} ${current}/${total}: ${name}`,
            });
          },
        });

        const mapped = batch.results.map(({ extraction, result }, index) =>
          mapEvaluationToScreeningResult(result, extraction, index),
        );

        const failures = batch.failures || [];
        const alreadyScreened = failures.filter((item) =>
          /already been screened/i.test(String(item.message || '')),
        );
        const allBlocked =
          !mapped.length && failures.length > 0 && alreadyScreened.length === failures.length;

        // Success path clears files; all-blocked stays failed so Retry is not tempting
        // (re-upload of same person will fail again until candidate is deleted).
        if (!allBlocked) {
          clearJobFiles(job.id);
        }

        updateJob(job.id, {
          status: allBlocked ? 'failed' : 'completed',
          progress: allBlocked
            ? 'Already screened — blocked'
            : `Done · ${mapped.length} candidate(s)`,
          results: mapped,
          failures,
          error: allBlocked
            ? alreadyScreened.map((item) => item.message).join(' ')
            : null,
          hasLocalFiles: allBlocked ? hasJobFiles(job.id) : false,
          preparedJd,
        });
        if (mapped.length) {
          setScreeningResults(mapped);
          await refreshData({ silent: true, force: true });
        }

        if (failures.length) {
          if (alreadyScreened.length && !mapped.length) {
            addToast(
              alreadyScreened
                .map((item) => `${item.name}: ${item.message}`)
                .join('\n'),
              'error',
            );
          } else if (alreadyScreened.length) {
            addToast(
              `${job.label}: screened ${mapped.length} of ${job.resumeCount}. ` +
                alreadyScreened
                  .map((item) => `${item.name} already screened`)
                  .join('; ') +
                '.',
              'error',
            );
          } else {
            addToast(
              mapped.length
                ? `${job.label}: screened ${mapped.length} of ${job.resumeCount}. Some resumes failed.`
                : `${job.label}: screening finished with errors.`,
              'error',
            );
          }
        } else {
          addToast(
            `${job.label}: screening complete — ${mapped.length} candidate(s) saved.`,
            'success',
          );
        }
      } catch (error) {
        // Keep the job + files so the user can preview and retry.
        updateJob(job.id, {
          status: 'failed',
          progress: 'Failed — retry available',
          error: error?.message || 'Screening failed.',
          hasLocalFiles: hasJobFiles(job.id),
        });
        addToast(`${job.label}: ${error?.message || 'Screening failed.'}`, 'error');
      }
    },
    [addToast, refreshData, setScreeningResults, updateJob],
  );

  useEffect(() => {
    if (activeJobIdRef.current) return;
    const next = jobsRef.current.find((job) => {
      if (job.status !== 'queued') return false;
      return hasJobFiles(job.id) || (job.jdMode === 'paste' && job.jdText && hasJobFiles(job.id));
    });
    if (!next) return;
    if (!hasJobFiles(next.id)) return;
    activeJobIdRef.current = next.id;
    processJob(next).finally(() => {
      activeJobIdRef.current = null;
      setJobs((prev) => prev.slice());
    });
  }, [jobs, processJob]);

  const activeCount = useMemo(
    () => jobs.filter((j) => j.status === 'queued' || j.status === 'processing').length,
    [jobs],
  );
  const totalCount = jobs.length;

  const value = useMemo(
    () => ({
      jobs,
      panelOpen,
      setPanelOpen,
      activeCount,
      totalCount,
      enqueueScreeningJob,
      dismissJob,
      clearFinished,
      retryJob,
      canRetryJob: (job) => {
        if (!job || job.status === 'queued' || job.status === 'processing') return false;
        if (job.status !== 'failed' && job.status !== 'completed') return false;
        // Completed with partial failures can also retry if files remain.
        if (job.status === 'completed' && !hasJobFiles(job.id)) return false;
        if (job.jdMode === 'paste') {
          return Boolean(String(job.jdText || '').trim()) && hasJobFiles(job.id);
        }
        if (job.jdMode === 'saved') {
          return Boolean(job.selectedJob) && hasJobFiles(job.id);
        }
        return hasJobFiles(job.id);
      },
    }),
    [
      jobs,
      panelOpen,
      activeCount,
      totalCount,
      enqueueScreeningJob,
      dismissJob,
      clearFinished,
      retryJob,
    ],
  );

  return (
    <ScreeningQueueContext.Provider value={value}>
      {children}
    </ScreeningQueueContext.Provider>
  );
}

export function useScreeningQueue() {
  const ctx = useContext(ScreeningQueueContext);
  if (!ctx) {
    throw new Error('useScreeningQueue must be used within ScreeningQueueProvider');
  }
  return ctx;
}
