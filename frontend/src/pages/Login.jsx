import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import DualCompanyLogos from '../components/DualCompanyLogos';
import PasswordInput from '../components/PasswordInput';
import SessionSplash from '../components/SessionSplash';
import { useAuth } from '../context/AuthContext';
import { isValidEmail, isValidPassword } from '../utils/validation';
import loginCampus from '../assets/login-campus.jpg';

export default function Login() {
  const { login, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <SessionSplash message="Loading…" />;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const validate = () => {
    const errors = {};
    const emailErr = isValidEmail(email);
    if (emailErr) errors.email = emailErr;
    const passErr = isValidPassword(password);
    if (passErr) errors.password = passErr;
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Check your email and password.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden p-4 bg-[#0b1220]">
      <img
        src={loginCampus}
        alt=""
        className="absolute inset-0 h-full w-full object-cover object-center"
      />
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950/75 via-slate-900/60 to-orange-950/50" />
      <div className="absolute inset-0 login-campus-grid opacity-50" />
      <div className="pointer-events-none absolute left-1/2 top-16 h-64 w-[28rem] -translate-x-1/2 rounded-full bg-orange-500/20 blur-3xl" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="relative z-10 w-full max-w-md rounded-2xl border border-white/80 bg-white/95 p-8 shadow-2xl shadow-slate-950/40 backdrop-blur-md"
      >
        <div className="text-center mb-8">
          <DualCompanyLogos height={52} className="mb-4" />
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 text-orange-700 text-xs font-medium mb-3">
            <Sparkles size={14} />
            Recruitment System
          </div>
          <h1 className="text-2xl font-bold text-col">Sign in to continue</h1>
          <p className="text-sm text-muted mt-2">
            HR portal for screening, candidate review, and scheduling
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-col mb-1.5">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: null }));
              }}
              onBlur={() => {
                const emailErr = isValidEmail(email);
                if (emailErr) setFieldErrors((f) => ({ ...f, email: emailErr }));
              }}
              className={`w-full rounded-xl border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500 ${
                fieldErrors.email ? 'border-red-400' : 'border-col'
              }`}
              placeholder="you@rrglobal.com"
            />
            {fieldErrors.email && (
              <p className="mt-1 text-xs text-red-600">{fieldErrors.email}</p>
            )}
          </div>

          <PasswordInput
            id="password"
            label="Password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: null }));
            }}
            error={fieldErrors.password}
            autoComplete="current-password"
            required
          />

          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || loading}
            className="w-full btn-primary py-2.5 text-sm"
          >
            {submitting ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
