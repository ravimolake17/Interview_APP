import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { CalendarDays, Briefcase, Mail, User, Hash, Sparkles } from 'lucide-react';
import { validateToken, bookSlot } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import AvailableSlots from '../components/AvailableSlots';
import ConfirmationDialog from '../components/ConfirmationDialog';
import ErrorPage from '../components/ErrorPage';
import SuccessPage from '../components/SuccessPage';
import { companyDisplayName, companyLogoSrc, applyCompanyTabBrand } from '../utils/companyBranding';
import DualCompanyLogos from '../components/DualCompanyLogos';

function ScheduleShell({ children, company }) {
  const known = Boolean(company?.name || company?.code);
  const name = known ? companyDisplayName(company) : 'RR Global';
  const logo = known ? companyLogoSrc(company) : null;
  useEffect(() => {
    applyCompanyTabBrand(company, { titleSuffix: 'Interview scheduling' });
  }, [company]);
  return (
    <div className="min-h-screen relative overflow-hidden">
      <div
        className="absolute inset-0 -z-10"
        style={{
          background:
            'radial-gradient(1200px 600px at 10% -10%, color-mix(in srgb, var(--color-primary) 18%, white), transparent 60%), radial-gradient(900px 500px at 100% 0%, color-mix(in srgb, var(--color-primary-light) 16%, white), transparent 55%), linear-gradient(180deg, #fff8f1 0%, #f8fafc 45%, #ffffff 100%)',
        }}
      />
      <div
        className="absolute inset-0 -z-10 opacity-[0.35]"
        style={{
          backgroundImage:
            'linear-gradient(var(--color-border) 1px, transparent 1px), linear-gradient(90deg, var(--color-border) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(ellipse at center, black 20%, transparent 75%)',
        }}
      />

      <header className="border-b border-col/70 bg-white/70 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {logo ? (
              <img src={logo} alt={name} className="h-9 w-auto logo-on-white" />
            ) : (
              <DualCompanyLogos height={36} />
            )}
            <div className="leading-tight hidden sm:block">
              <p className="text-sm font-semibold text-col">{name}</p>
              <p className="text-xs text-muted">Recruitment System</p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full bg-orange-50 text-orange-700 border border-orange-100">
            <CalendarDays size={13} />
            Interview booking
          </span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8 sm:py-12">{children}</main>

      <footer className="pb-8 text-center text-xs text-muted">
        © {new Date().getFullYear()} RR Global · {name} Recruitment
      </footer>
    </div>
  );
}

export default function ScheduleInterview() {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [candidate, setCandidate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [serverNow, setServerNow] = useState(null);
  const [serverToday, setServerToday] = useState(null);
  const [error, setError] = useState(null);
  const [errorType, setErrorType] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [showDialog, setShowDialog] = useState(false);
  const [booked, setBooked] = useState(false);
  const [bookingResult, setBookingResult] = useState(null);
  const [selectedSlotId, setSelectedSlotId] = useState(null);
  const company = candidate
    ? { name: candidate.company_name, code: candidate.company_code }
    : null;

  useEffect(() => {
    async function loadToken() {
      try {
        const { data } = await validateToken(token);
        if (data.already_booked) {
          setErrorType('already_booked');
          setCandidate(data);
          return;
        }
        if (!data.valid) {
          if (data.error?.toLowerCase().includes('expired')) {
            setErrorType('expired');
          } else if (data.error?.toLowerCase().includes('invalid')) {
            setErrorType('invalid');
          } else if (data.error?.toLowerCase().includes('already been used')) {
            setErrorType('already_booked');
          } else {
            setErrorType('error');
          }
          setError(data.error);
          setCandidate(data);
          return;
        }
        setCandidate(data);
        setSlots(data.slots || []);
        setServerNow(data.server_now || null);
        setServerToday(data.server_today || null);
      } catch (err) {
        setErrorType('error');
        setError(err.response?.data?.detail || 'Failed to validate scheduling link.');
      } finally {
        setLoading(false);
      }
    }
    loadToken();
  }, [token]);

  const handleSelectSlot = (slot) => {
    setSelectedSlot(slot);
    setShowDialog(true);
  };

  const handleConfirm = async () => {
    setBooking(true);
    try {
      const { data } = await bookSlot(token, selectedSlot.id);
      setSelectedSlotId(selectedSlot.id);
      setBookingResult(data);
      setBooked(true);
      setShowDialog(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to book slot. Please try another time.');
      setShowDialog(false);
    } finally {
      setBooking(false);
    }
  };

  if (loading) {
    return (
      <ScheduleShell company={company}>
        <div className="card p-12 flex justify-center">
          <LoadingSpinner message="Validating your scheduling link..." />
        </div>
      </ScheduleShell>
    );
  }

  if (errorType === 'expired') {
    return (
      <ScheduleShell company={company}>
        <ErrorPage
          title="Link Expired"
          message="This scheduling link has expired. Please contact HR to request a new link."
          icon="clock"
          companyName={candidate?.company_name}
        />
      </ScheduleShell>
    );
  }

  if (errorType === 'invalid') {
    return (
      <ScheduleShell company={company}>
        <ErrorPage
          title="Invalid Link"
          message="This scheduling link is invalid. Please check the link in your email."
          icon="link"
          companyName={candidate?.company_name}
        />
      </ScheduleShell>
    );
  }

  if (errorType === 'already_booked') {
    return (
      <ScheduleShell company={company}>
        <ErrorPage
          title="Already Scheduled"
          message={`Hi ${candidate?.full_name || 'there'}, your interview has already been scheduled. Check your email for details.`}
          icon="check"
          companyName={candidate?.company_name}
        />
      </ScheduleShell>
    );
  }

  if (booked && bookingResult) {
    return (
      <ScheduleShell company={company}>
        <SuccessPage booking={bookingResult} candidate={candidate} />
      </ScheduleShell>
    );
  }

  const infoItems = [
    { label: 'Candidate ID', value: candidate?.candidate_id, icon: Hash },
    { label: 'Name', value: candidate?.full_name, icon: User },
    { label: 'Email', value: candidate?.email, icon: Mail },
    { label: 'Job Position', value: candidate?.job_position || 'Open Position', icon: Briefcase },
  ];

  return (
    <ScheduleShell company={company}>
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28 }}
        className="space-y-6"
      >
        <div className="text-center sm:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 text-orange-700 text-xs font-medium border border-orange-100 mb-3">
            <Sparkles size={13} />
            Candidate scheduling portal
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-col tracking-tight">
            Schedule your interview
          </h1>
          <p className="text-muted mt-2 max-w-2xl">
            Pick a date on the calendar, then choose one of that day’s open times. Once confirmed,
            you will receive an email with your interview date and time. The room opens 5 minutes
            before your scheduled slot.
          </p>
        </div>

        <div className="card overflow-hidden">
          <div
            className="px-5 sm:px-6 py-4 border-b border-col"
            style={{
              background:
                'linear-gradient(135deg, color-mix(in srgb, var(--color-primary) 12%, white), color-mix(in srgb, var(--color-primary-light) 8%, white))',
            }}
          >
            <p className="text-xs font-semibold uppercase tracking-wider text-primary-accent">
              Your details
            </p>
            <p className="text-sm text-muted mt-0.5">Confirm this looks correct before booking</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-4 p-5 sm:p-6">
            {infoItems.map(({ label, value, icon: Icon }) => (
              <div
                key={label}
                className="rounded-xl border border-col bg-slate-50/70 dark:bg-slate-800/30 px-4 py-3"
              >
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted mb-1">
                  <Icon size={12} className="text-primary-accent" />
                  {label}
                </div>
                <p className="font-semibold text-col break-all">{value || '—'}</p>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 text-red-700 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <div className="card p-5 sm:p-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-9 h-9 rounded-xl bg-orange-100 text-orange-700 flex items-center justify-center">
              <CalendarDays size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-col">Choose a date, then a time</h2>
              <p className="text-xs text-muted">Only dates with open slots are selectable</p>
            </div>
          </div>
          <AvailableSlots
            slots={slots}
            onSelect={handleSelectSlot}
            selectedSlotId={selectedSlotId}
            disabled={booked}
            serverNow={serverNow}
            serverToday={serverToday}
          />
        </div>
      </motion.div>

      {showDialog && (
        <ConfirmationDialog
          slot={selectedSlot}
          onConfirm={handleConfirm}
          onCancel={() => setShowDialog(false)}
          loading={booking}
        />
      )}
    </ScheduleShell>
  );
}
