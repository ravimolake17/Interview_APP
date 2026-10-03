const AVATAR_COLORS = ['#7C3AED', '#0891B2', '#059669', '#D97706', '#DB2777', '#2563EB'];

function avatarColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export function mapStatusFromBackend(status) {
  const map = {
    NEEDS_REVIEW: 'Pending',
    SHORTLISTED: 'Shortlisted',
    REJECTED: 'Rejected',
    INTERVIEW_SCHEDULED: 'Interview Scheduled',
    INTERVIEW_COMPLETED: 'Interview Completed',
    PENDING: 'Pending',
  };
  return map[status] || status;
}

export function mapInterviewResult(value) {
  const key = String(value || '').trim().toUpperCase();
  const map = {
    HIRE: 'Hire',
    CONSIDER: 'Consider',
    REJECT: 'Reject',
    HOLD: 'Hold',
  };
  return map[key] || null;
}

export function recommendationFromScore(score) {
  if (score >= 85) return 'Highly Recommended';
  if (score >= 70) return 'Recommended';
  if (score >= 55) return 'Consider';
  return 'Not Recommended';
}

function parseExperienceYears(candidate, snapshot = {}) {
  const parsed = snapshot.parsed_resume || {};
  const breakdown = snapshot.score_breakdown || {};
  const exp = breakdown.experience_assessment || snapshot.experience_assessment || {};
  const raw = [
    parsed.total_experience_years,
    exp.candidate_total_experience_years,
    snapshot.candidate_experience_years,
  ].find((value) => value != null && value !== '');
  const numeric = Number(raw);
  if (Number.isFinite(numeric) && numeric >= 0) return numeric;
  const match = String(candidate.experience_summary || candidate.experience || '').match(/(\d+(?:\.\d+)?)\s*yrs/i);
  if (match) return Number(match[1]);
  return null;
}

function formatYears(value) {
  if (value == null || value === '') return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return null;
  return `${numeric}`;
}

function mapSkillExperienceAssessments(experienceAssessment = {}) {
  return asList(experienceAssessment.skill_experience_assessments).map((item) => ({
    skill: item.skill_or_domain || item.skillOrDomain || '',
    sourceText: item.source_text || item.sourceText || '',
    supportedYears: formatYearsLabel(item.supported_years ?? item.supportedYears),
    explicitYears: formatYearsLabel(item.explicit_dated_years ?? item.explicitDatedYears),
    strongYears: formatYearsLabel(item.strong_dated_years ?? item.strongDatedYears),
    evidenceKind: item.evidence_kind || item.evidenceKind || 'NO_EVIDENCE',
    meetsMinimum: item.meets_minimum ?? item.meetsMinimum,
    reason: item.reason || '',
  }));
}

function isValidEducationLine(text) {
  const value = String(text || '').replace(/^#+\s*/, '').trim();
  if (!value || value.length > 400) return false;
  if (/^(education|academic qualifications?|qualification)$/i.test(value)) return false;
  return true;
}

function skillDedupeKey(skill) {
  return String(skill || '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[\s_\-/|,;]+/g, ' ')
    .replace(/\((?:advanced|intermediate|beginner|preferred|required)\)/g, '')
    .trim();
}

function uniqueSkills(skills) {
  const seen = new Set();
  const output = [];
  const list = Array.isArray(skills) ? skills.filter(Boolean) : skills ? [skills] : [];
  list.forEach((skill) => {
    const key = skillDedupeKey(skill);
    if (!key || seen.has(key)) return;
    seen.add(key);
    output.push(skill);
  });
  return output;
}

function summarizeExperienceEntries(entries, limit = 2) {
  if (!Array.isArray(entries) || entries.length === 0) return null;
  const lines = entries.slice(0, limit).map((entry) => {
    const role = entry.role || entry.job_title || 'Role';
    const company = entry.company || '';
    const years = formatYears(entry.duration_years);
    let line = role;
    if (company) line += ` @ ${company}`;
    if (years) line += ` (${years} yrs)`;
    return line;
  });
  return lines.join(' · ');
}

export function extractExperienceFromSnapshot(snapshot = {}, breakdown = {}) {
  const parsedResume = snapshot.parsed_resume || {};
  const entries = parsedResume.experience_entries || [];

  const entrySummary = summarizeExperienceEntries(entries);
  if (entrySummary) return entrySummary;

  const exp = breakdown.experience_assessment || snapshot.experience_assessment || {};
  const total =
    parsedResume.total_experience_years ??
    exp.candidate_total_experience_years ??
    snapshot.candidate_experience_years;
  const totalText = formatYears(total);
  if (totalText) return `${totalText} yrs total`;

  const relevant = exp.candidate_relevant_experience_years ?? snapshot.candidate_relevant_experience_years;
  const relevantText = formatYears(relevant);
  if (relevantText) return `${relevantText} yrs relevant`;

  if (entries.length > 0) {
    return `${entries.length} role${entries.length !== 1 ? 's' : ''} listed`;
  }

  return null;
}

export function extractEducationFromSnapshot(snapshot = {}) {
  const education = snapshot.candidate_education;
  if (Array.isArray(education) && education.length > 0) {
    const cleaned = education.map((item) => String(item).trim()).filter(isValidEducationLine).slice(0, 2);
    if (cleaned.length > 0) return cleaned.join(' · ');
  }

  const parsedEducation = snapshot.parsed_resume?.education;
  if (Array.isArray(parsedEducation) && parsedEducation.length > 0) {
    const cleaned = parsedEducation.map((item) => String(item).trim()).filter(isValidEducationLine).slice(0, 2);
    if (cleaned.length > 0) return cleaned.join(' · ');
  }

  return null;
}

function getInitials(name = '') {
  return String(name || '?')
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

export function buildEvaluationDetailFromSnapshot(snapshot = {}, overrides = {}) {
  const breakdown = snapshot.score_breakdown || {};
  const experienceAssessment =
    snapshot.experience_assessment || breakdown.experience_assessment || {};
  const match = snapshot.match_analysis || {};
  const jd = snapshot.extracted_jd_requirements || {};
  const weights = breakdown.score_weights || {};
  const parsedResume = snapshot.parsed_resume || {};

  const scoreBreakdown = [
    { label: 'Required skills', value: breakdown.required_skill_score, weight: weights.required_skills },
    { label: 'Preferred skills', value: breakdown.preferred_skill_score, weight: weights.preferred_skills },
    { label: 'Experience', value: breakdown.experience_score, weight: weights.experience },
    { label: 'Education', value: breakdown.education_score, weight: weights.education_certification },
    { label: 'Keywords', value: breakdown.keyword_score, weight: weights.keywords },
    { label: 'Responsibilities', value: breakdown.responsibility_score, weight: weights.responsibilities ?? weights.keywords },
  ].filter((row) => row.value != null);

  const education =
    overrides.education ||
    extractEducationFromSnapshot({
      candidate_education: snapshot.candidate_education || overrides.candidate_education,
      parsed_resume: parsedResume,
    }) ||
    asList(snapshot.candidate_education).filter(isValidEducationLine).slice(0, 3).join(' · ') ||
    asList(parsedResume.education).filter(isValidEducationLine).slice(0, 3).join(' · ') ||
    'Not extracted';

  const experienceSummary =
    overrides.experience ||
    extractExperienceFromSnapshot(snapshot, breakdown) ||
    formatYearsLabel(experienceAssessment.candidate_total_experience_years);

  return {
    skills: uniqueSkills(overrides.matched_skills || breakdown.matched_skills),
    missingSkills: uniqueSkills(overrides.missing_skills || breakdown.missing_skills),
    partialSkills: uniqueSkills(match.partial_required_skills || breakdown.partial_skills),
    responsibilityMatches: asList(breakdown.responsibility_matches),
    strengths: asList(overrides.strengths || breakdown.strengths),
    concerns: asList(overrides.concerns || breakdown.concerns),
    certifications: asList(snapshot.candidate_certifications || parsedResume.certifications),
    education,
    experience: experienceSummary === '—' ? 'Not extracted' : experienceSummary,
    summary:
      overrides.final_recommendation ||
      snapshot.final_recommendation ||
      breakdown.recommendation ||
      'No AI summary available yet.',
    scoreBreakdown,
    experienceAssessment: {
      jdRequirement: experienceAssessment.jd_requirement || 'Not specified',
      totalYears: formatYearsLabel(experienceAssessment.candidate_total_experience_years),
      relevantYears: formatYearsLabel(experienceAssessment.candidate_relevant_experience_years),
      professionalYears: formatYearsLabel(experienceAssessment.professional_experience_years),
      internshipYears: formatYearsLabel(experienceAssessment.internship_experience_years),
      researchYears: formatYearsLabel(experienceAssessment.research_experience_years),
      projectYears: formatYearsLabel(experienceAssessment.academic_project_years),
      // Full hands-on pool (professional + intern + projects) — used for hands-on JD kinds.
      handsOnYears: formatYearsLabel(
        experienceAssessment.relevant_hands_on_experience_years ??
          experienceAssessment.candidate_relevant_experience_years
      ),
      // Internship + projects + research only (never added into total relevant).
      supportingYears: formatYearsLabel(
        experienceAssessment.supporting_exposure_years ??
          (
            Number(experienceAssessment.internship_experience_years || 0) +
            Number(experienceAssessment.academic_project_years || 0) +
            Number(experienceAssessment.research_experience_years || 0)
          )
      ),
      yearsTowardRequirement: formatYearsLabel(
        experienceAssessment.years_toward_requirement
      ),
      requirementKind: experienceAssessment.experience_requirement_kind || 'professional',
      allowsInternship: Boolean(experienceAssessment.allows_internship_for_requirement),
      unrelatedYears: formatYearsLabel(experienceAssessment.unrelated_experience_years),
      meetsMinimum: experienceAssessment.meets_minimum,
      result: experienceAssessment.result || 'No experience result available.',
      counted: asList(experienceAssessment.counted_experience).map(formatExperienceEntry),
      excluded: asList(experienceAssessment.excluded_experience).map(formatExperienceEntry),
      skillExperience: mapSkillExperienceAssessments(experienceAssessment),
    },
    hardRequirementStatus: breakdown.hard_requirement_status || 'N/A',
    hardRequirementReasons: asList(breakdown.hard_requirement_reasons),
    jobTitle: jd.job_title || overrides.job_position || 'Not specified',
    requiredMatchRatio: Math.round(Number(match.required_match_ratio || 0) * 100),
    preferredMatchRatio: Math.round(Number(match.preferred_match_ratio || 0) * 100),
  };
}

export function mapCandidateFromBackend(candidate, detail = null) {
  const snapshot = detail?.evaluation_snapshot || candidate.evaluation_snapshot || {};
  const breakdown = snapshot.score_breakdown || {};
  const score = Math.round(candidate.resume_score || breakdown.overall_score || 0);
  const name = candidate.full_name || 'Candidate';
  const evaluation = buildEvaluationDetailFromSnapshot(snapshot, {
    matched_skills: detail?.matched_skills,
    missing_skills: detail?.missing_skills,
    strengths: detail?.strengths,
    concerns: detail?.concerns,
    final_recommendation: detail?.final_recommendation,
    education: candidate.education_summary || detail?.education_summary,
    experience: candidate.experience_summary || detail?.experience_summary,
    job_position: candidate.job_position,
    candidate_education: detail?.candidate_education,
  });

  const status =
    candidate.status === 'INTERVIEW_COMPLETED' || candidate.interview_completed
      ? 'Interview Completed'
      : candidate.status === 'INTERVIEW_SCHEDULED' || candidate.interview_scheduled
      ? 'Interview Scheduled'
      : mapStatusFromBackend(candidate.status);

  return {
    id: candidate.candidate_id,
    candidateId: candidate.candidate_id,
    companyId: candidate.company_id ?? null,
    name,
    email: candidate.email || '',
    phone: candidate.phone || '—',
    appliedJob: candidate.job_position || 'Open Role',
    matchScore: Number.isFinite(score) ? score : 0,
    status,
    backendStatus: candidate.status,
    avatar: getInitials(name),
    avatarColor: avatarColor(name),
    skills: evaluation.skills,
    missingSkills: evaluation.missingSkills,
    partialSkills: evaluation.partialSkills,
    responsibilityMatches: evaluation.responsibilityMatches,
    strengths: evaluation.strengths,
    concerns: evaluation.concerns,
    certifications: evaluation.certifications,
    summary: evaluation.summary,
    recommendation: recommendationFromScore(score),
    education: evaluation.education,
    experience: evaluation.experience,
    experienceYears: parseExperienceYears(candidate, snapshot),
    experienceMatch:
      evaluation.missingSkills.length === 0
        ? 'Strong'
        : evaluation.missingSkills.length <= 1
          ? 'Good'
          : 'Moderate',
    educationMatch: 'Good',
    scoreBreakdown: evaluation.scoreBreakdown,
    experienceAssessment: evaluation.experienceAssessment,
    jobTitle: evaluation.jobTitle,
    requiredMatchRatio: evaluation.requiredMatchRatio,
    preferredMatchRatio: evaluation.preferredMatchRatio,
    createdAt: candidate.created_at,
    resumeFileUrl: candidate.resume_file_url,
    jdFileUrl: candidate.jd_file_url,
    jdOriginalFilename: candidate.jd_original_filename,
    resumeOriginalFilename: candidate.resume_original_filename,
    interviewScheduled: candidate.interview_scheduled,
    interviewCompleted: candidate.interview_completed,
    interviewResult: mapInterviewResult(candidate.interview_result),
    interviewResultKey: String(candidate.interview_result || '').toUpperCase() || null,
    inviteUsed: candidate.invite_used ?? detail?.invite_used ?? false,
    inviteSent: candidate.invite_sent ?? false,
    canResendInvite: candidate.can_resend_invite,
    scheduledDate: detail?.scheduled_date ?? candidate.scheduled_date ?? null,
    scheduledTime: detail?.scheduled_time ?? candidate.scheduled_time ?? null,
    meetingLink: detail?.meeting_link ?? candidate.meeting_link ?? null,
    joinLink: detail?.join_link ?? snapshot?.agent5?.join_link ?? null,
    calendarEventId: detail?.calendar_event_id ?? candidate.calendar_event_id ?? null,
    evaluationSnapshot: snapshot,
  };
}

export function buildJobsFromCandidates(candidates) {
  const grouped = new Map();

  candidates.forEach((candidate) => {
    const title = (candidate.job_position || 'Unassigned Role').trim() || 'Unassigned Role';
    const existing = grouped.get(title) || {
      id: title,
      title,
      department: 'Hiring',
      experience: 'As per JD',
      location: 'India',
      skills: [],
      applicants: 0,
      status: 'Active',
      created: candidate.created_at?.slice(0, 10) || new Date().toISOString().slice(0, 10),
      jdOriginalFilename: candidate.jd_original_filename,
    };

    existing.applicants += 1;
  if (candidate.jd_original_filename) {
      existing.jdOriginalFilename = candidate.jd_original_filename;
    }
    grouped.set(title, existing);
  });

  return Array.from(grouped.values()).sort((a, b) => b.applicants - a.applicants);
}

export function mapAuditToActivity(entry) {
  const actionMap = {
    USER_LOGIN: { icon: 'check', text: entry.message || `${entry.user_email} signed in` },
    RESUME_EVALUATED: { icon: 'bot', text: entry.message || 'Resume evaluated' },
    CANDIDATE_SHORTLISTED: { icon: 'check', text: entry.message || 'Candidate shortlisted' },
    CANDIDATE_REJECTED: { icon: 'x', text: entry.message || 'Candidate rejected' },
    INVITE_RESENT: { icon: 'briefcase', text: entry.message || 'Invite resent' },
    USER_CREATED: { icon: 'check', text: entry.message || 'User created' },
    USER_UPDATED: { icon: 'check', text: entry.message || 'User updated' },
  };
  const mapped = actionMap[entry.action] || { icon: 'bot', text: entry.message || entry.action };
  return {
    id: entry.id,
    icon: mapped.icon,
    text: mapped.text,
    time: new Date(entry.created_at).toLocaleString(),
  };
}

function asList(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (value == null || value === '') return [];
  return [value];
}

function formatYearsLabel(value) {
  if (value == null || value === '') return '—';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  return `${numeric} yrs`;
}

function formatExperienceEntry(entry = {}) {
  const role = entry.role || 'Role';
  const company = entry.company ? ` @ ${entry.company}` : '';
  const dates = entry.date_range ? ` (${entry.date_range})` : '';
  const type = entry.entry_type ? ` [${String(entry.entry_type).toUpperCase()}]` : '';
  const years =
    entry.duration_years != null && entry.duration_years !== ''
      ? ` — ${formatYearsLabel(entry.duration_years)}`
      : '';
  const reason = entry.reason ? ` · ${entry.reason}` : '';
  return `${role}${company}${dates}${type}${years}${reason}`;
}

export function mapEvaluationToScreeningResult(evaluation, extraction, index = 0) {
  const candidate = evaluation.candidate_details || {};
  const breakdown = evaluation.score_breakdown || {};
  const experienceAssessment =
    evaluation.experience_assessment || breakdown.experience_assessment || {};
  const match = evaluation.match_analysis || {};
  const jd = evaluation.extracted_jd_requirements || {};
  const parsedResume = extraction?.parsed_data || {};
  const name =
    candidate.name ||
    parsedResume.name ||
    `Candidate ${index + 1}`;
  const score = Math.round(breakdown.overall_score || 0);
  const emails = asList(candidate.emails || parsedResume.emails);
  const phones = asList(candidate.phones || parsedResume.phones);
  const education =
    extractEducationFromSnapshot({
      candidate_education: evaluation.candidate_education,
      parsed_resume: parsedResume,
    }) ||
    asList(evaluation.candidate_education).filter(isValidEducationLine).slice(0, 3).join(' · ') ||
    asList(parsedResume.education).filter(isValidEducationLine).slice(0, 3).join(' · ') ||
    'Not extracted';
  const experienceSummary =
    extractExperienceFromSnapshot(
      {
        score_breakdown: breakdown,
        experience_assessment: experienceAssessment,
        parsed_resume: parsedResume,
        candidate_experience_years: evaluation.candidate_experience_years,
        candidate_relevant_experience_years: evaluation.candidate_relevant_experience_years,
      },
      breakdown,
    ) || formatYearsLabel(experienceAssessment.candidate_total_experience_years);

  const weights = breakdown.score_weights || {};
  const scoreBreakdown = [
    { label: 'Required skills', value: breakdown.required_skill_score, weight: weights.required_skills },
    { label: 'Preferred skills', value: breakdown.preferred_skill_score, weight: weights.preferred_skills },
    { label: 'Experience', value: breakdown.experience_score, weight: weights.experience },
    { label: 'Education', value: breakdown.education_score, weight: weights.education_certification },
    { label: 'Keywords', value: breakdown.keyword_score, weight: weights.keywords },
    { label: 'Responsibilities', value: breakdown.responsibility_score, weight: weights.responsibilities ?? weights.keywords },
  ].filter((row) => row.value != null);

  return {
    id: evaluation.saved_candidate_id || `${Date.now()}-${index}`,
    candidateId: evaluation.saved_candidate_id,
    name,
    email: emails[0] || '',
    phone: phones[0] || '',
    contact: [...emails, ...phones, ...asList(candidate.links)].filter(Boolean).join(' · '),
    avatar: name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase(),
    avatarColor: avatarColor(name),
    matchScore: score,
    recommendation: recommendationFromScore(score),
    shortlistStatus: evaluation.shortlist_status || breakdown.decision || 'Needs Review',
    skills: uniqueSkills(breakdown.matched_skills),
    missingSkills: uniqueSkills(breakdown.missing_skills),
    partialSkills: uniqueSkills(evaluation.match_analysis?.partial_required_skills || breakdown.partial_skills),
    responsibilityMatches: asList(breakdown.responsibility_matches),
    strengths: breakdown.strengths || [],
    concerns: breakdown.concerns || [],
    certifications: asList(evaluation.candidate_certifications),
    education,
    experience: experienceSummary === '—' ? 'Not extracted' : experienceSummary,
    summary: evaluation.final_recommendation || breakdown.recommendation || 'Screening completed.',
    scoreBreakdown,
    experienceAssessment: {
      jdRequirement: experienceAssessment.jd_requirement || 'Not specified',
      totalYears: formatYearsLabel(experienceAssessment.candidate_total_experience_years),
      relevantYears: formatYearsLabel(experienceAssessment.candidate_relevant_experience_years),
      professionalYears: formatYearsLabel(experienceAssessment.professional_experience_years),
      internshipYears: formatYearsLabel(experienceAssessment.internship_experience_years),
      researchYears: formatYearsLabel(experienceAssessment.research_experience_years),
      projectYears: formatYearsLabel(experienceAssessment.academic_project_years),
      handsOnYears: formatYearsLabel(
        experienceAssessment.relevant_hands_on_experience_years ??
          experienceAssessment.candidate_relevant_experience_years
      ),
      supportingYears: formatYearsLabel(
        experienceAssessment.supporting_exposure_years ??
          (
            Number(experienceAssessment.internship_experience_years || 0) +
            Number(experienceAssessment.academic_project_years || 0) +
            Number(experienceAssessment.research_experience_years || 0)
          )
      ),
      yearsTowardRequirement: formatYearsLabel(
        experienceAssessment.years_toward_requirement
      ),
      requirementKind: experienceAssessment.experience_requirement_kind || 'professional',
      allowsInternship: Boolean(experienceAssessment.allows_internship_for_requirement),
      unrelatedYears: formatYearsLabel(experienceAssessment.unrelated_experience_years),
      meetsMinimum: experienceAssessment.meets_minimum,
      result: experienceAssessment.result || 'No experience result available.',
      counted: asList(experienceAssessment.counted_experience).map(formatExperienceEntry),
      excluded: asList(experienceAssessment.excluded_experience).map(formatExperienceEntry),
      skillExperience: mapSkillExperienceAssessments(experienceAssessment),
    },
    hardRequirementStatus: breakdown.hard_requirement_status || 'N/A',
    hardRequirementReasons: asList(breakdown.hard_requirement_reasons),
    jobTitle: jd.job_title || 'Not specified',
    requiredMatchRatio: Math.round(Number(match.required_match_ratio || 0) * 100),
    preferredMatchRatio: Math.round(Number(match.preferred_match_ratio || 0) * 100),
    scheduling: evaluation.scheduling || null,
    resumeFileUrl: extraction?.stored_file_url || null,
  };
}
