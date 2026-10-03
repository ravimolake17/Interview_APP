import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Plus, Briefcase, MapPin, Clock, Users, Pencil, Trash2, Search } from 'lucide-react';
import { useForm } from 'react-hook-form';
import Modal from '../../components/ui/Modal';
import DuplicateJobDialog from '../../components/ui/DuplicateJobDialog';
import { StatusBadge, SkillBadge } from '../../components/ui/Badges';
import FileUploader from '../../components/ui/FileUploader';
import EmptyState from '../../components/ui/EmptyState';
import { useApp } from '../../context/AppContext';
import LoadingSpinner from '../../components/LoadingSpinner';
import { matchesJob } from '../../utils/search';
import { uploadJobDescription } from '../../services/screeningApi';
import { checkJobDuplicate, getScreeningFileUrl } from '../../services/api';
import { duplicateJobDetail, nextAvailableJobTitle } from '../../utils/jobTitle';

function JobSkillsCell({ skills = [] }) {
  const [expanded, setExpanded] = useState(false);
  const extra = Math.max(0, skills.length - 3);
  const visible = expanded ? skills : skills.slice(0, 3);

  return (
    <div className={`flex flex-wrap gap-1 ${expanded ? 'max-w-xs' : 'max-w-48'}`}>
      {visible.map((s) => <SkillBadge key={s} skill={s} />)}
      {extra > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className="text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 underline-offset-2 hover:underline"
          title={expanded ? 'Show fewer skills' : 'Show all skills'}
        >
          {expanded ? 'Show less' : `+${extra}`}
        </button>
      )}
    </div>
  );
}

function applicantsForJob(job, candidates) {
  if (job.applicantList?.length) return job.applicantList;
  const key = String(job.title || '').trim().toLowerCase();
  return (candidates || [])
    .filter((c) => String(c.appliedJob || c.job_position || '').trim().toLowerCase() === key)
    .map((c) => ({
      candidate_id: c.candidateId || c.id,
      full_name: c.name || 'Candidate',
    }));
}

function JobApplicantsCell({ count, onOpen }) {
  if (!count) {
    return (
      <div className="flex items-center gap-1 text-muted">
        <Users size={12} />0
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-medium hover:underline"
      title="View applicants"
    >
      <Users size={12} />
      {count}
    </button>
  );
}

function TagInput({ value = [], onChange }) {
  const [input, setInput] = useState('');
  const addTag = () => {
    const t = input.trim();
    if (t && !value.includes(t)) { onChange([...value, t]); setInput(''); }
  };
  return (
    <div className="border border-col rounded-xl px-3 py-2 flex flex-wrap gap-2 min-h-[42px] focus-within:ring-2 focus-within:ring-blue-500/30 focus-within:border-blue-500 transition-all">
      {value.map((tag) => (
        <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 text-xs font-medium">
          {tag}
          <button type="button" onClick={() => onChange(value.filter((item) => item !== tag))} className="text-blue-400 hover:text-blue-600">×</button>
        </span>
      ))}
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(); } }}
        placeholder={value.length ? '' : 'Add skills, press Enter…'}
        className="flex-1 min-w-24 text-sm bg-transparent outline-none text-col placeholder:text-muted"
      />
    </div>
  );
}

function JobFormModal({ open, onClose, initialJob = null }) {
  const { addJob, updateJob, addToast, departments, jobs } = useApp();
  const { register, handleSubmit, reset, setValue, formState: { errors } } = useForm();
  const [skills, setSkills] = useState([]);
  const [jdMeta, setJdMeta] = useState(null);
  const [saving, setSaving] = useState(false);
  const [uploadingJd, setUploadingJd] = useState(false);
  const [duplicatePrompt, setDuplicatePrompt] = useState(null);
  const [pendingOnDuplicate, setPendingOnDuplicate] = useState('error');
  const isEdit = Boolean(initialJob?.id);

  useEffect(() => {
    if (!open) {
      setDuplicatePrompt(null);
      return;
    }
    if (initialJob) {
      reset({
        title: initialJob.title || '',
        department: initialJob.department || '',
        experience: initialJob.experience || '',
        location: initialJob.location || '',
        description: initialJob.description || '',
        status: initialJob.status || 'Active',
      });
      setSkills(initialJob.skills || []);
      setJdMeta({
        jdOriginalFilename: initialJob.jdOriginalFilename,
        jdFileUrl: initialJob.jdFileUrl,
        jdText: initialJob.jdText,
      });
    } else {
      reset({
        title: '',
        department: '',
        experience: '',
        location: 'India',
        description: '',
        status: 'Active',
      });
      setSkills([]);
      setJdMeta(null);
    }
    setPendingOnDuplicate('error');
    setDuplicatePrompt(null);
  }, [open, initialJob, reset]);

  const handleJdUpload = async (file) => {
    const jdFile = Array.isArray(file) ? file[0] : file;
    if (!jdFile) return;
    setUploadingJd(true);
    try {
      const payload = await uploadJobDescription(jdFile);
      const parsed = payload.parsed_jd || {};
      const required = parsed.required_skills?.normalized || parsed.required_skills?.raw || [];
      const preferred = parsed.preferred_skills?.normalized || parsed.preferred_skills?.raw || [];
      const mergedSkills = [...new Set([...(required || []), ...(preferred || [])].map(String))];
      const parsedTitle = String(parsed.job_title || '').trim();

      if (parsedTitle && parsedTitle !== 'Open Position') {
        setValue('title', parsedTitle);
      }
      if (!initialJob?.experience) {
        const min = parsed.minimum_experience_years;
        const max = parsed.maximum_experience_years;
        if (min != null && max != null) setValue('experience', `${min}–${max} years`);
        else if (min != null) setValue('experience', `${min}+ years`);
      }
      if (mergedSkills.length) setSkills(mergedSkills);
      if (payload.jd_text) setValue('description', payload.jd_text.slice(0, 4000));

      setJdMeta({
        jdOriginalFilename: payload.original_filename,
        jdFileUrl: payload.stored_file_url,
        jdText: payload.jd_text,
        parsedJd: payload.parsed_jd,
      });
      addToast('JD parsed — fields filled from the document.', 'success');
      if (!isEdit) {
        try {
          const check = await checkJobDuplicate({
            title: parsedTitle || undefined,
            jdFileUrl: payload.stored_file_url,
          });
          if (check.data?.duplicate && check.data.existing) {
            setDuplicatePrompt({
              existing: check.data.existing,
              reason: check.data.reason,
              suggestedTitle: nextAvailableJobTitle(parsedTitle || 'Open Position', jobs),
              payload: null,
            });
          }
        } catch {
          /* duplicate check is best-effort; submit still asks if needed */
        }
      }
    } catch (error) {
      addToast(error.message || 'Failed to parse JD.', 'error');
    } finally {
      setUploadingJd(false);
    }
  };

  const saveJob = async (payload, onDuplicate = 'error') => {
    if (isEdit) {
      await updateJob(initialJob.id, payload);
      addToast(`"${payload.title}" updated.`, 'success');
      return true;
    }
    try {
      await addJob({ ...payload, onDuplicate });
      addToast(
        onDuplicate === 'replace'
          ? `"${payload.title}" replaced the existing job.`
          : `"${payload.title}" created and saved to database.`,
        'success',
      );
      return true;
    } catch (error) {
      const dup = duplicateJobDetail(error);
      if (dup) {
        setDuplicatePrompt({
          existing: dup.existing,
          reason: dup.reason,
          suggestedTitle: nextAvailableJobTitle(payload.title, jobs),
          payload,
        });
        return false;
      }
      throw error;
    }
  };

  const onSubmit = async (data) => {
    setSaving(true);
    try {
      const payload = {
        ...data,
        skills,
        jdOriginalFilename: jdMeta?.jdOriginalFilename,
        jdFileUrl: jdMeta?.jdFileUrl,
        jdText: jdMeta?.jdText || data.description,
        parsedJd: jdMeta?.parsedJd,
      };
      const saved = await saveJob(payload, pendingOnDuplicate);
      if (saved) onClose();
    } catch (error) {
      addToast(error.response?.data?.detail || error.message || 'Failed to save job.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const inputCls = `w-full px-3 py-2 text-sm rounded-xl border border-col bg-transparent text-col placeholder:text-muted
    focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all`;
  const errCls = 'text-xs text-red-500 mt-1';

  return (
    <>
    <Modal open={open} onClose={onClose} title={isEdit ? 'Edit Job Posting' : 'Create Job Posting'} size="lg">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted mb-1.5 block">Job Title *</label>
            <input {...register('title', { required: 'Required' })} placeholder="e.g. Senior React Engineer" className={inputCls} />
            {errors.title && <p className={errCls}>{errors.title.message}</p>}
          </div>
          <div>
            <label className="text-xs font-medium text-muted mb-1.5 block">Department *</label>
            <select {...register('department', { required: 'Required' })} className={inputCls}>
              <option value="">Select department</option>
              {(departments || []).map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
            {!(departments || []).length && (
              <p className="text-xs text-muted mt-1">No departments for this company yet. Add them in SuperAdmin → Departments.</p>
            )}
            {errors.department && <p className={errCls}>{errors.department.message}</p>}
          </div>
          <div>
            <label className="text-xs font-medium text-muted mb-1.5 block">Experience Required</label>
            <input {...register('experience')} placeholder="e.g. 3-5 years" className={inputCls} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted mb-1.5 block">Location</label>
            <input {...register('location')} placeholder="e.g. Remote / Mumbai" className={inputCls} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted mb-1.5 block">Status</label>
            <select {...register('status')} className={inputCls}>
              <option value="Active">Active</option>
              <option value="Draft">Draft</option>
              <option value="Closed">Closed</option>
            </select>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-muted mb-1.5 block">Required Skills</label>
          <TagInput value={skills} onChange={setSkills} />
        </div>

        <div>
          <label className="text-xs font-medium text-muted mb-1.5 block">Job Description</label>
          <textarea
            {...register('description')}
            rows={4}
            placeholder="Describe the role, responsibilities, and requirements…"
            className={`${inputCls} resize-none`}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-muted mb-1.5 block">
            Upload JD (PDF/DOCX) {uploadingJd ? '— parsing…' : ''}
          </label>
          <FileUploader
            accept=".pdf,.doc,.docx"
            label="Upload Job Description"
            hint="Parsed fields will auto-fill title, skills, and description"
            onFiles={handleJdUpload}
          />
          {jdMeta?.jdOriginalFilename && (
            <p className="text-xs text-muted mt-2">
              Attached: {jdMeta.jdOriginalFilename}
              {jdMeta.jdFileUrl && (
                <>
                  {' · '}
                  <a
                    href={getScreeningFileUrl(jdMeta.jdFileUrl)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    open file
                  </a>
                </>
              )}
            </p>
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <button type="button" onClick={onClose} className="flex-1 px-4 py-2.5 rounded-xl border border-col text-sm font-medium text-col hover:bg-slate-50 dark:hover:bg-slate-800 transition-all">
            Cancel
          </button>
          <button type="submit" disabled={saving || uploadingJd} className="flex-1 btn-primary px-4 py-2.5 text-sm disabled:opacity-50">
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Job'}
          </button>
        </div>
      </form>
    </Modal>
    <DuplicateJobDialog
      open={Boolean(duplicatePrompt)}
      existing={duplicatePrompt?.existing}
      reason={duplicatePrompt?.reason}
      suggestedTitle={duplicatePrompt?.suggestedTitle}
      onCancel={() => setDuplicatePrompt(null)}
      onReplace={async () => {
        const prompt = duplicatePrompt;
        setDuplicatePrompt(null);
        if (prompt?.payload) {
          setSaving(true);
          try {
            const saved = await saveJob(prompt.payload, 'replace');
            if (saved) onClose();
          } catch (error) {
            addToast(error.response?.data?.detail || error.message || 'Failed to replace job.', 'error');
          } finally {
            setSaving(false);
          }
          return;
        }
        if (prompt?.existing?.title) setValue('title', prompt.existing.title);
        setPendingOnDuplicate('replace');
        addToast('Existing job will be replaced when you save.', 'info');
      }}
      onRename={async (title) => {
        if (!title) {
          addToast('Enter a new job title to rename this JD.', 'error');
          return;
        }
        const prompt = duplicatePrompt;
        setDuplicatePrompt(null);
        setValue('title', title);
        if (prompt?.payload) {
          setSaving(true);
          try {
            const saved = await saveJob({ ...prompt.payload, title }, 'rename');
            if (saved) onClose();
          } catch (error) {
            addToast(error.response?.data?.detail || error.message || 'Failed to save job.', 'error');
          } finally {
            setSaving(false);
          }
          return;
        }
        setPendingOnDuplicate('rename');
        addToast(`Will save as “${title}”.`, 'info');
      }}
    />
    </>
  );
}

export default function Jobs() {
  const { jobs, candidates, loadingData, removeJob, addToast } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [search, setSearch] = useState(() => searchParams.get('q') || '');
  const [filter, setFilter] = useState('All');
  const [deletingId, setDeletingId] = useState(null);
  const [applicantsJob, setApplicantsJob] = useState(null);
  const applicantRows = applicantsJob ? applicantsForJob(applicantsJob, candidates) : [];

  useEffect(() => {
    setSearch(searchParams.get('q') || '');
  }, [searchParams]);

  const handleSearchChange = (value) => {
    setSearch(value);
    if (value.trim()) {
      setSearchParams({ q: value.trim() });
    } else {
      setSearchParams({});
    }
  };

  const handleDelete = async (job) => {
    const linked = Number(job.applicants) || 0;
    if (linked > 0) {
      window.alert(
        `Cannot delete "${job.title}" while ${linked} candidate${linked === 1 ? ' is' : 's are'} linked. ` +
          'Remove or reassign candidates first.',
      );
      return;
    }
    if (!window.confirm(`Delete job "${job.title}"? This cannot be undone.`)) return;
    setDeletingId(job.id);
    try {
      await removeJob(job.id);
      addToast(`"${job.title}" deleted.`, 'success');
    } catch (error) {
      addToast(error.response?.data?.detail || 'Failed to delete job.', 'error');
    } finally {
      setDeletingId(null);
    }
  };

  const filtered = jobs.filter((j) => {
    const matchSearch = matchesJob(j, search);
    const matchFilter = filter === 'All' || j.status === filter;
    return matchSearch && matchFilter;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      {loadingData && !jobs.length ? (
        <LoadingSpinner message="Loading jobs from database..." />
      ) : (
      <>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-col">Job Postings</h2>
          <p className="text-sm text-muted">{jobs.length} roles saved in database (manual + JD screening)</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="btn-primary flex items-center gap-2 px-4 py-2.5 text-sm"
        >
          <Plus size={16} />
          Create Job
        </button>
      </div>

      <div className="card p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search jobs…"
            className="pl-9 pr-4 py-2 text-sm rounded-xl border border-col bg-transparent w-full text-col placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 transition-all"
          />
        </div>
        <div className="flex gap-2">
          {['All', 'Active', 'Draft', 'Closed'].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === s
                  ? 'bg-blue-600 text-white'
                  : 'text-muted hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="card">
          <EmptyState icon={Briefcase} title="No jobs found" description="Create a job manually in the Jobs tab with a JD upload." action={
            <button type="button" onClick={() => setCreateOpen(true)} className="btn-primary px-4 py-2 text-sm flex items-center gap-2 mx-auto">
              <Plus size={16} />Create Job
            </button>
          } />
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-col">
                  {['Job Title', 'Department', 'Experience', 'Location', 'Skills', 'Applicants', 'Status', 'Created', 'Actions'].map((h) => (
                    <th key={h} className="text-left px-5 py-3.5 text-xs font-semibold text-muted uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((job, i) => (
                  <motion.tr
                    key={job.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="border-b border-col last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-blue-100 dark:bg-blue-900/20 flex items-center justify-center flex-shrink-0">
                          <Briefcase size={14} className="text-blue-500" />
                        </div>
                        <span className="font-medium text-col">{job.title}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-muted">{job.department}</td>
                    <td className="px-5 py-4 text-muted whitespace-nowrap">
                      <div className="flex items-center gap-1"><Clock size={12} />{job.experience}</div>
                    </td>
                    <td className="px-5 py-4 text-muted whitespace-nowrap">
                      <div className="flex items-center gap-1"><MapPin size={12} />{job.location}</div>
                    </td>
                    <td className="px-5 py-4">
                      <JobSkillsCell skills={job.skills || []} />
                    </td>
                    <td className="px-5 py-4">
                      <JobApplicantsCell
                        count={job.applicants || 0}
                        onOpen={() => setApplicantsJob(job)}
                      />
                    </td>
                    <td className="px-5 py-4"><StatusBadge status={job.status} /></td>
                    <td className="px-5 py-4 text-muted whitespace-nowrap">{job.created}</td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setEditingJob(job)}
                          className="w-7 h-7 rounded-lg flex items-center justify-center text-muted hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all"
                          title="Edit"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(job)}
                          disabled={deletingId === job.id}
                          className="w-7 h-7 rounded-lg flex items-center justify-center text-muted hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all disabled:opacity-50"
                          title="Delete"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <JobFormModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <JobFormModal
        open={Boolean(editingJob)}
        initialJob={editingJob}
        onClose={() => setEditingJob(null)}
      />
      <Modal
        open={Boolean(applicantsJob)}
        onClose={() => setApplicantsJob(null)}
        title={applicantsJob ? `Applicants — ${applicantsJob.title}` : 'Applicants'}
        size="sm"
      >
        {applicantRows.length === 0 ? (
          <p className="text-sm text-muted">No candidates are linked to this job yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {applicantRows.map((person) => (
              <li key={person.candidate_id}>
                <Link
                  to={`/candidates/${person.candidate_id}`}
                  className="flex items-center justify-between gap-3 py-2.5 text-sm font-medium text-col hover:text-blue-600"
                  onClick={() => setApplicantsJob(null)}
                >
                  <span>{person.full_name}</span>
                  <span className="text-xs text-muted font-normal">Open dashboard →</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Modal>
      </>
      )}
    </div>
  );
}
