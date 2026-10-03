import type { AnalysisResponse, VerificationResponse } from './types'

export type LiveState = 'neutral' | 'ok' | 'bad'
export interface LiveStatus { label: string; state: LiveState }

function title(value: unknown): string {
  return String(value ?? '').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function faceLiveStatus(data: AnalysisResponse): LiveStatus {
  const state = String(data.face_state ?? data.status ?? '')
  const verification = data.face_verification
  const label = String(verification?.label ?? state)
  if (label === 'face_match') return { label: 'Face matched', state: 'ok' }
  if (label === 'face_mismatch') return { label: 'Face mismatch confirmed', state: 'bad' }
  if (label === 'face_detected') return { label: 'Face verification pending', state: 'neutral' }
  if (label === 'no_face') return { label: 'No face', state: 'bad' }
  if (label === 'multiple_faces') return { label: 'Multiple faces', state: 'bad' }
  if (label === 'low_quality_frame' || label === 'poor_quality') return { label: 'Low-quality frame', state: 'neutral' }
  if (label === 'stale_frame') return { label: 'Frame analysis delayed', state: 'neutral' }
  if (label === 'frame_decode_error') return { label: 'Camera frame could not be processed', state: 'neutral' }
  if (label === 'face_model_unavailable') return { label: 'Face detector unavailable', state: 'bad' }
  if (label === 'face_inference_timeout') return { label: 'Face analysis timed out', state: 'neutral' }
  if (label === 'face_inference_error') return { label: 'Face verification unavailable', state: 'neutral' }
  if (typeof data.face_count === 'number') {
    if (data.face_count === 1) return { label: 'One face detected — verification pending', state: 'neutral' }
    if (data.face_count > 1) return { label: 'Multiple faces', state: 'bad' }
    return { label: 'No face', state: 'bad' }
  }
  return { label: 'Frame analysis unavailable', state: 'neutral' }
}

export function voiceLiveStatus(result?: VerificationResponse, responseStatus?: string): LiveStatus {
  const label = String(result?.label ?? responseStatus ?? '')
  if (label === 'voice_match') return { label: 'Voice matched', state: 'ok' }
  if (label === 'voice_mismatch') return { label: 'Voice mismatch confirmed', state: 'bad' }
  if (label === 'no_speech') return { label: 'Waiting for speech', state: 'neutral' }
  if (label === 'insufficient_speech') return { label: 'Insufficient speech', state: 'neutral' }
  if (label === 'audio_too_noisy') return { label: 'Audio too noisy', state: 'neutral' }
  if (label === 'audio_clipped') return { label: 'Audio clipped', state: 'neutral' }
  if (label === 'stale_audio_window') return { label: 'Older audio result ignored', state: 'neutral' }
  if (label === 'speaker_model_unavailable') return { label: 'Speaker model unavailable', state: 'bad' }
  if (label === 'speaker_inference_error') return { label: 'Voice analysis unavailable', state: 'neutral' }
  if (label === 'microphone_interruption') return { label: 'Microphone interrupted', state: 'bad' }
  return { label: label ? title(label) : 'Waiting for speech', state: 'neutral' }
}

export function headPoseLiveStatus(headPose?: Record<string, unknown>): LiveStatus {
  const status = String(headPose?.pose_status ?? '')
  const direction = String(headPose?.pose_direction ?? 'neutral')
  if (status === 'valid') {
    if (direction === 'neutral' || direction === 'screen') return { label: 'Neutral', state: 'ok' }
    return { label: `${title(direction)} movement`, state: 'bad' }
  }
  if (status === 'brief_movement') return { label: 'Brief movement', state: 'neutral' }
  if (['low_confidence', 'extreme_pose'].includes(status)) return { label: 'Low confidence', state: 'neutral' }
  if (['landmark_unavailable', 'model_unavailable', 'inference_timeout'].includes(status)) return { label: 'Unavailable', state: 'neutral' }
  return { label: status ? title(status) : 'Waiting for landmarks', state: 'neutral' }
}

export function gazeLiveStatus(gaze?: Record<string, unknown>): LiveStatus {
  const status = String(gaze?.gaze_status ?? '')
  const direction = String(gaze?.gaze_direction ?? 'unknown')
  if (Boolean(gaze?.blink_detected)) return { label: 'Blink', state: 'neutral' }
  if (Boolean(gaze?.eyes_closed)) return { label: 'Eyes closed', state: 'neutral' }
  if (status === 'valid') {
    if (direction === 'screen' || direction === 'center') return { label: 'Screen focused', state: 'ok' }
    if (['left', 'right', 'up', 'down'].includes(direction)) return { label: `Looking ${title(direction)}`, state: 'bad' }
  }
  if (status === 'brief_glance') return { label: 'Brief glance', state: 'neutral' }
  if (['low_confidence', 'glasses_reflection', 'one_eye_unavailable'].includes(status)) return { label: 'Low confidence', state: 'neutral' }
  if (['landmarks_unavailable', 'model_unavailable', 'inference_timeout'].includes(status)) return { label: 'Unavailable', state: 'neutral' }
  return { label: status ? title(status) : 'Waiting for eye landmarks', state: 'neutral' }
}

export function attentionLiveStatus(attention?: Record<string, unknown>): LiveStatus {
  const combined = String(attention?.combined_state ?? '')
  const dominant = String(attention?.dominant_detector ?? 'none')
  const duplicateValue = attention?.duplicate_suppression ?? attention?.duplicate_suppressed
  const duplicate = duplicateValue === true || duplicateValue === 'suppressed' || duplicateValue === 'capped_combined_contribution'
  if (combined === 'screen_focused') return { label: 'Screen focused', state: 'ok' }
  if (combined === 'brief_glance') return { label: 'Brief glance', state: 'neutral' }
  if (combined === 'eyes_closed') return { label: 'Eyes closed', state: 'neutral' }
  if (combined === 'low_confidence' || combined === 'landmark_unavailable') return { label: 'Low confidence', state: 'neutral' }
  if (['eye_only_look_away', 'head_only_look_away', 'combined_look_away'].includes(combined)) {
    const suffix = dominant !== 'none' ? ` — ${title(dominant)} dominant` : ''
    return { label: `${title(combined)}${suffix}${duplicate ? ' — duplicate score suppressed' : ''}`, state: 'bad' }
  }
  return { label: combined ? title(combined) : 'Waiting for attention analysis', state: 'neutral' }
}
