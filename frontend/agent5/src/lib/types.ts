export type MessageKind = 'notice' | 'warning' | 'error' | 'success'

export type CandidatePhase = 'registration' | 'devices' | 'enrollment' | 'interview' | 'finished'

export interface CandidateSessionCredentials {
  sessionId: string
  token: string
  role?: 'candidate' | 'hr'
  company?: string
}

export interface CandidateRegistrationResponse {
  candidate_id: string
  session_id: string
  token: string
  status: string
  mandatory_models?: Record<string, boolean>
  mandatory_models_ready?: boolean
}

export interface SessionStateResponse {
  id: string
  status: string
  face_enrolled: boolean
  voice_enrolled: boolean
  device_checks_passed?: boolean
  mandatory_models?: Record<string, boolean>
  mandatory_models_ready?: boolean
  initial_face_verified: boolean
  initial_voice_verified: boolean
  tab_switch_count: number
  risk_score?: number
  risk_classification?: string
  termination_reason: string | null
  started_at: string | null
  current_client_elapsed_ms: number
  voice_sentence?: VoiceSentenceResponse | null
  company_code?: string | null
  company_name?: string | null
}

export interface AiInterviewSessionResponse {
  candidate_id: string
  status: string
  current_question: {
    id?: string
    question_text?: string
    category_name?: string
    category_id?: string
    is_followup?: boolean
    is_candidate_qna?: boolean
    is_closing?: boolean
    order?: number
  } | null
  current_index: number
  total_questions: number
  remaining_questions: number
  follow_ups?: Array<Record<string, unknown>>
  questions?: Array<{
    id?: string
    question_text?: string
    category_name?: string
    order?: number
    added_by_hr?: boolean
  }>
  turn_history: Array<{
    question?: { question_text?: string }
    answer_text?: string
  }>
  agent6_feedback?: string | null
  error?: string | null
  welcome_message?: string | null
  planned_duration_minutes?: number | null
  elapsed_seconds?: number
  duration_extended?: boolean
  interview_phase?: string | null
  turn_ack?: string | null
}

export interface McqOption {
  id: string
  text: string
}

export interface McqQuestionPublic {
  id: string
  order: number
  question_text: string
  options: McqOption[]
}

export interface McqStateResponse {
  status: 'missing' | 'pending' | 'in_progress' | 'completed' | 'timed_out' | string
  total_questions: number
  current_index: number
  remaining_seconds: number
  duration_seconds: number
  current_question: McqQuestionPublic | null
  intro_message?: string
  rules_message?: string
  oral_rules_message?: string
  result?: { answered?: number; skipped?: number; correct?: number; total?: number } | null
}

export interface InterviewRuntimeResponse {
  candidate_id: string
  session_id?: string
  state: string
  hr_speaking: boolean
  hr_message?: string | null
}



export interface VoiceSentenceResponse {
  id: string
  text: string
  issued_at: string | null
}

export interface SentenceVerificationSummary {
  passed: boolean
  failure_reason: string | null
  completion_percentage: number
  recognized_transcript?: string
  recognition_available?: boolean
  recognition_error?: string | null
  stt_provider?: string
  stt_model?: string
  recognized_words?: string[]
  word_results?: Array<Record<string, unknown>>
  sentence_id?: string
  sentence_text?: string
}

export interface VerificationResponse {
  passed: boolean
  label: string
  confidence: number
  measurements: Record<string, unknown>
  engine?: string
  sentence_verification?: SentenceVerificationSummary
  speaker_verification?: Record<string, unknown>
}

export interface FraudEventSummary {
  id?: string
  relative_ms: number
  type: string
  risk_contribution: number
  confidence?: number
  explanation?: string
}

export interface AnalysisResponse {
  status?: string
  frame_sequence?: number
  risk_score?: number
  risk_classification?: string
  events?: FraudEventSummary[]
  face_count?: number | null
  face_state?: string
  failure_reason?: string
  face_verification?: VerificationResponse
  speaker_verification?: VerificationResponse
  attention?: Record<string, unknown>
  head_pose?: Record<string, unknown>
  gaze?: Record<string, unknown>
  performance?: Record<string, number>
  monitoring?: { camera?: string; microphone?: string; analysis?: string }
  guidance?: string
}

export interface TabSwitchResponse {
  action: 'warn' | 'terminate' | 'none' | 'duplicate_ignored'
  message?: string
  termination_reason?: string | null
  tab_switch_count?: number
}

export interface FinishResponse {
  status: string
  termination_reason: string | null
  ended_at?: string | null
  artifacts?: Record<string, unknown>
}

export interface AdminLoginResponse {
  token: string
  username: string
  role: string
}

export interface AdminSessionListItem {
  id: string
  candidate: {
    id: string
    full_name: string
    email: string
  }
  status: string
  started_at: string | null
  ended_at: string | null
  termination_reason: string | null
  risk_score: number
  risk_classification: string
  tab_switch_count: number
}

export interface AdminSessionListResponse {
  page: number
  page_size: number
  total: number
  items: AdminSessionListItem[]
}

export interface EvidenceItem {
  id?: string
  kind: 'screenshot' | 'video' | 'audio' | string
  url: string
  creation_status: string
  size_bytes: number
  mime_type?: string
}

export interface TimelineEvent {
  id: string
  relative_ms: number
  start_ms?: number
  end_ms?: number
  duration_ms?: number
  state?: string
  type: string
  confidence: number
  risk_contribution: number
  explanation: string
  review_status?: string
  measurements?: Record<string, unknown>
  evidence?: EvidenceItem[]
}

export interface RecordingItem {
  id: string
  url: string
  validation_status: string
  duration_seconds?: number | null
  video_codec?: string | null
  audio_codec?: string | null
  size_bytes: number
}

export interface AdminSessionDetail {
  candidate: {
    id: string
    full_name: string
    email: string
  }
  session: Record<string, unknown> & {
    id: string
    status: string
  }
  risk: {
    score: number
    classification: string
    contributions_by_type: Record<string, number>
    automated_score?: number
    automated_classification?: string
    review_adjusted_score?: number
    review_adjusted_classification?: string
    review_adjusted_contributions_by_type?: Record<string, number>
    dismissed_event_count?: number
  }
  timeline: TimelineEvent[]
  recordings: RecordingItem[]
  system_errors?: Array<Record<string, unknown>>
  voice_sentence_attempts?: Array<Record<string, unknown>>
  detector_metrics?: Array<Record<string, unknown>>
  verification_attempts?: Array<Record<string, unknown>>
  attention_baseline?: Record<string, unknown> | null
  report_readiness?: {
    status: string
    recording_available: boolean
    recording_upload_complete: boolean
    confirmed_event_count: number
    evidence_artifact_count: number
    evidence_coverage_ratio: number
    evaluation_confidence: number
    uncertainty_label: string
  }
}

export interface ReportRegenerateResponse {
  report_id: string
  html_url: string
  pdf_url: string
  json_url: string
  checksums: { json: string; html: string; pdf: string }
  integrity_manifest: Record<string, { path: string; sha256: string; size_bytes: number }>
}
