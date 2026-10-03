import { CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { SkillBadge } from './Badges';

function SectionCard({ title, children }) {
  return (
    <div className="rounded-xl border border-col bg-slate-50/50 dark:bg-slate-800/30 overflow-hidden">
      <div className="px-4 py-2.5 border-b border-col bg-white/80 dark:bg-slate-900/40">
        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">{title}</h4>
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
  const displayValue = Number.isInteger(score) ? score : Number(score).toFixed(1);

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-1">
        <p className="text-sm text-col">{label}</p>
        <p className="text-sm font-semibold text-col">
          {displayValue}
          {hasMax ? <span className="text-xs font-normal text-muted"> / {max}</span> : null}
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

/**
 * Shared detailed evaluation sections used by Screening, HR Review, and Candidates drawer.
 * Accepts either a mapped screening/candidate object or buildEvaluationDetailFromSnapshot() output.
 */
export default function EvaluationDetailPanels({ data }) {
  if (!data) return null;

  const skills = data.skills || data.matched_skills || [];
  const missingSkills = data.missingSkills || data.missing_skills || [];
  const partialSkills = data.partialSkills || data.partial_skills || [];
  const responsibilityMatches = data.responsibilityMatches || data.responsibility_matches || [];
  const strengths = data.strengths || [];
  const concerns = data.concerns || [];
  const scoreBreakdown = data.scoreBreakdown || [];
  const experienceAssessment = data.experienceAssessment || null;
  const certifications = data.certifications || [];

  return (
    <div className="space-y-5">
      {scoreBreakdown.length > 0 && (
        <SectionCard title="Score breakdown">
          <div className="space-y-3">
            {scoreBreakdown.map((row) => (
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

      {experienceAssessment && (
        <SectionCard title="JD-relevant experience match">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
            <div>
              <p className="text-xs text-muted mb-1">JD requirement</p>
              <p className="text-sm font-medium text-col">{experienceAssessment.jdRequirement}</p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Professional experience</p>
              <p className="text-sm font-medium text-col">
                {experienceAssessment.professionalYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Relevant internship</p>
              <p className="text-sm font-medium text-col">
                {experienceAssessment.internshipYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Relevant projects</p>
              <p className="text-sm font-medium text-col">
                {experienceAssessment.projectYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Total relevant (professional)</p>
              <p className="text-sm font-medium text-col">
                {experienceAssessment.professionalYears || experienceAssessment.relevantYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Supporting exposure (intern/projects)</p>
              <p className="text-sm font-medium text-col">
                {experienceAssessment.supportingYears || '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted mb-1">Years toward JD requirement</p>
              <p className="text-sm font-medium text-col">
                {experienceAssessment.yearsTowardRequirement || '—'}
                {experienceAssessment.requirementKind
                  ? ` (${String(experienceAssessment.requirementKind).replace(/_/g, ' ')})`
                  : ''}
              </p>
            </div>
            <div className="sm:col-span-2 lg:col-span-3">
              <p className="text-xs text-muted mb-1">Experience result</p>
              <p className="text-sm font-medium text-col">{experienceAssessment.result}</p>
            </div>
          </div>

          {experienceAssessment.counted?.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Counted experience</p>
              <ul className="space-y-1.5 text-sm text-col">
                {experienceAssessment.counted.map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {experienceAssessment.excluded?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                Excluded from relevant experience
              </p>
              <ul className="space-y-1.5 text-sm text-col">
                {experienceAssessment.excluded.map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <XCircle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {experienceAssessment.skillExperience?.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                Skill-specific experience
              </p>
              <ul className="space-y-2.5 text-sm text-col">
                {experienceAssessment.skillExperience.map((item) => (
                  <li key={`${item.skill}-${item.sourceText}`} className="border-b border-col last:border-0 pb-2 last:pb-0">
                    <p className="font-medium">{item.skill}</p>
                    <p className="text-xs text-muted mt-0.5">
                      {item.supportedYears || '0 yrs'} supported
                      {item.explicitYears ? ` · ${item.explicitYears} explicit` : ''}
                      {item.strongYears ? ` · ${item.strongYears} strong` : ''}
                      {item.evidenceKind ? ` · ${String(item.evidenceKind).replace(/_/g, ' ')}` : ''}
                      {item.meetsMinimum === true ? ' · PASS' : ''}
                      {item.meetsMinimum === false ? ' · FAIL' : ''}
                    </p>
                    {item.reason ? <p className="text-xs mt-1">{item.reason}</p> : null}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </SectionCard>
      )}

      <div className="grid sm:grid-cols-2 gap-4">
        <SectionCard title="Matched skills">
          {skills.length ? (
            <div className="flex flex-wrap gap-1.5">
              {skills.map((skill) => (
                <SkillBadge key={skill} skill={skill} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No matched skills.</p>
          )}
        </SectionCard>
        <SectionCard title="Missing skills">
          {missingSkills.length ? (
            <div className="flex flex-wrap gap-1.5">
              {missingSkills.map((skill) => (
                <SkillBadge key={skill} skill={skill} missing />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No missing skills.</p>
          )}
        </SectionCard>
      </div>

      {partialSkills.length > 0 && (
        <SectionCard title="Partial skill matches">
          <div className="flex flex-wrap gap-1.5">
            {partialSkills.map((skill) => (
              <SkillBadge key={skill} skill={skill} />
            ))}
          </div>
        </SectionCard>
      )}

      {responsibilityMatches.length > 0 && (
        <SectionCard title="JD responsibility match">
          <ul className="space-y-2.5 text-sm text-col">
            {responsibilityMatches.map((item) => {
              const status = item.match_status || item.matchStatus || 'UNSUPPORTED';
              const evidence = item.evidence || [];
              return (
                <li key={item.jd_responsibility || item.jdResponsibility} className="border-b border-col last:border-0 pb-2 last:pb-0">
                  <p className="font-medium">
                    {item.jd_responsibility || item.jdResponsibility}
                  </p>
                  <p className="text-xs text-muted mt-0.5">
                    {status}
                    {item.priority ? ` · ${item.priority}` : ''}
                    {item.confidence != null ? ` · ${Math.round(Number(item.confidence) * 100)}%` : ''}
                  </p>
                  {item.reason ? <p className="text-xs mt-1">{item.reason}</p> : null}
                  {evidence.length > 0 ? (
                    <p className="text-xs text-muted mt-1">Evidence: {evidence.join(' | ')}</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </SectionCard>
      )}

      {(strengths.length > 0 || concerns.length > 0) && (
        <div className="grid sm:grid-cols-2 gap-4">
          {strengths.length > 0 && (
            <SectionCard title="Strengths">
              <ul className="space-y-1.5 text-sm text-col">
                {strengths.map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}
          {concerns.length > 0 && (
            <SectionCard title="Concerns">
              <ul className="space-y-1.5 text-sm text-col">
                {concerns.map((item) => (
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

      <div className="grid sm:grid-cols-2 gap-4">
        <SectionCard title="Education">
          <p className="text-sm text-col leading-relaxed">{data.education || 'Not extracted'}</p>
          {certifications.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-muted mb-1.5">Certifications</p>
              <div className="flex flex-wrap gap-1.5">
                {certifications.map((item) => (
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
        <SectionCard title="Experience summary">
          <p className="text-sm text-col leading-relaxed">{data.experience || 'Not extracted'}</p>
          {(data.requiredMatchRatio != null || data.preferredMatchRatio != null) && (
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <p className="text-xs text-muted mb-0.5">Required skill match</p>
                <p className="text-lg font-bold text-col">{data.requiredMatchRatio ?? 0}%</p>
              </div>
              <div>
                <p className="text-xs text-muted mb-0.5">Preferred skill match</p>
                <p className="text-lg font-bold text-col">{data.preferredMatchRatio ?? 0}%</p>
              </div>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
