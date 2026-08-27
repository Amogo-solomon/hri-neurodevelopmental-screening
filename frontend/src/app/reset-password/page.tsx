'use client';
import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Brain, Loader2, AlertCircle, CheckCircle2, Eye, EyeOff, Lock, Check, X } from 'lucide-react';
import { apiConfirmPasswordReset } from '@/lib/authApi';
import { clsx } from 'clsx';

const RULES = [
  { id: 'len',   label: 'At least 8 characters',                   test: (p: string) => p.length >= 8 },
  { id: 'upper', label: 'Uppercase letter',                         test: (p: string) => /[A-Z]/.test(p) },
  { id: 'lower', label: 'Lowercase letter',                         test: (p: string) => /[a-z]/.test(p) },
  { id: 'digit', label: 'Number',                                   test: (p: string) => /\d/.test(p) },
  { id: 'spec',  label: 'Special character',                        test: (p: string) => /[@$!%*?&_\-#]/.test(p) },
];

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token  = params.get('token') || '';

  const [password, setPassword]     = useState('');
  const [confirm, setConfirm]       = useState('');
  const [showPw, setShowPw]         = useState(false);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [done, setDone]             = useState(false);

  const score   = RULES.filter(r => r.test(password)).length;
  const pwMatch = password === confirm && confirm.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token)    { setError('Missing reset token. Use the link from your email.'); return; }
    if (score < 5) { setError('Password does not meet all requirements.'); return; }
    if (!pwMatch)  { setError('Passwords do not match.'); return; }
    setLoading(true); setError(null);
    try {
      await apiConfirmPasswordReset(token, password);
      setDone(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Reset failed — the token may have expired.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-card p-8 space-y-5">
      {done ? (
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-full bg-green-500/20 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-green-400" />
            </div>
          </div>
          <h2 className="text-lg font-semibold text-white">Password reset!</h2>
          <p className="text-slate-400 text-sm">Your password has been updated. You can now sign in.</p>
          <button onClick={() => router.push('/login')} className="btn-primary w-full justify-center py-3">
            Sign in
          </button>
        </div>
      ) : (
        <>
          <div>
            <h2 className="text-lg font-semibold text-white">Set a new password</h2>
            <p className="text-slate-400 text-sm mt-1">Choose a strong password for your account.</p>
          </div>

          {!token && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
              No reset token found. Please use the link from your email.
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* New password */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">New password</label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  disabled={loading || !token}
                  className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 pr-11
                             text-sm text-white placeholder:text-slate-500
                             focus:outline-none focus:border-brand-500 transition-colors disabled:opacity-50"
                />
                <button type="button" tabIndex={-1}
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {password && (
                <div className="grid grid-cols-2 gap-1 pt-1">
                  {RULES.map(r => (
                    <div key={r.id} className={clsx(
                      'flex items-center gap-1 text-xs',
                      r.test(password) ? 'text-green-400' : 'text-slate-500',
                    )}>
                      {r.test(password) ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                      {r.label}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Confirm */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Confirm new password</label>
              <input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="••••••••"
                disabled={loading || !token}
                className={clsx(
                  'w-full bg-slate-800 border rounded-xl px-4 py-2.5',
                  'text-sm text-white placeholder:text-slate-500',
                  'focus:outline-none transition-colors disabled:opacity-50',
                  confirm.length > 0
                    ? pwMatch ? 'border-green-500' : 'border-red-500'
                    : 'border-slate-600 focus:border-brand-500',
                )}
              />
            </div>

            <button
              type="submit"
              disabled={loading || score < 5 || !pwMatch || !token}
              className="btn-primary w-full justify-center py-3"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
              {loading ? 'Resetting…' : 'Reset password'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-400">
            <Link href="/login" className="text-brand-400 hover:text-brand-300">← Back to sign in</Link>
          </p>
        </>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6 animate-fade-in">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/30">
              <Brain className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white">Reset password</h1>
          <p className="text-slate-400 text-sm">HRI Behaviour Platform</p>
        </div>
        <Suspense fallback={<div className="glass-card p-8 text-center text-slate-400">Loading…</div>}>
          <ResetForm />
        </Suspense>
      </div>
    </div>
  );
}
