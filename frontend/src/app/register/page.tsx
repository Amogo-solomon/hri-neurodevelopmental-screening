'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Eye, EyeOff, Loader2, Brain, AlertCircle,
  CheckCircle2, UserPlus, Check, X,
} from 'lucide-react';
import { apiRegister } from '@/lib/authApi';
import { clsx } from 'clsx';

/* ── Password strength rules ──────────────────────────────────────────── */
const RULES = [
  { id: 'len',   label: 'At least 8 characters',               test: (p: string) => p.length >= 8 },
  { id: 'upper', label: 'Contains uppercase letter',           test: (p: string) => /[A-Z]/.test(p) },
  { id: 'lower', label: 'Contains lowercase letter',           test: (p: string) => /[a-z]/.test(p) },
  { id: 'digit', label: 'Contains a number',                   test: (p: string) => /\d/.test(p) },
  { id: 'spec',  label: 'Contains special character (@$!%*?&_-#)', test: (p: string) => /[@$!%*?&_\-#]/.test(p) },
];

function strengthScore(pw: string) { return RULES.filter(r => r.test(pw)).length; }
function strengthLabel(s: number) {
  if (s <= 1) return { label: 'Very weak', color: 'bg-red-500' };
  if (s === 2) return { label: 'Weak',     color: 'bg-orange-500' };
  if (s === 3) return { label: 'Fair',     color: 'bg-amber-500' };
  if (s === 4) return { label: 'Good',     color: 'bg-blue-500' };
  return               { label: 'Strong',  color: 'bg-green-500' };
}

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: '', email: '', password: '', confirm: '',
    institution: '', role: 'researcher' as 'researcher' | 'clinician',
  });
  const [showPw, setShowPw]       = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [success, setSuccess]     = useState(false);

  const score  = strengthScore(form.password);
  const { label: sLabel, color: sColor } = strengthLabel(score);
  const pwMatch = form.password === form.confirm && form.confirm.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (score < 5) { setError('Password does not meet all requirements.'); return; }
    if (!pwMatch)  { setError('Passwords do not match.'); return; }

    setLoading(true);
    try {
      await apiRegister({
        email:       form.email,
        full_name:   form.full_name,
        password:    form.password,
        institution: form.institution || undefined,
        role:        form.role,
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md glass-card p-8 text-center space-y-4 animate-fade-in">
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center">
              <CheckCircle2 className="w-9 h-9 text-green-400" />
            </div>
          </div>
          <h2 className="text-xl font-bold text-white">Account created!</h2>
          <p className="text-slate-400 text-sm">
            Your account has been registered. You can now sign in.
          </p>
          <button onClick={() => router.push('/login')} className="btn-primary w-full justify-center py-3">
            Go to sign in
          </button>
        </div>
      </div>
    );
  }

  const field = (
    id: keyof typeof form,
    label: string,
    type = 'text',
    placeholder = '',
    required = true,
  ) => (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-slate-300">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      <input
        type={type}
        value={form[id]}
        onChange={e => setForm({ ...form, [id]: e.target.value })}
        placeholder={placeholder}
        disabled={loading}
        className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 text-sm
                   text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500
                   transition-colors disabled:opacity-50"
      />
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg space-y-6 animate-fade-in">

        {/* Brand */}
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/30">
              <Brain className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Create your account</h1>
          <p className="text-slate-400 text-sm">HRI Behaviour Platform · University of Lincoln</p>
        </div>

        <div className="glass-card p-8 space-y-5">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name + email */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {field('full_name', 'Full name', 'text', 'Dr Jane Smith')}
              {field('email', 'Email address', 'email', 'you@institution.ac.uk')}
            </div>

            {/* Institution + role */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {field('institution', 'Institution', 'text', 'University of Lincoln', false)}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">
                  Role <span className="text-red-400">*</span>
                </label>
                <select
                  value={form.role}
                  onChange={e => setForm({ ...form, role: e.target.value as any })}
                  disabled={loading}
                  className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5
                             text-sm text-white focus:outline-none focus:border-brand-500
                             transition-colors disabled:opacity-50"
                >
                  <option value="researcher">Researcher</option>
                  <option value="clinician">Clinician</option>
                </select>
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">
                Password <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  placeholder="••••••••"
                  disabled={loading}
                  className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 pr-11
                             text-sm text-white placeholder:text-slate-500
                             focus:outline-none focus:border-brand-500 transition-colors"
                />
                <button type="button" tabIndex={-1}
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

              {/* Strength bar */}
              {form.password && (
                <div className="space-y-2 pt-1">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div className={clsx('h-full rounded-full transition-all duration-300', sColor)}
                           style={{ width: `${(score / 5) * 100}%` }} />
                    </div>
                    <span className="text-xs text-slate-400 w-16 text-right">{sLabel}</span>
                  </div>
                  <div className="grid grid-cols-1 gap-1">
                    {RULES.map(r => (
                      <div key={r.id} className={clsx(
                        'flex items-center gap-1.5 text-xs transition-colors',
                        r.test(form.password) ? 'text-green-400' : 'text-slate-500',
                      )}>
                        {r.test(form.password)
                          ? <Check className="w-3 h-3 flex-shrink-0" />
                          : <X     className="w-3 h-3 flex-shrink-0" />}
                        {r.label}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Confirm password */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">
                Confirm password <span className="text-red-400">*</span>
              </label>
              <div className="relative">
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={form.confirm}
                  onChange={e => setForm({ ...form, confirm: e.target.value })}
                  placeholder="••••••••"
                  disabled={loading}
                  className={clsx(
                    'w-full bg-slate-800 border rounded-xl px-4 py-2.5 pr-11',
                    'text-sm text-white placeholder:text-slate-500',
                    'focus:outline-none transition-colors',
                    form.confirm.length > 0
                      ? pwMatch ? 'border-green-500' : 'border-red-500'
                      : 'border-slate-600 focus:border-brand-500',
                  )}
                />
                <button type="button" tabIndex={-1}
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                  {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {form.confirm.length > 0 && !pwMatch && (
                <p className="text-xs text-red-400">Passwords do not match</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || score < 5 || !pwMatch}
              className="btn-primary w-full justify-center py-3 mt-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-400">
            Already have an account?{' '}
            <Link href="/login" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
              Sign in
            </Link>
          </p>
        </div>

        <p className="text-center text-xs text-slate-600 px-4">
          By registering you confirm this is for authorised research purposes only.
          All use is logged per NHS DSP Toolkit and UK GDPR Article 30.
        </p>
      </div>
    </div>
  );
}
