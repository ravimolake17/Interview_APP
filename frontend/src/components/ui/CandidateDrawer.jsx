import { motion, AnimatePresence } from 'framer-motion';
import { X, Download, UserCheck, UserX, Mail, Phone, Briefcase, GraduationCap, Star, AlertTriangle, ChevronRight } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  CandidateAvatar, MatchScoreRing, MatchScoreBar,
  SkillBadge, StatusBadge, RecommendationBadge, Divider
} from './index';

export default function CandidateDrawer({ candidate, onClose, onUpdateStatus }) {
  if (!candidate) return null;

  const handleShortlist = () => {
    onUpdateStatus(candidate.id, 'shortlisted');
    toast.success(`${candidate.name} shortlisted!`);
  };

  const handleReject = () => {
    onUpdateStatus(candidate.id, 'rejected');
    toast.error(`${candidate.name} marked as rejected.`);
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-40 flex">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="flex-1 bg-black/20 dark:bg-black/50 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Drawer */}
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 28, stiffness: 280 }}
          className="w-[480px] h-full bg-white dark:bg-slate-900 shadow-2xl flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <CandidateAvatar name={candidate.name} size="md" />
              <div>
                <h3 className="font-semibold text-slate-900 dark:text-white text-sm">{candidate.name}</h3>
                <p className="text-xs text-slate-500 flex items-center gap-1">
                  <Briefcase size={11} /> {candidate.appliedJob}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="btn-ghost p-2 rounded-xl">
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-5 space-y-5">
            {/* Score + Recommendation */}
            <div className="flex items-center gap-5">
              <MatchScoreRing score={candidate.matchScore} size={80} />
              <div className="flex-1 space-y-2">
                <RecommendationBadge recommendation={candidate.recommendation} />
                <StatusBadge status={candidate.status} />
                <p className="text-xs text-slate-500">{candidate.experience} experience</p>
              </div>
            </div>

            {/* Contact */}
            <div className="card p-4 space-y-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Contact</p>
              <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <Mail size={14} className="text-slate-400 shrink-0" />
                <a href={`mailto:${candidate.email}`} className="hover:text-primary-600 transition-colors">{candidate.email}</a>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <Phone size={14} className="text-slate-400 shrink-0" />
                <span>{candidate.phone}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <GraduationCap size={14} className="text-slate-400 shrink-0" />
                <span>{candidate.education}</span>
              </div>
            </div>

            {/* AI Summary */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                <Star size={12} className="text-amber-400" /> AI Summary
              </h4>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed bg-amber-50/50 dark:bg-amber-950/10 border border-amber-100 dark:border-amber-900/30 rounded-xl p-3.5">
                {candidate.aiSummary}
              </p>
            </div>

            {/* Match Scores */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Match Analysis</h4>
              <MatchScoreBar score={candidate.matchScore} label="Overall Match" />
              <MatchScoreBar score={Math.min(100, candidate.matchScore + 5)} label="Skills Match" />
              <MatchScoreBar score={Math.max(0, candidate.matchScore - 8)} label="Experience" />
              <MatchScoreBar score={candidate.matchScore + 3 > 100 ? 97 : candidate.matchScore + 3} label="Education" />
            </div>

            <Divider />

            {/* Skills */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Matched Skills</h4>
              <div className="flex flex-wrap gap-1.5">
                {candidate.skills.map(s => <SkillBadge key={s} skill={s} variant="success" />)}
              </div>
            </div>

            {candidate.missingSkills?.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                  <AlertTriangle size={12} className="text-amber-400" /> Missing Skills
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.missingSkills.map(s => <SkillBadge key={s} skill={s} variant="missing" />)}
                </div>
              </div>
            )}

            {/* Experience & Education Analysis */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Experience Analysis</h4>
              <div className="text-sm text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 rounded-xl p-3.5">
                <div className="flex items-start gap-2">
                  <ChevronRight size={14} className="text-primary-500 mt-0.5 shrink-0" />
                  <p>{candidate.experienceAnalysis}</p>
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Education Analysis</h4>
              <div className="text-sm text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 rounded-xl p-3.5">
                <div className="flex items-start gap-2">
                  <ChevronRight size={14} className="text-primary-500 mt-0.5 shrink-0" />
                  <p>{candidate.educationAnalysis}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={handleShortlist}
                disabled={candidate.status === 'shortlisted'}
                className="flex items-center justify-center gap-2 btn-primary py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <UserCheck size={15} /> Shortlist
              </button>
              <button
                onClick={handleReject}
                disabled={candidate.status === 'rejected'}
                className="flex items-center justify-center gap-2 btn-danger py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <UserX size={15} /> Reject
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button className="flex items-center justify-center gap-2 btn-secondary py-2 text-xs">
                <Download size={13} /> Resume
              </button>
              <button className="flex items-center justify-center gap-2 btn-secondary py-2 text-xs">
                <Download size={13} /> Report
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
