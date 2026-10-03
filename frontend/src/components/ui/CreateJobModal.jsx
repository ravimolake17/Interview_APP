import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, Upload, Briefcase } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { useApp } from '../../context/AppContext';

export default function CreateJobModal({ isOpen, onClose, onSubmit }) {
  const { departments } = useApp();
  const departmentOptions = departments || [];
  const [skills, setSkills] = useState([]);
  const [skillInput, setSkillInput] = useState('');
  const [jdFile, setJdFile] = useState(null);

  const { register, handleSubmit, formState: { errors }, reset } = useForm();

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => {
      if (files[0]) setJdFile(files[0]);
    },
    accept: { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] },
    maxFiles: 1,
  });

  const addSkill = (e) => {
    if ((e.key === 'Enter' || e.key === ',') && skillInput.trim()) {
      e.preventDefault();
      const s = skillInput.trim().replace(/,$/, '');
      if (s && !skills.includes(s)) setSkills(prev => [...prev, s]);
      setSkillInput('');
    }
  };

  const removeSkill = (s) => setSkills(prev => prev.filter(x => x !== s));

  const handleFormSubmit = (data) => {
    onSubmit({ ...data, skills, jdFile });
    reset();
    setSkills([]);
    setJdFile(null);
    onClose();
    toast.success('Job created successfully!');
  };

  const handleClose = () => {
    reset();
    setSkills([]);
    setJdFile(null);
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            onClick={handleClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 16 }}
            transition={{ duration: 0.2 }}
            className="relative w-full max-w-xl card shadow-dropdown overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-100 dark:border-slate-800">
              <div className="w-8 h-8 rounded-xl bg-primary-100 dark:bg-primary-950/40 flex items-center justify-center">
                <Briefcase size={15} className="text-primary-600 dark:text-primary-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white">Create New Job</h3>
              <button onClick={handleClose} className="ml-auto btn-ghost p-1.5 rounded-lg">
                <X size={16} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit(handleFormSubmit)}>
              <div className="px-6 py-5 space-y-4 max-h-[65vh] overflow-y-auto scrollbar-thin">
                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="label">Job Title *</label>
                    <input
                      {...register('title', { required: 'Job title is required' })}
                      className="input"
                      placeholder="e.g. Senior Frontend Engineer"
                    />
                    {errors.title && <p className="text-xs text-red-500 mt-1">{errors.title.message}</p>}
                  </div>

                  <div>
                    <label className="label">Department *</label>
                    <select {...register('department', { required: 'Department is required' })} className="input">
                      <option value="">Select department</option>
                      {departmentOptions.map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                    {errors.department && <p className="text-xs text-red-500 mt-1">{errors.department.message}</p>}
                  </div>

                  <div>
                    <label className="label">Experience Required *</label>
                    <input
                      {...register('experience', { required: true })}
                      className="input"
                      placeholder="e.g. 5+ years"
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="label">Location</label>
                    <input
                      {...register('location')}
                      className="input"
                      placeholder="e.g. Remote, Mumbai, Hybrid"
                    />
                  </div>
                </div>

                {/* Skills */}
                <div>
                  <label className="label">Required Skills</label>
                  <div className="input flex flex-wrap gap-1.5 min-h-[42px] cursor-text" onClick={e => e.currentTarget.querySelector('input')?.focus()}>
                    {skills.map(s => (
                      <span key={s} className="inline-flex items-center gap-1 bg-primary-50 dark:bg-primary-950/30 text-primary-700 dark:text-primary-400 text-xs font-medium px-2 py-0.5 rounded-full">
                        {s}
                        <button type="button" onClick={() => removeSkill(s)} className="hover:text-red-500 transition-colors">
                          <X size={10} />
                        </button>
                      </span>
                    ))}
                    <input
                      type="text"
                      value={skillInput}
                      onChange={e => setSkillInput(e.target.value)}
                      onKeyDown={addSkill}
                      placeholder={skills.length === 0 ? 'Type a skill and press Enter…' : ''}
                      className="flex-1 min-w-[120px] bg-transparent border-none outline-none text-sm placeholder-slate-400"
                    />
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Press Enter or comma to add a skill</p>
                </div>

                {/* Description */}
                <div>
                  <label className="label">Job Description</label>
                  <textarea
                    {...register('description')}
                    className="input resize-none"
                    rows={4}
                    placeholder="Describe the role, responsibilities, and what success looks like…"
                  />
                </div>

                {/* JD Upload */}
                <div>
                  <label className="label">Upload Job Description (PDF/DOCX)</label>
                  <div
                    {...getRootProps()}
                    className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors ${
                      isDragActive
                        ? 'border-primary-400 bg-primary-50 dark:bg-primary-950/20'
                        : 'border-slate-200 dark:border-slate-700 hover:border-primary-300 dark:hover:border-primary-700 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                    }`}
                  >
                    <input {...getInputProps()} />
                    {jdFile ? (
                      <div className="flex items-center justify-center gap-2 text-sm text-primary-600 dark:text-primary-400">
                        <Upload size={14} />
                        <span className="font-medium">{jdFile.name}</span>
                        <button
                          type="button"
                          onClick={e => { e.stopPropagation(); setJdFile(null); }}
                          className="text-slate-400 hover:text-red-500 transition-colors"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="text-sm text-slate-500 dark:text-slate-400">
                        <Upload size={18} className="mx-auto mb-2 text-slate-400" />
                        <span className="font-medium text-slate-700 dark:text-slate-300">Drag & drop</span> or click to upload
                        <p className="text-xs text-slate-400 mt-0.5">PDF or DOCX up to 10MB</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex gap-3 px-6 py-4 border-t border-slate-100 dark:border-slate-800">
                <button type="button" onClick={handleClose} className="btn-secondary flex-1">Cancel</button>
                <button type="submit" className="btn-primary flex-1 flex items-center justify-center gap-2">
                  <Plus size={15} /> Create Job
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
