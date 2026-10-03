import parkonLogo from '../assets/Parkon_logo.png'
import kabelLogo from '../assets/RR-Kabel-logo.png'
import { readCompanyCodeFromToken } from './sessionRole'

const COMPANY_STORAGE_KEY = 'agent5-company'

export interface CompanyBrand {
  code: string
  name: string
  logo: string
  subtitle: string
  footer: string
  interviewTitle: string
}

type BrandListener = () => void
const listeners = new Set<BrandListener>()

function notifyBrand(): void {
  listeners.forEach((listener) => listener())
}

export function subscribeCompanyBrand(listener: BrandListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function normalizeCode(value: string | null | undefined): string {
  return String(value || '').trim().toUpperCase()
}

function sessionIdFromLocation(): string {
  return String(new URLSearchParams(window.location.search).get('session_id') || '').trim()
}

function scopedStorageKey(sessionId?: string): string {
  const id = sessionId || sessionIdFromLocation()
  return id ? `${COMPANY_STORAGE_KEY}:${id}` : COMPANY_STORAGE_KEY
}

export function setCompanyCode(code: string | null | undefined, sessionId?: string): void {
  const normalized = normalizeCode(code)
  if (!normalized) return
  sessionStorage.setItem(scopedStorageKey(sessionId), normalized)
  notifyBrand()
}

export function readCompanyCode(): string {
  const params = new URLSearchParams(window.location.search)
  const fromQuery = normalizeCode(params.get('company'))
  if (fromQuery) {
    sessionStorage.setItem(scopedStorageKey(), fromQuery)
    return fromQuery
  }
  const sessionId = sessionIdFromLocation()
  if (sessionId) {
    const scoped = normalizeCode(sessionStorage.getItem(scopedStorageKey(sessionId)))
    if (scoped) return scoped
  }
  const token = params.get('token') || ''
  const fromToken = readCompanyCodeFromToken(token)
  if (fromToken) {
    sessionStorage.setItem(scopedStorageKey(sessionId), fromToken)
    return fromToken
  }
  return ''
}

export function resolveCompanyBrand(code = readCompanyCode()): CompanyBrand {
  const normalized = normalizeCode(code)
  const isKabel = normalized === 'RRKABEL' || normalized === 'KABEL' || normalized.includes('KABEL')
  if (isKabel) {
    return {
      code: 'RRKABEL',
      name: 'RR Kabel',
      logo: kabelLogo,
      subtitle: 'Recruitment System',
      footer: `© ${new Date().getFullYear()} RR Global · Kabel Recruitment`,
      interviewTitle: 'RR Kabel AI Interview',
    }
  }
  const isParkon = normalized === 'RRPARKON' || normalized === 'PARKON' || normalized.includes('PARKON')
  if (isParkon) {
    return {
      code: 'RRPARKON',
      name: 'RR Parkon',
      logo: parkonLogo,
      subtitle: 'Recruitment System',
      footer: `© ${new Date().getFullYear()} RR Global · Parkon Recruitment`,
      interviewTitle: 'RR Parkon AI Interview',
    }
  }
  return {
    code: '',
    name: 'AI Interview',
    logo: '',
    subtitle: 'Secure session',
    footer: `© ${new Date().getFullYear()} RR Global`,
    interviewTitle: 'AI Interview',
  }
}

export function applyCompanyDocumentBrand(brand = resolveCompanyBrand()): void {
  document.title = `${brand.name} — AI Interview`
  const icon = document.querySelector<HTMLLinkElement>("link[rel='icon']")
  if (icon) icon.href = brand.logo
}
