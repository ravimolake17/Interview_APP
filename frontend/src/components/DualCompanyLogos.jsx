import { companyLogoSrc } from '../utils/companyBranding';
import globalLogo from '../assets/RR-Global-logo.svg';

export default function DualCompanyLogos({ height = 48, className = '' }) {
  return (
    <div className={`flex items-center justify-center ${className}`.trim()}>
      <img
        src={globalLogo}
        alt="RR Global"
        style={{ height }}
        className="w-auto max-w-full"
      />
    </div>
  );
}

export function CompanyLogo({ company, height = 48, className = 'logo-on-white' }) {
  const known = Boolean(company?.code || company?.name);
  if (!known) {
    return <DualCompanyLogos height={height} className={className} />;
  }
  const name = company?.name || 'Company';
  return (
    <img
      src={companyLogoSrc(company)}
      alt={name}
      style={{ height }}
      className={`w-auto ${className}`.trim()}
    />
  );
}
