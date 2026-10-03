import axios from 'axios';
import { attachAuthInterceptors } from './api';

const screeningClient = axios.create({
  baseURL: '',
  timeout: 10 * 60 * 1000,
});

attachAuthInterceptors(screeningClient);

async function readError(error) {
  const detail = error.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ');
  return detail || error.message || 'Request failed.';
}

function appendJdFields(form, jdPayload, jdText) {
  if (jdPayload?.parsed_jd) {
    form.append('parsed_jd', JSON.stringify(jdPayload.parsed_jd));
    if (jdPayload.jd_text) form.append('jd_source_text', jdPayload.jd_text);
    if (jdPayload.original_filename) form.append('jd_original_filename', jdPayload.original_filename);
    if (jdPayload.stored_file_url) form.append('jd_file_url', jdPayload.stored_file_url);
    return;
  }
  const text = jdPayload?.jd_text || jdText;
  if (text) form.append('jd_text', text);
}

export async function extractResume(file) {
  const form = new FormData();
  form.append('file', file);
  try {
    const { data } = await screeningClient.post('/extract', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  } catch (error) {
    throw new Error(await readError(error));
  }
}

export async function enqueueResumeExtract(file, jdPayload, jdText, options = {}) {
  const form = new FormData();
  form.append('file', file);
  appendJdFields(form, jdPayload, jdText);
  form.append('send_invite_email', options.sendInviteEmail === false ? 'false' : 'true');
  try {
    const { data } = await screeningClient.post('/extract/async', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  } catch (error) {
    throw new Error(await readError(error));
  }
}

export async function uploadJobDescription(file) {
  const form = new FormData();
  form.append('file', file);
  try {
    const { data } = await screeningClient.post('/api/jd/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  } catch (error) {
    throw new Error(await readError(error));
  }
}

export async function enqueueEvaluation(payload) {
  try {
    const { data } = await screeningClient.post('/api/candidates/evaluate/async', payload);
    return data;
  } catch (error) {
    throw new Error(await readError(error));
  }
}

export async function getEvaluationJob(jobId) {
  try {
    const { data } = await screeningClient.get(`/api/candidates/evaluate/jobs/${jobId}`);
    return data;
  } catch (error) {
    throw new Error(await readError(error));
  }
}

export async function pollScreeningJob(jobId, { intervalMs = 2000, timeoutMs = 20 * 60 * 1000 } = {}) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const job = await getEvaluationJob(jobId);
    if (job.status === 'completed') return job;
    if (job.status === 'failed') {
      throw new Error(job.error || 'Screening job failed.');
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('Screening timed out. Please try again.');
}

export async function pollEvaluationJob(jobId, options) {
  const job = await pollScreeningJob(jobId, options);
  return job.result;
}

function extractionFromJob(job) {
  const extraction = job.extraction;
  if (!extraction?.parsed_data) {
    throw new Error('Resume extraction completed without parsed data.');
  }
  return {
    original_filename: extraction.original_filename,
    stored_file_url: extraction.stored_file_url,
    pages: extraction.pages || 0,
    parsed_data: extraction.parsed_data,
  };
}

export async function runScreening({ resumeFile, jdFile, jdText }) {
  let jdPayload = null;
  if (jdFile) {
    jdPayload = await uploadJobDescription(jdFile);
  }

  const queued = await enqueueResumeExtract(resumeFile, jdPayload, jdText);
  const extractJob = await pollScreeningJob(queued.job_id);
  const extraction = extractionFromJob(extractJob);
  const scoringId = extractJob.scoring_job_id || extractJob.extraction?.scoring_job_id;
  if (!scoringId) {
    throw new Error('Extraction finished but no scoring job was queued.');
  }
  const result = await pollEvaluationJob(scoringId);
  return { extraction, result };
}

export async function runBatchScreening({
  resumeFiles,
  jdFile,
  jdText,
  selectedJob,
  preparedJd,
  sendInviteEmail = true,
  onProgress,
}) {
  let jdPayload = preparedJd || null;
  if (!jdPayload && selectedJob) {
    if (selectedJob.parsedJd) {
      jdPayload = {
        parsed_jd: selectedJob.parsedJd,
        jd_text: selectedJob.jdText || undefined,
        original_filename: selectedJob.jdOriginalFilename || undefined,
        stored_file_url: selectedJob.jdFileUrl || undefined,
      };
    } else if (selectedJob.jdText?.trim()) {
      jdPayload = { jd_text: selectedJob.jdText.trim() };
    } else if (jdFile) {
      jdPayload = await uploadJobDescription(jdFile);
    } else if (jdText?.trim()) {
      jdPayload = { jd_text: jdText.trim() };
    } else {
      throw new Error('Selected job has no saved JD content. Upload or paste a JD instead.');
    }
  } else if (!jdPayload && jdFile) {
    jdPayload = await uploadJobDescription(jdFile);
  } else if (!jdPayload && !jdText?.trim()) {
    throw new Error('Please select a saved job or provide a job description.');
  }

  const results = [];
  const failures = [];
  const queuedExtracts = [];
  const total = resumeFiles.length;

  for (let index = 0; index < resumeFiles.length; index += 1) {
    const resumeFile = resumeFiles[index];
    onProgress?.(index + 1, total, resumeFile.name, 'uploading');
    try {
      const queued = await enqueueResumeExtract(resumeFile, jdPayload, jdText, {
        sendInviteEmail,
      });
      queuedExtracts.push({ jobId: queued.job_id, fileName: resumeFile.name });
    } catch (error) {
      failures.push({
        name: resumeFile.name,
        message: error instanceof Error ? error.message : 'Resume upload failed.',
      });
    }
  }

  const scoringJobs = [];
  for (let index = 0; index < queuedExtracts.length; index += 1) {
    const queued = queuedExtracts[index];
    onProgress?.(index + 1, queuedExtracts.length, queued.fileName, 'extracting');
    try {
      const extractJob = await pollScreeningJob(queued.jobId);
      const extraction = extractionFromJob(extractJob);
      const scoringJobId = extractJob.scoring_job_id || extractJob.extraction?.scoring_job_id;
      if (!scoringJobId) {
        throw new Error('Extraction finished but no scoring job was queued.');
      }
      scoringJobs.push({ extraction, scoringJobId, fileName: queued.fileName });
    } catch (error) {
      failures.push({
        name: queued.fileName,
        message: error instanceof Error ? error.message : 'Resume extraction failed.',
      });
    }
  }

  for (let index = 0; index < scoringJobs.length; index += 1) {
    const job = scoringJobs[index];
    onProgress?.(index + 1, scoringJobs.length, job.fileName, 'scoring');
    try {
      const result = await pollEvaluationJob(job.scoringJobId);
      results.push({ extraction: job.extraction, result, fileName: job.fileName });
    } catch (error) {
      failures.push({
        name: job.fileName,
        message: error instanceof Error ? error.message : 'Screening failed.',
      });
    }
  }

  if (!results.length && failures.length) {
    throw new Error(
      failures.map(({ name, message }) => `${name}: ${message}`).join('\n'),
    );
  }

  return { results, failures };
}
