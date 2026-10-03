import { AlertTriangle, Clock3, Link2, CheckCircle2 } from 'lucide-react';

const ICONS = {
  clock: Clock3,
  link: Link2,
  check: CheckCircle2,
  warning: AlertTriangle,
};

export default function ErrorPage({ title, message, icon = 'warning', companyName }) {
  const Icon = ICONS[icon] || AlertTriangle;
  const tone =
    icon === 'check'
      ? 'bg-green-100 text-green-600'
      : icon === 'clock'
        ? 'bg-amber-100 text-amber-700'
        : 'bg-orange-100 text-orange-700';
  const recruiterBrand = companyName || 'RR Global';

  return (
    <div className="card text-center py-12 px-6 max-w-lg mx-auto">
      <div className={`w-16 h-16 rounded-2xl ${tone} flex items-center justify-center mx-auto mb-5`}>
        <Icon size={28} />
      </div>
      <h2 className="text-2xl font-bold text-col mb-2">{title}</h2>
      <p className="text-muted leading-relaxed">{message}</p>
      <p className="text-xs text-muted mt-6">
        Need help? Contact your {recruiterBrand} recruiter.
      </p>
    </div>
  );
}
