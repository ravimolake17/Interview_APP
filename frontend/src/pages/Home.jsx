import { Link } from 'react-router-dom';
import DualCompanyLogos from '../components/DualCompanyLogos';
import { useAuth } from '../context/AuthContext';

export default function Home() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="space-y-6">
      <div className="card text-center py-12">
        <DualCompanyLogos height={56} className="mb-5" />
        <h2 className="text-3xl font-semibold text-hr-800 mb-4">
          RR Global Recruitment System
        </h2>
        <p className="text-gray-600 max-w-2xl mx-auto mb-8">
          Agent 1 parses resumes and shortlists candidates using the job description title and
          contact details from the resume. Agent 2 emails shortlisted candidates and tracks
          interviews on the HR calendar.
        </p>

        <div className="grid sm:grid-cols-3 gap-4 max-w-3xl mx-auto text-left">
          {isAuthenticated ? (
            <a
              href="http://localhost:8030/screening/"
              className="block p-5 rounded-lg border border-hr-200 hover:border-hr-400 hover:bg-hr-50 transition-colors"
            >
              <h3 className="font-semibold text-hr-800 mb-1">Agent 1 — Screening</h3>
              <p className="text-sm text-gray-500">Upload resume + JD → shortlist with job title from JD</p>
            </a>
          ) : (
            <Link
              to="/login"
              className="block p-5 rounded-lg border border-hr-200 hover:border-hr-400 hover:bg-hr-50 transition-colors"
            >
              <h3 className="font-semibold text-hr-800 mb-1">Agent 1 — Screening</h3>
              <p className="text-sm text-gray-500">Sign in first, then open resume screening in this tab</p>
            </Link>
          )}

          <Link
            to="/login"
            className="block p-5 rounded-lg border border-hr-200 hover:border-hr-400 hover:bg-hr-50 transition-colors"
          >
            <h3 className="font-semibold text-hr-800 mb-1">HR Candidate Review</h3>
            <p className="text-sm text-gray-500">
              Sign in to review candidates — shortlist, reject, resend emails, audit trail
            </p>
          </Link>

          <Link
            to="/login"
            className="block p-5 rounded-lg border border-hr-200 hover:border-hr-400 hover:bg-hr-50 transition-colors"
          >
            <h3 className="font-semibold text-hr-800 mb-1">HR Calendar</h3>
            <p className="text-sm text-gray-500">Sign in to view scheduled interviews with candidate name &amp; ID</p>
          </Link>
        </div>
      </div>

      <div className="card bg-hr-50 border-hr-100">
        <h3 className="font-semibold text-hr-800 mb-2">Data flow from Agent 1</h3>
        <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
          <li><strong>Job position</strong> — parsed from the job description (not hardcoded)</li>
          <li><strong>Name &amp; email</strong> — extracted from the resume</li>
          <li><strong>All outcomes saved</strong> — shortlisted, needs review, and rejected appear in HR review</li>
          <li><strong>Resend email</strong> — only before the candidate books an interview slot</li>
          <li><strong>Calendar</strong> — appears after the candidate books a slot</li>
        </ul>
      </div>
    </div>
  );
}
