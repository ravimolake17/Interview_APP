import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2, ShieldCheck } from 'lucide-react';
import { joinInterview } from '../services/api';
import { companyDisplayName, companyLogoSrc, applyCompanyTabBrand } from '../utils/companyBranding';
import DualCompanyLogos from '../components/DualCompanyLogos';

export default function JoinInterview({ role = 'candidate' } = {}) {
  const { token } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [company, setCompany] = useState(null);
  const isHr = String(role).toLowerCase() === 'hr';
  const knownCompany = Boolean(company?.name || company?.code);
  const brandName = knownCompany ? companyDisplayName(company) : 'RR Global';
  const brandLogo = knownCompany ? companyLogoSrc(company) : null;

  useEffect(() => {
    applyCompanyTabBrand(company, { titleSuffix: isHr ? 'Interview room' : 'Interview verification' });
  }, [company, isHr]);

  useEffect(() => {
    if (!token) {
      setError('Missing interview link token.');
      setLoading(false);
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const { data } = await joinInterview(token, isHr ? 'hr' : undefined);
        if (cancelled) return;
        setCompany({ name: data.company_name, code: data.company_code });
        let proctoringUrl =
          data.proctoring_url ||
          `/proctoring/?session_id=${encodeURIComponent(data.session_id)}&token=${encodeURIComponent(data.agent5_token)}`;
        try {
          const resolved = new URL(proctoringUrl, window.location.origin);
          if (isHr) resolved.searchParams.set('role', 'hr');
          if (data.company_code) resolved.searchParams.set('company', data.company_code);
          proctoringUrl = resolved.toString();
        } catch {
          const params = [];
          if (isHr && !/[?&]role=hr\b/.test(proctoringUrl)) params.push('role=hr');
          if (data.company_code && !/[?&]company=/.test(proctoringUrl)) {
            params.push(`company=${encodeURIComponent(data.company_code)}`);
          }
          if (params.length) {
            const sep = proctoringUrl.includes('?') ? '&' : '?';
            proctoringUrl = `${proctoringUrl}${sep}${params.join('&')}`;
          }
        }
        window.location.assign(proctoringUrl);
      } catch (err) {
        if (cancelled) return;
        const data = err.response?.data || {};
        const detail = data.detail;
        if (detail && typeof detail === 'object') {
          setError(detail.message || 'Unable to open interview verification.');
          if (detail.company_name || detail.company_code) {
            setCompany({ name: detail.company_name, code: detail.company_code });
          }
        } else {
          setError(detail || err.message || 'Unable to open interview verification.');
        }
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isHr, navigate, token]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[var(--color-bg)]">
      <div className="card max-w-lg w-full p-8 text-center space-y-4">
        {brandLogo ? (
          <img src={brandLogo} alt={brandName} className="h-12 w-auto mx-auto logo-on-white" />
        ) : (
          <DualCompanyLogos height={48} />
        )}
        <div className="mx-auto w-14 h-14 rounded-full bg-orange-50 text-primary-accent flex items-center justify-center">
          {loading ? <Loader2 className="animate-spin" size={28} /> : <ShieldCheck size={28} />}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary-accent mb-1">{brandName}</p>
          <h1 className="text-2xl font-bold text-col">
            {isHr ? 'HR / Admin interview room' : 'Interview verification'}
          </h1>
        </div>
        {loading ? (
          <p className="text-sm text-muted">
            {isHr
              ? 'Opening the interview room for HR / Admin…'
              : 'Preparing identity verification before your in-app AI interview…'}
          </p>
        ) : (
          <>
            <p className="text-sm text-red-600">{typeof error === 'string' ? error : JSON.stringify(error)}</p>
            {isHr ? (
              <button type="button" className="btn-secondary" onClick={() => navigate('/login')}>
                HR login
              </button>
            ) : (
              <p className="text-xs text-muted">
                If you believe this is a mistake, please contact HR for assistance.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
