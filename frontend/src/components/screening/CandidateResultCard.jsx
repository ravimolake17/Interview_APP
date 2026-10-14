import { motion } from 'framer-motion';
import {
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
import { MatchScore, SkillBadge, RecommendationBadge, StatusBadge } from '../ui/Badges';
import { getScreeningFileUrl } from '../../services/api';

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

export function CandidateResultCard({ candidate: c, delay = 0 }) {
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

