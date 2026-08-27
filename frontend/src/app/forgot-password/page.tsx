'use client';
import { useState } from 'react';
import Link from 'next/link';
import { Brain, Mail, Loader2, AlertCircle, CheckCircle2, ArrowLeft } from 'lucide-react';
import { apiRequestPasswordReset } from '@/lib/authApi';

export default function ForgotPasswordPage() {
  const [email, setEmail]     = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [sent, setSent]       = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) { setError('Please enter your email address.'); return; }
    setLoading(true); setError(null);
    try {
      const res = await apiRequestPasswordReset(email);
      // In dev mode the API returns the token directly
      if (res?.reset_token) setDevToken(res.reset_token);
      setSent(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6 animate-fade-in">

        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/30">
              <Brain className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white">Reset your password</h1>
          <p className="text-slate-400 text-sm">HRI Behaviour Platform · University of Lincoln</p>
        </div>

        <div className="glass-card p-8 space-y-5">
          {sent ? (
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="w-14 h-14 rounded-full bg-green-500/20 flex items-center justify-center">
                  <CheckCircle2 className="w-8 h-8 text-green-400" />
                </div>
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Check your email</h2>
                <p className="text-slate-400 text-sm mt-1">
                  If <span className="text-white">{email}</span> is registered, a reset link has been sent.
                </p>
              </div>
              {devToken && (
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-left">
                  <p className="text-xs text-amber-300 font-medium mb-1">⚠ Dev mode — reset token:</p>
                  <p className="text-xs font-mono text-amber-200 break-all">{devToken}</p>
                  <Link
                    href={`/reset-password?token=${devToken}`}
                    className="text-xs text-brand-400 hover:underline mt-2 block"
                  >
                    → Use this token to reset password
                  </Link>
                </div>
              )}
              <Link href="/login" className="btn-secondary w-full justify-center py-2.5 block text-center">
                <ArrowLeft className="w-4 h-4" /> Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <div>
                <h2 className="text-lg font-semibold text-white">Forgot your password?</h2>
                <p className="text-slate-400 text-sm mt-1">
                  Enter your registered email and we'll send you a reset link.
                </p>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-300">Email address</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="you@institution.ac.uk"
                      disabled={loading}
                      className="w-full bg-slate-800 border border-slate-600 rounded-xl pl-10 pr-4 py-2.5
                                 text-sm text-white placeholder:text-slate-500
                                 focus:outline-none focus:border-brand-500 transition-colors"
                    />
                  </div>
                </div>
                <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-3">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>

              <p className="text-center text-sm text-slate-400">
                Remember it?{' '}
                <Link href="/login" className="text-brand-400 hover:text-brand-300 font-medium">Sign in</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
