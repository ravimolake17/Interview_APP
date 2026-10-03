import parkonLogo from '../assets/Parkon_logo.png';
import kabelLogo from '../assets/RR-Kabel-logo.png';
import rrMarkLogo from '../assets/RR-logo.png';

const CODE_LOGOS = {
  RRPARKON: parkonLogo,
  RRKABEL: kabelLogo,
};

function companyCode(company) {
  return String(company?.code || '').trim().toUpperCase();
}

export function isKabelCompany(company) {
  const code = companyCode(company);
  if (code === 'RRKABEL' || code === 'KABEL') return true;
  return String(company?.name || '').toLowerCase().includes('kabel');
}

export function companyDisplayName(company) {
  if (company?.name) return company.name;
  if (isKabelCompany(company)) return 'RR Kabel';
  return 'RR Parkon';
}

export function companyLogoSrc(company) {
  const code = companyCode(company);
  if (CODE_LOGOS[code]) return CODE_LOGOS[code];
  if (isKabelCompany(company)) return kabelLogo;
  if (company?.logo) return company.logo;
  return parkonLogo;
}

export function companyFaviconSrc() {
  return rrMarkLogo;
}

export function applyCompanyTabBrand(company, { titleSuffix = 'HR Recruitment System' } = {}) {
  if (typeof document === 'undefined') return;
  const name = companyDisplayName(company);
  document.title = titleSuffix ? `${name} — ${titleSuffix}` : name;
  const href = companyFaviconSrc();
  const selectors = ['link[rel="icon"]', 'link[rel="shortcut icon"]'];
  let link = selectors.map((sel) => document.querySelector(sel)).find(Boolean);
  if (!link) {
    link = document.createElement('link');
    link.rel = 'icon';
    document.head.appendChild(link);
  }
  link.type = 'image/png';
  link.href = href;
}
