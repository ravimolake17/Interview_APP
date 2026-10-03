import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BrandMark } from '../components/BrandMark'
import { JsonBlock } from '../components/JsonBlock'
import { MessageBanner } from '../components/MessageBanner'
import { Spinner } from '../components/Spinner'
import { StatusPill } from '../components/StatusPill'
import { TopBar } from '../components/TopBar'
import { ApiError, jsonRequest, requestJson } from '../lib/api'
import type {
  AdminSessionDetail,
  AdminSessionListItem,
  AdminSessionListResponse,
  EvidenceItem,
  MessageKind,
  ReportRegenerateResponse,
  TimelineEvent,
} from '../lib/types'

interface MessageState {
  text: string
  kind: MessageKind
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && typeof error.detail === 'string') return error.detail
  return error instanceof Error ? error.message : String(error)
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function riskState(score: number): 'ok' | 'warning' | 'bad' {
  if (score >= 55) return 'bad'
  if (score >= 25) return 'warning'
  return 'ok'
}

function eventLabel(type: string): string {
  return type.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function ContributionList({ values }: { values: Record<string, number> }) {
  const rows = Object.entries(values).sort((a, b) => Number(b[1]) - Number(a[1]))
  if (rows.length === 0) return <p className="muted">No confirmed risk contributions.</p>
  return <div className="contribution-list">{rows.map(([name, value]) => <div key={name}><span>{eventLabel(name)}</span><strong>+{Number(value).toFixed(1)}</strong></div>)}</div>
}

export function AdminPage() {
  const [token, setToken] = useState(() => localStorage.getItem('hr_access_token') ?? '')
  const tokenRef = useRef(token)
  const [mediaToken, setMediaToken] = useState('')
  const [message, setMessage] = useState<MessageState>({ text: '', kind: 'notice' })
  const [busy, setBusy] = useState('')
  const [sessions, setSessions] = useState<AdminSessionListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AdminSessionDetail | null>(null)
  const [reviewDecision, setReviewDecision] = useState('needs_more_review')
  const [reviewNotes, setReviewNotes] = useState('')
  const [reportLinks, setReportLinks] = useState<{ json: string; html: string; pdf: string; checksums: ReportRegenerateResponse['checksums'] } | null>(null)
  const debounceRef = useRef<number | null>(null)

  useEffect(() => { tokenRef.current = token }, [token])

  const showMessage = useCallback((text: string, kind: MessageKind = 'notice') => setMessage({ text, kind }), [])

  const api = useCallback(<T,>(path: string, options: RequestInit = {}): Promise<T> => {
    const currentToken = tokenRef.current
    if (!currentToken) return Promise.reject(new Error('Admin sign-in is required'))
    return requestJson<T>(path, options, currentToken)
  }, [])

  const refreshMediaToken = useCallback(async () => {
    if (!tokenRef.current) return
    setMediaToken(tokenRef.current)
  }, [])

  const mediaUrl = useCallback((url: string) => `${url}?token=${encodeURIComponent(mediaToken || tokenRef.current)}`, [mediaToken])

  const loadSessions = useCallback(async (requestedPage = page) => {
    if (!tokenRef.current) return
    setBusy('Loading sessions')
    try {
      const query = new URLSearchParams({ page: String(requestedPage), page_size: String(pageSize) })
      if (search.trim()) query.set('search', search.trim())
      if (statusFilter) query.set('status', statusFilter)
      if (riskFilter) query.set('risk', riskFilter)
      const data = await api<AdminSessionListResponse>(`/api/admin/sessions?${query}`)
      setSessions(data.items)
      setTotal(data.total)
      setPage(data.page)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        localStorage.removeItem('hr_access_token')
        setToken('')
        window.location.href = '/login'
      }
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }, [api, page, pageSize, riskFilter, search, showMessage, statusFilter])

  const loadDetail = useCallback(async (sessionId: string) => {
    setSelectedId(sessionId)
    setBusy('Loading session evidence')
    try {
      await refreshMediaToken()
      const data = await api<AdminSessionDetail>(`/api/admin/sessions/${sessionId}`)
      setDetail(data)
      setReportLinks(null)
      window.setTimeout(() => document.getElementById('session-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }, [api, refreshMediaToken, showMessage])

  const logout = () => {
    localStorage.removeItem('hr_access_token')
    tokenRef.current = ''
    setToken('')
    setMediaToken('')
    setSessions([])
    setDetail(null)
    setSelectedId(null)
    window.location.href = '/login'
  }

  useEffect(() => {
    if (!token) return
    void refreshMediaToken()
    void loadSessions(1)
    const interval = window.setInterval(() => void refreshMediaToken(), 8 * 60 * 1000)
    return () => window.clearInterval(interval)
  }, [token]) // Intentionally starts once per authentication token.

  useEffect(() => {
    if (!token) return
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => void loadSessions(1), 350)
    return () => { if (debounceRef.current) window.clearTimeout(debounceRef.current) }
  }, [search, statusFilter, riskFilter])

  const regenerateReport = async () => {
    if (!selectedId) return
    setBusy('Generating report')
    try {
      await refreshMediaToken()
      const data = await api<ReportRegenerateResponse>(`/api/admin/sessions/${selectedId}/report/regenerate`, { method: 'POST' })
      setReportLinks({ json: data.json_url, html: data.html_url, pdf: data.pdf_url, checksums: data.checksums })
      showMessage('Frozen JSON, HTML, and PDF reports were generated with SHA-256 checksums.', 'success')
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  const saveReview = async () => {
    if (!selectedId) return
    setBusy('Saving review')
    try {
      await api(`/api/admin/sessions/${selectedId}/review`, jsonRequest('POST', { decision: reviewDecision, notes: reviewNotes }))
      showMessage('Human review decision saved to the audit trail.', 'success')
      setReviewNotes('')
      await loadDetail(selectedId)
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  const reviewEvent = async (eventId: string, status: 'confirmed' | 'dismissed' | 'pending') => {
    if (!selectedId) return
    setBusy('Updating event review')
    try {
      await api(`/api/admin/events/${eventId}/review?status=${encodeURIComponent(status)}`, { method: 'PATCH' })
      showMessage(`Event marked ${status}.`, 'success')
      await loadDetail(selectedId)
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  const deleteSession = async () => {
    if (!selectedId || !detail) return
    const confirmed = window.confirm(`Permanently delete local data for ${detail.candidate.full_name}? This cannot be undone.`)
    if (!confirmed) return
    setBusy('Deleting session')
    try {
      await api(`/api/admin/sessions/${selectedId}`, { method: 'DELETE' })
      setDetail(null)
      setSelectedId(null)
      showMessage('Session data deleted from Agent5 local storage.', 'success')
      await loadSessions(1)
    } catch (error) {
      showMessage(errorMessage(error), 'error')
    } finally {
      setBusy('')
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const metrics = useMemo(() => ({
    active: sessions.filter((item) => item.status === 'active').length,
    completed: sessions.filter((item) => item.status === 'completed').length,
    terminated: sessions.filter((item) => item.status === 'terminated').length,
    highRisk: sessions.filter((item) => Number(item.risk_score) >= 55).length,
  }), [sessions])

  return (
    <>
      <TopBar title="Proctoring review" badge="HR workspace" />
      <main className="shell admin-shell">
        <div id="adminMessage">
          <MessageBanner text={message.text} kind={message.kind} onDismiss={() => setMessage({ text: '', kind: 'notice' })} />
        </div>
        {busy && <div className="busy-banner"><Spinner label={busy} /></div>}

        {!token && (
          <section className="card login-card" id="loginPanel">
            <div className="login-visual">
              <BrandMark subtitle="Recruitment System" size="lg" />
              <h1>HR sign-in required</h1>
              <p>Proctoring review uses the HR dashboard login. Sign in there, then return to this workspace.</p>
            </div>
            <div className="login-form">
              <button
                id="adminLogin"
                type="button"
                onClick={() => { window.location.href = '/login' }}
              >
                Go to HR login
              </button>
            </div>
          </section>
        )}

        {token && (
          <div id="dashboard">
            <section className="admin-heading">
              <div>
                <div className="section-kicker">Human review workspace</div>
                <h1>Interview sessions</h1>
                <p>AI-generated signals remain decision support. Confirm or dismiss evidence after reviewing the media.</p>
              </div>
              <div className="controls">
                <button id="refresh" type="button" className="secondary" onClick={() => void loadSessions(page)}>Refresh</button>
                <button type="button" className="ghost" onClick={logout}>Sign out</button>
              </div>
            </section>

            <section className="metric-grid">
              <div className="metric-card"><span>Sessions on this page</span><strong>{sessions.length}</strong><small>{total} total</small></div>
              <div className="metric-card"><span>Active</span><strong>{metrics.active}</strong><small>currently recording</small></div>
              <div className="metric-card"><span>Completed</span><strong>{metrics.completed}</strong><small>normal completion</small></div>
              <div className="metric-card"><span>Terminated</span><strong>{metrics.terminated}</strong><small>policy or technical</small></div>
              <div className="metric-card"><span>High review score</span><strong>{metrics.highRisk}</strong><small>55 or above</small></div>
            </section>

            <section className="card">
              <div className="filter-grid">
                <label>
                  Search
                  <input id="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Candidate, email, or session ID" />
                </label>
                <label>
                  Status
                  <select id="statusFilter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                    <option value="">All statuses</option>
                    <option value="pending">Pending</option>
                    <option value="active">Active</option>
                    <option value="completed">Completed</option>
                    <option value="terminated">Terminated</option>
                  </select>
                </label>
                <label>
                  Risk
                  <select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value)}>
                    <option value="">All risk classes</option>
                    <option value="low">Low</option>
                    <option value="moderate">Moderate</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </label>
              </div>

              <div className="session-table-wrap">
                <table className="session-table">
                  <thead><tr><th>Candidate</th><th>Status</th><th>Started</th><th>Risk</th><th>Tab switches</th><th /></tr></thead>
                  <tbody id="sessionList">
                    {sessions.map((session) => (
                      <tr key={session.id} className={selectedId === session.id ? 'selected' : ''}>
                        <td><strong>{session.candidate.full_name}</strong><span>{session.candidate.email}</span><code>{session.id}</code></td>
                        <td><StatusPill label={session.status} state={session.status === 'completed' ? 'ok' : session.status === 'terminated' ? 'bad' : session.status === 'active' ? 'warning' : 'neutral'} /></td>
                        <td>{formatDate(session.started_at)}</td>
                        <td><div className="table-risk"><strong>{Number(session.risk_score).toFixed(1)}</strong><StatusPill label={session.risk_classification} state={riskState(Number(session.risk_score))} /></div></td>
                        <td>{session.tab_switch_count}</td>
                        <td><button type="button" data-session={session.id} onClick={() => void loadDetail(session.id)}>Review</button></td>
                      </tr>
                    ))}
                    {sessions.length === 0 && <tr><td colSpan={6} className="empty-state">No sessions match these filters.</td></tr>}
                  </tbody>
                </table>
              </div>
              <div className="pagination">
                <button type="button" className="secondary" disabled={page <= 1} onClick={() => void loadSessions(page - 1)}>Previous</button>
                <span>Page {page} of {pageCount}</span>
                <button type="button" className="secondary" disabled={page >= pageCount} onClick={() => void loadSessions(page + 1)}>Next</button>
              </div>
            </section>

            {detail && (
              <section className="card detail-card" id="detailPanel">
                <div id="session-detail">
                  <div id="sessionDetail">
                    <div className="detail-heading">
                      <div>
                        <div className="section-kicker">Session review</div>
                        <h2>{detail.candidate.full_name}</h2>
                        <p>{detail.candidate.email} · <code>{detail.session.id}</code></p>
                      </div>
                      <div className="detail-risk">
                        <span>Final/current score</span>
                        <strong>{Number(detail.risk.score).toFixed(1)}<small>/100</small></strong>
                        <StatusPill label={detail.risk.classification} state={riskState(Number(detail.risk.score))} />
                        <small>Review adjusted: {Number(detail.risk.review_adjusted_score ?? detail.risk.score).toFixed(1)} ({detail.risk.review_adjusted_classification ?? detail.risk.classification})</small>
                      </div>
                    </div>

                    {detail.report_readiness && (
                      <div className={`report-readiness-banner ${detail.report_readiness.status}`}>
                        <div><strong>Report completeness: {detail.report_readiness.status}</strong><span>Evaluation confidence {(detail.report_readiness.evaluation_confidence * 100).toFixed(0)}% · {eventLabel(detail.report_readiness.uncertainty_label)}</span></div>
                        <div><span>Recording {detail.report_readiness.recording_available ? 'available' : 'unavailable'}</span><span>Evidence coverage {(detail.report_readiness.evidence_coverage_ratio * 100).toFixed(0)}%</span></div>
                      </div>
                    )}

                    <div className="grid two summary-grid">
                      <article className="subcard"><h3>Session state</h3><dl className="dashboard-definition-list"><div><dt>Status</dt><dd>{String(detail.session.status ?? '—')}</dd></div><div><dt>Started</dt><dd>{formatDate(String(detail.session.started_at ?? ''))}</dd></div><div><dt>Ended</dt><dd>{formatDate(String(detail.session.ended_at ?? ''))}</dd></div><div><dt>Termination</dt><dd>{String(detail.session.termination_reason ?? 'Normal completion')}</dd></div><div><dt>Recording upload</dt><dd>{String(detail.session.recording_upload_complete ?? false)}</dd></div></dl></article>
                      <article className="subcard"><h3>Explainable contributions</h3><ContributionList values={detail.risk.contributions_by_type} /></article>
                    </div>

                    <section className="detail-section detector-section" id="face-verification-section">
                      <div className="section-header"><div><h3>Face verification</h3><p>Whether the candidate’s face photos passed identity checks.</p></div></div>
                      <VerificationSummary attempts={(detail.verification_attempts ?? []).filter((item) => item.kind === 'face')} />
                      <DetectorEventGrid events={detail.timeline.filter((item) => ['face_mismatch', 'no_face', 'multiple_faces', 'face_spoof_concern'].includes(item.type))} mediaUrl={mediaUrl} onReview={reviewEvent} />
                    </section>

                    <section className="detail-section detector-section" id="voice-verification-section">
                      <div className="section-header"><div><h3>Voice verification</h3><p>Sentence read-back and speaker match for this session.</p></div></div>
                      <VoiceSentenceTable attempts={detail.voice_sentence_attempts ?? []} />
                      <VerificationSummary attempts={(detail.verification_attempts ?? []).filter((item) => item.kind === 'voice')} />
                      <DetectorEventGrid events={detail.timeline.filter((item) => ['voice_mismatch', 'possible_additional_speaker', 'overlapping_speech', 'microphone_interruption'].includes(item.type))} mediaUrl={mediaUrl} onReview={reviewEvent} />
                    </section>

                    <AutomaticAttentionBaselineSummary baseline={detail.attention_baseline} />
                    <LatestAttentionSummary metrics={detail.detector_metrics ?? []} />
                    <DetectorEventSection title="Gaze tracking" description="Eye/iris direction independent of head pose, with blink handling, passive-baseline context, evidence, and explainable risk." events={detail.timeline.filter((item) => item.type === 'gaze_violation')} mediaUrl={mediaUrl} onReview={reviewEvent} />
                    <DetectorEventSection title="Head pose" description="Automatic neutral-baseline status, raw/smoothed/neutral-relative yaw, pitch and roll, duration, confidence, evidence, and risk." events={detail.timeline.filter((item) => item.type === 'head_pose_violation')} mediaUrl={mediaUrl} onReview={reviewEvent} />
                    <DetectorEventSection title="Combined attention" description="Coordinated gaze/head state, dominant detector, duplicate suppression, and capped final contribution." events={detail.timeline.filter((item) => item.type === 'attention_look_away')} mediaUrl={mediaUrl} onReview={reviewEvent} />
                    <DetectorEventSection title="Multiple-face detection" description="Confirmed visible-face counts and evidence." events={detail.timeline.filter((item) => item.type === 'multiple_faces')} mediaUrl={mediaUrl} onReview={reviewEvent} />
                    <DetectorEventSection title="Multiple voice and audio" description="Review-only additional speaker, overlapping speech, background/noise context, and microphone events." events={detail.timeline.filter((item) => ['possible_additional_speaker', 'overlapping_speech', 'voice_mismatch', 'microphone_interruption'].includes(item.type))} mediaUrl={mediaUrl} onReview={reviewEvent} />

                    <section className="detail-section detector-section" id="tab-switch-section">
                      <div className="section-header"><div><h3>Tab switching</h3><p>Backend-authoritative count, warning, termination, timestamps, and recording finalization state.</p></div></div>
                      <dl className="media-meta dashboard-definition-list">
                        <div><dt>Total switches</dt><dd>{String(detail.session.tab_switch_count ?? 0)}</dd></div>
                        <div><dt>Session state</dt><dd>{String(detail.session.status ?? '—')}</dd></div>
                        <div><dt>Termination reason</dt><dd>{String(detail.session.termination_reason ?? '—')}</dd></div>
                        <div><dt>Recording complete</dt><dd>{String(detail.session.recording_upload_complete ?? false)}</dd></div>
                      </dl>
                      <DetectorEventGrid events={detail.timeline.filter((item) => ['first_tab_switch', 'repeated_tab_switch'].includes(item.type))} mediaUrl={mediaUrl} onReview={reviewEvent} />
                    </section>

                    <section className="detail-section detector-section" id="detector-performance-section">
                      <div className="section-header"><div><h3>Detector speed and queue telemetry</h3><p>Measured server inference/API time, sequence, queue depth, stale-drop count, and status.</p></div></div>
                      <DetectorMetricTable metrics={detail.detector_metrics ?? []} />
                    </section>

                    <section className="detail-section">
                      <div className="section-header">
                        <div><h3>Full interview recording</h3><p>Validated server-side recording with byte-range playback.</p></div>
                      </div>
                      <div className="media-grid">
                        {detail.recordings.map((recording) => (
                          <article className="media-item" key={recording.id}>
                            <div className="media-title">
                              <strong>Full interview</strong>
                              <StatusPill label={recording.validation_status} state={recording.validation_status === 'valid' ? 'ok' : 'warning'} />
                            </div>
                            <video controls preload="metadata" src={mediaUrl(recording.url)} />
                            <dl className="media-meta">
                              <div><dt>Duration</dt><dd>{Number(recording.duration_seconds ?? 0).toFixed(2)}s</dd></div>
                              <div><dt>Codecs</dt><dd>{recording.video_codec || '—'} / {recording.audio_codec || '—'}</dd></div>
                              <div><dt>Size</dt><dd>{recording.size_bytes.toLocaleString()} bytes</dd></div>
                            </dl>
                          </article>
                        ))}
                        {detail.recordings.length === 0 && <div className="empty-state">No finalized recording is available.</div>}
                      </div>
                    </section>

                    <section className="detail-section">
                      <div className="section-header">
                        <div><h3>Chronological event timeline</h3><p>{detail.timeline.length} confirmed detector event(s)</p></div>
                      </div>
                      <div className="timeline-list">
                        {detail.timeline.map((event) => (
                          <EventCard key={event.id} event={event} mediaUrl={mediaUrl} onReview={reviewEvent} />
                        ))}
                        {detail.timeline.length === 0 && <div className="empty-state">No confirmed fraud events were stored for this session.</div>}
                      </div>
                    </section>

                    <section className="detail-section review-section">
                      <div>
                        <h3>Human review decision</h3>
                        <p>Record an independent review outcome and notes. Agent5 does not automatically declare guilt.</p>
                      </div>
                      <div className="review-form">
                        <label>
                          Decision
                          <select value={reviewDecision} onChange={(event) => setReviewDecision(event.target.value)}>
                            <option value="needs_more_review">Needs more review</option>
                            <option value="clear">Clear</option>
                            <option value="confirmed_concern">Confirmed concern</option>
                          </select>
                        </label>
                        <label>
                          Notes
                          <textarea value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} rows={4} placeholder="Evidence reviewed, context, and rationale" />
                        </label>
                        <div className="controls">
                          <button type="button" onClick={() => void saveReview()}>Save review</button>
                          <button id="regenReport" type="button" className="secondary" onClick={() => void regenerateReport()}>Generate reports</button>
                        </div>
                        <div id="reportLinks">
                          {reportLinks && (
                            <div className="report-links">
                              <a className="button secondary" target="_blank" rel="noreferrer" href={mediaUrl(reportLinks.json)}>Open JSON report</a>
                              <a className="button secondary" target="_blank" rel="noreferrer" href={mediaUrl(reportLinks.html)}>Open HTML report</a>
                              <a className="button secondary" target="_blank" rel="noreferrer" href={mediaUrl(reportLinks.pdf)}>Open PDF report</a>
                              <details className="report-checksums"><summary>Report SHA-256 checksums</summary><JsonBlock value={reportLinks.checksums} /></details>
                            </div>
                          )}
                        </div>
                      </div>
                    </section>

                    <details className="technical-details">
                      <summary>Technical errors and diagnostic data</summary>
                      <JsonBlock value={detail.system_errors ?? []} />
                    </details>
                    <div className="danger-zone">
                      <div><strong>Delete local session data</strong><p>Removes the database session and associated local recordings/evidence using the backend retention workflow.</p></div>
                      <button type="button" className="danger" onClick={() => void deleteSession()}>Delete session</button>
                    </div>
                  </div>
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </>
  )

}

function VoiceSentenceTable({ attempts }: { attempts: Array<Record<string, unknown>> }) {
  if (!attempts.length) return <div className="empty-state compact">No voice sentence attempt is stored.</div>
  return (
    <div className="table-scroll"><table className="detail-table"><thead><tr><th>Stage</th><th>Sentence</th><th>Transcript</th><th>Completion</th><th>Result</th></tr></thead><tbody>
      {attempts.map((item, index) => <tr key={String(item.id ?? index)}><td>{String(item.stage ?? '—')}</td><td>{String(item.sentence_text ?? '—')}</td><td>{String(item.recognized_transcript ?? '—')}</td><td>{Number(item.completion_percentage ?? 0).toFixed(1)}%</td><td>{Boolean(item.passed) ? 'Passed' : String(item.failure_reason ?? 'Failed')}</td></tr>)}
    </tbody></table></div>
  )
}

function VerificationSummary({ attempts }: { attempts: Array<Record<string, unknown>> }) {
  if (!attempts.length) return <div className="empty-state compact">No identity checks were recorded.</div>
  const passed = attempts.filter((item) => Boolean(item.passed)).length
  const failed = attempts.length - passed
  const latest = attempts[attempts.length - 1]
  return (
    <dl className="media-meta dashboard-definition-list">
      <div><dt>Attempts</dt><dd>{attempts.length}</dd></div>
      <div><dt>Passed</dt><dd>{passed}</dd></div>
      <div><dt>Needs review</dt><dd>{failed}</dd></div>
      <div><dt>Latest result</dt><dd>{Boolean(latest?.passed) ? 'Passed' : 'Needs review'}</dd></div>
    </dl>
  )
}


function displayValue(value: unknown, digits = 3): string {
  if (value == null || value === '') return '—'
  if (typeof value === 'number') return Number.isFinite(value) ? value.toFixed(digits) : '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function AutomaticAttentionBaselineSummary({ baseline }: { baseline?: Record<string, unknown> | null }) {
  const data = baseline ?? {}
  const measurements = (data.measurements && typeof data.measurements === 'object' ? data.measurements : data) as Record<string, unknown>
  const neutralPose = (data.neutral_pose ?? measurements.neutral_pose ?? {}) as Record<string, unknown>
  const neutralGaze = (data.neutral_gaze ?? measurements.neutral_gaze ?? {}) as Record<string, unknown>
  const status = String(data.status ?? measurements.status ?? 'not_started')
  const state = status === 'ready' ? 'ok' : status === 'fallback' ? 'warning' : 'neutral'
  return <section className="detail-section detector-section" id="automatic-attention-baseline-section">
    <div className="section-header"><div><h3>Automatic attention baseline</h3><p>Passive in-interview neutral-pose handling. No candidate buttons or pre-interview calibration are used.</p></div><StatusPill label={status.replaceAll('_', ' ')} state={state} /></div>
    <dl className="media-meta dashboard-definition-list">
      <div><dt>Baseline status</dt><dd>{displayValue(status)}</dd></div>
      <div><dt>Baseline confidence</dt><dd>{displayValue(data.baseline_confidence ?? measurements.baseline_confidence)}</dd></div>
      <div><dt>Accepted / rejected frames</dt><dd>{displayValue(data.accepted_samples, 0)} / {displayValue(data.rejected_samples, 0)}</dd></div>
      <div><dt>Neutral yaw / pitch / roll</dt><dd>{displayValue(neutralPose.yaw)} / {displayValue(neutralPose.pitch)} / {displayValue(neutralPose.roll)}</dd></div>
      <div><dt>Neutral gaze X / Y</dt><dd>{displayValue(neutralGaze.x_ratio)} / {displayValue(neutralGaze.y_ratio)}</dd></div>
      <div><dt>Natural pose range</dt><dd>{displayValue(measurements.natural_pose_range)}</dd></div>
      <div><dt>Started / ready time</dt><dd>{displayValue(data.started_relative_ms, 0)} ms / {displayValue(data.ready_relative_ms, 0)} ms</dd></div>
      <div><dt>Technical warning</dt><dd>{displayValue(data.technical_warning ?? measurements.technical_warning)}</dd></div>
      <div><dt>Model</dt><dd>{displayValue(data.model_name)} {displayValue(data.model_version)}</dd></div>
      <div><dt>Quality</dt><dd>{displayValue(data.quality ?? measurements.quality)}</dd></div>
    </dl>
  </section>
}

function LatestAttentionSummary({ metrics }: { metrics: Array<Record<string, unknown>> }) {
  const latest = [...metrics].reverse().find((item) => {
    const details = item.details
    if (!details || typeof details !== 'object' || Array.isArray(details)) return false
    const attention = (details as Record<string, unknown>).attention
    return Boolean(attention && typeof attention === 'object' && !Array.isArray(attention) && Object.keys(attention as Record<string, unknown>).length)
  })
  if (!latest) return <section className="detail-section detector-section" id="latest-attention-section"><div className="section-header"><div><h3>Latest attention state</h3><p>No visual-attention telemetry has been stored for this session.</p></div></div></section>
  const details = latest.details as Record<string, unknown>
  const a = details.attention as Record<string, unknown>
  return <section className="detail-section detector-section" id="latest-attention-section">
    <div className="section-header"><div><h3>Latest attention state</h3><p>Most recent bounded visual-analysis result, including technical confidence and queue health.</p></div></div>
    <dl className="media-meta dashboard-definition-list attention-event-details">
      <div><dt>Combined / dominant</dt><dd>{displayValue(a.combined_state)} / {displayValue(a.dominant_detector)}</dd></div>
      <div><dt>Gaze direction / confidence</dt><dd>{displayValue(a.gaze_direction)} / {displayValue(a.gaze_confidence)}</dd></div>
      <div><dt>Left / right eye confidence</dt><dd>{displayValue(a.left_eye_confidence)} / {displayValue(a.right_eye_confidence)}</dd></div>
      <div><dt>Eyes closed / blink</dt><dd>{displayValue(a.eyes_closed)} / {displayValue(a.blink_detected)}</dd></div>
      <div><dt>Pose direction / confidence</dt><dd>{displayValue(a.pose_direction)} / {displayValue(a.pose_confidence)}</dd></div>
      <div><dt>Raw yaw / pitch / roll</dt><dd>{displayValue(a.raw_yaw)} / {displayValue(a.raw_pitch)} / {displayValue(a.raw_roll)}</dd></div>
      <div><dt>Smoothed yaw / pitch / roll</dt><dd>{displayValue(a.smoothed_yaw)} / {displayValue(a.smoothed_pitch)} / {displayValue(a.smoothed_roll)}</dd></div>
      <div><dt>Technical status</dt><dd>{displayValue(a.status)}{a.failure_reason ? ` — ${displayValue(a.failure_reason)}` : ''}</dd></div>
      <div><dt>Model engine / version</dt><dd>{displayValue(a.model_name ?? a.engine)} / {displayValue(a.model_version)}</dd></div>
      <div><dt>Frame / captured</dt><dd>{displayValue(a.frame_sequence ?? latest.sequence_number, 0)} / {formatDate(String(a.capture_timestamp ?? latest.captured_at ?? ''))}</dd></div>
      <div><dt>Landmark / gaze / pose latency</dt><dd>{displayValue(a.landmark_inference_latency_ms)} / {displayValue(a.gaze_inference_latency_ms)} / {displayValue(a.head_pose_inference_latency_ms)} ms</dd></div>
      <div><dt>End-to-end / queue / dropped</dt><dd>{displayValue(latest.api_ms)} ms / {displayValue(latest.queue_depth, 0)} / {displayValue(latest.dropped_stale, 0)}</dd></div>
      <div><dt>Duplicate suppression</dt><dd>{displayValue(a.duplicate_suppression)}</dd></div>
      <div><dt>Automatic baseline</dt><dd>{displayValue(a.baseline_status)} / confidence {displayValue(a.baseline_confidence)}{a.baseline_technical_warning ? ` — ${displayValue(a.baseline_technical_warning)}` : ''}</dd></div>
    </dl>
  </section>
}

function TabSwitchEventDetails({ event }: { event: TimelineEvent }) {
  if (!['first_tab_switch', 'repeated_tab_switch'].includes(event.type)) return null
  const m = event.measurements ?? {}
  return <dl className="media-meta dashboard-definition-list attention-event-details">
    <div><dt>Episode ID</dt><dd>{displayValue(m.episode_id)}</dd></div>
    <div><dt>Hidden duration</dt><dd>{displayValue(m.hidden_duration_ms, 0)} ms</dd></div>
    <div><dt>Hidden / visible</dt><dd>{displayValue(m.hidden_started_at)} / {displayValue(m.visible_returned_at)}</dd></div>
    <div><dt>Visibility / focus</dt><dd>{displayValue(m.visibility_state)} / {displayValue(m.focus_lost)}</dd></div>
    <div><dt>Browser events</dt><dd>{displayValue(m.triggering_browser_events)}</dd></div>
    <div><dt>Authoritative count</dt><dd>{displayValue(m.authoritative_count, 0)}</dd></div>
    <div><dt>Deduplication</dt><dd>{displayValue(m.deduplication_result)}</dd></div>
    <div><dt>Evidence scope</dt><dd>{displayValue(m.evidence_scope)}</dd></div>
  </dl>
}

function VoiceEventDetails({ event }: { event: TimelineEvent }) {
  if (!['voice_mismatch', 'possible_additional_speaker', 'overlapping_speech'].includes(event.type)) return null
  const m = event.measurements ?? {}
  const quality = (m.quality && typeof m.quality === 'object' ? m.quality : {}) as Record<string, unknown>
  const window = (m.audio_window && typeof m.audio_window === 'object' ? m.audio_window : {}) as Record<string, unknown>
  return <dl className="media-meta dashboard-definition-list attention-event-details">
    <div><dt>Similarity / threshold</dt><dd>{displayValue(m.similarity)} / {displayValue(m.threshold)}</dd></div>
    <div><dt>Audio quality accepted</dt><dd>{displayValue(quality.accepted)}</dd></div>
    <div><dt>Voiced duration / ratio</dt><dd>{displayValue(quality.voiced_duration_seconds)} / {displayValue(quality.voiced_ratio)}</dd></div>
    <div><dt>Verification windows</dt><dd>{displayValue(m.verification_window_count, 0)}</dd></div>
    <div><dt>Audio sequence</dt><dd>{displayValue(window.sequence_number, 0)}</dd></div>
    <div><dt>Window start / end</dt><dd>{displayValue(window.window_start_ms, 0)} / {displayValue(window.window_end_ms, 0)} ms</dd></div>
    <div><dt>Engine / version</dt><dd>{displayValue(m.engine)} / {displayValue(m.model_version)}</dd></div>
  </dl>
}

function AttentionEventDetails({ event }: { event: TimelineEvent }) {
  if (!['gaze_violation', 'head_pose_violation', 'attention_look_away'].includes(event.type)) return null
  const m = event.measurements ?? {}
  return <dl className="media-meta dashboard-definition-list attention-event-details">
    <div><dt>Combined state</dt><dd>{displayValue(m.combined_state ?? event.state)}</dd></div>
    <div><dt>Gaze / pose direction</dt><dd>{displayValue(m.gaze_direction)} / {displayValue(m.pose_direction)}</dd></div>
    <div><dt>Dominant detector</dt><dd>{displayValue(m.dominant_detector)}</dd></div>
    <div><dt>Duplicate suppression</dt><dd>{displayValue(m.duplicate_suppression)}</dd></div>
    <div><dt>Raw yaw / pitch / roll</dt><dd>{displayValue(m.raw_yaw)} / {displayValue(m.raw_pitch)} / {displayValue(m.raw_roll)}</dd></div>
    <div><dt>Smoothed yaw / pitch / roll</dt><dd>{displayValue(m.smoothed_yaw)} / {displayValue(m.smoothed_pitch)} / {displayValue(m.smoothed_roll)}</dd></div>
    <div><dt>Neutral-relative pose</dt><dd>{displayValue(m.neutral_relative_yaw)} / {displayValue(m.neutral_relative_pitch)} / {displayValue(m.neutral_relative_roll)}</dd></div>
    <div><dt>Automatic neutral offset</dt><dd>{displayValue(m.neutral_offset)}</dd></div>
    <div><dt>Gaze X / Y</dt><dd>{displayValue(m.gaze_x_ratio)} / {displayValue(m.gaze_y_ratio)}</dd></div>
    <div><dt>Gaze confidence</dt><dd>{displayValue(m.gaze_confidence)}</dd></div>
    <div><dt>Left / right eye confidence</dt><dd>{displayValue(m.left_eye_confidence)} / {displayValue(m.right_eye_confidence)}</dd></div>
    <div><dt>Pose / landmark confidence</dt><dd>{displayValue(m.pose_confidence)} / {displayValue(m.landmark_confidence)}</dd></div>
    <div><dt>Eyes closed / blink</dt><dd>{displayValue(m.eyes_closed)} / {displayValue(m.blink_detected)}</dd></div>
    <div><dt>Automatic baseline</dt><dd>{displayValue(m.baseline_status)} / confidence {displayValue(m.baseline_confidence)}{m.baseline_technical_warning ? ` — ${displayValue(m.baseline_technical_warning)}` : ''}</dd></div>
    <div><dt>Technical status</dt><dd>{displayValue(m.status)}{m.failure_reason ? ` — ${displayValue(m.failure_reason)}` : ''}</dd></div>
    <div><dt>Event start / end</dt><dd>{displayValue(event.start_ms ?? m.event_start_ms, 0)} ms / {displayValue(event.end_ms ?? m.event_end_ms, 0)} ms</dd></div>
    <div><dt>Duration</dt><dd>{displayValue(event.duration_ms ?? m.event_duration_ms, 0)} ms</dd></div>
    <div><dt>Confirmation count</dt><dd>{displayValue(m.consecutive_confirmation_count, 0)}</dd></div>
    <div><dt>Model engine / version</dt><dd>{displayValue(m.model_name ?? m.engine)} / {displayValue(m.model_version)}</dd></div>
    <div><dt>Final risk contribution</dt><dd>+{displayValue(event.risk_contribution, 2)}</dd></div>
    <div><dt>Human review</dt><dd>{displayValue(event.review_status ?? 'pending')}</dd></div>
  </dl>
}

function DetectorMetricTable({ metrics }: { metrics: Array<Record<string, unknown>> }) {
  if (!metrics.length) return <div className="empty-state compact">No detector telemetry is stored.</div>
  return (
    <div className="table-scroll"><table className="detail-table"><thead><tr><th>Detector</th><th>Sequence</th><th>Inference</th><th>API</th><th>Queue</th><th>Dropped</th><th>Status</th></tr></thead><tbody>
      {metrics.slice(-200).reverse().map((item, index) => <tr key={String(item.id ?? index)}><td>{String(item.detector ?? '—')}</td><td>{String(item.sequence_number ?? '—')}</td><td>{Number(item.inference_ms ?? 0).toFixed(2)} ms</td><td>{Number(item.api_ms ?? 0).toFixed(2)} ms</td><td>{String(item.queue_depth ?? 0)}</td><td>{String(item.dropped_stale ?? 0)}</td><td>{String(item.status ?? '—')}</td></tr>)}
    </tbody></table></div>
  )
}

function DetectorEventGrid({ events, mediaUrl, onReview }: { events: TimelineEvent[]; mediaUrl: (url: string) => string; onReview: EventCardProps['onReview'] }) {
  return <div className="timeline-list compact-timeline">{events.map((event) => <EventCard key={event.id} event={event} mediaUrl={mediaUrl} onReview={onReview} />)}{events.length === 0 && <div className="empty-state compact">No confirmed events in this section.</div>}</div>
}

function DetectorEventSection({ title, description, events, mediaUrl, onReview }: { title: string; description: string; events: TimelineEvent[]; mediaUrl: (url: string) => string; onReview: EventCardProps['onReview'] }) {
  return <section className="detail-section detector-section"><div className="section-header"><div><h3>{title}</h3><p>{description}</p></div></div><DetectorEventGrid events={events} mediaUrl={mediaUrl} onReview={onReview} /></section>
}

interface EventCardProps {
  event: TimelineEvent
  mediaUrl: (url: string) => string
  onReview: (eventId: string, status: 'confirmed' | 'dismissed' | 'pending') => Promise<void>
}

function EventCard({ event, mediaUrl, onReview }: EventCardProps) {
  return (
    <article className="timeline-card">
      <div className="timeline-marker"><span>{(event.relative_ms / 1000).toFixed(1)}s</span></div>
      <div className="timeline-content">
        <div className="timeline-heading">
          <div><h4>{eventLabel(event.type)}</h4><p>{event.explanation}</p></div>
          <div className="timeline-metrics"><span>Confidence <strong>{Number(event.confidence).toFixed(2)}</strong></span><span>Risk <strong>+{Number(event.risk_contribution).toFixed(2)}</strong></span><StatusPill label={event.review_status || 'pending'} state={event.review_status === 'confirmed' ? 'bad' : event.review_status === 'dismissed' ? 'ok' : 'warning'} /></div>
        </div>
        <AttentionEventDetails event={event} />
        <VoiceEventDetails event={event} />
        <TabSwitchEventDetails event={event} />
        <div className="media-grid event-media">
          {(event.evidence ?? []).map((evidence, index) => <EvidencePlayer key={evidence.id ?? `${evidence.kind}-${index}`} evidence={evidence} mediaUrl={mediaUrl} />)}
          {(event.evidence ?? []).length === 0 && ['first_tab_switch', 'repeated_tab_switch'].includes(event.type) && <div className="empty-state compact">Browser visibility metadata is stored in the event measurements. External application content cannot be captured by the browser.</div>}
          {(event.evidence ?? []).length === 0 && !['first_tab_switch', 'repeated_tab_switch'].includes(event.type) && <div className="empty-state compact">Evidence creation is pending or unavailable for this event.</div>}
        </div>
        <div className="controls event-controls"><button type="button" className="secondary" onClick={() => void onReview(event.id, 'confirmed')}>Confirm concern</button><button type="button" className="secondary" onClick={() => void onReview(event.id, 'dismissed')}>Dismiss event</button><button type="button" className="ghost" onClick={() => void onReview(event.id, 'pending')}>Reset pending</button></div>
      </div>
    </article>
  )
}

function EvidencePlayer({ evidence, mediaUrl }: { evidence: EvidenceItem; mediaUrl: (url: string) => string }) {
  return (
    <article className="media-item evidence-player">
      <div className="media-title"><strong>{eventLabel(evidence.kind)}</strong><StatusPill label={evidence.creation_status} state={evidence.creation_status === 'ready' || evidence.creation_status === 'created' ? 'ok' : 'warning'} /></div>
      {evidence.kind === 'screenshot' && <img src={mediaUrl(evidence.url)} alt="Fraud event evidence" />}
      {evidence.kind === 'video' && <video controls preload="metadata" src={mediaUrl(evidence.url)} />}
      {evidence.kind === 'audio' && <audio controls preload="metadata" src={mediaUrl(evidence.url)} />}
      {!['screenshot', 'video', 'audio'].includes(evidence.kind) && <a className="button secondary" href={mediaUrl(evidence.url)} target="_blank" rel="noreferrer">Open evidence</a>}
      <div className="muted">{evidence.size_bytes.toLocaleString()} bytes</div>
    </article>
  )
}
