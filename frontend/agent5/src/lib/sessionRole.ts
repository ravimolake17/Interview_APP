function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const segment = token.split('.')[1]
    if (!segment) return null
    return JSON.parse(atob(segment.replace(/-/g, '+').replace(/_/g, '/'))) as Record<string, unknown>
  } catch {
    return null
  }
}

/** Read participant_role from Agent5 JWT (client hint; server enforces). */
export function resolveParticipantRole(
  token: string,
  hint?: 'candidate' | 'hr' | null,
): 'candidate' | 'hr' {
  const payload = decodeJwtPayload(token)
  const role = String(payload?.participant_role || '').toLowerCase()
  if (role === 'hr') return 'hr'
  if (role === 'candidate') return 'candidate'
  return hint === 'hr' ? 'hr' : 'candidate'
}

export function readCompanyCodeFromToken(token: string): string {
  const payload = decodeJwtPayload(token)
  return String(payload?.company_code || '').trim().toUpperCase()
}
