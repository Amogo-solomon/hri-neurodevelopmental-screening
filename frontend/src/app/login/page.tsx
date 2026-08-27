'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, Brain, AlertCircle, LogIn } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { apiLogin } from '@/lib/authApi';
import { clsx } from 'clsx';

export default function LoginPage() {
  const router = useRouter();
  const { setUser } = useAuthStore();

  const [form, setForm]       = useState({ email: '', password: '' });
  const [showPw, setShowPw]   = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email || !form.password) {
      setError('Please enter your email and password.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const user = await apiLogin(form.email, form.password);
      setUser(user);
      router.replace('/');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6 animate-fade-in">

        {/* Brand header */}
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/30">
              <Brain className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            HRI Behaviour Platform
          </h1>
          <p className="text-slate-400 text-sm">
            University of Lincoln · MSc Cloud Computing
          </p>
        </div>

        {/* Card */}
        <div className="glass-card p-8 space-y-6">
          <div className="text-center">
            <h2 className="text-lg font-semibold text-white">Sign in to your account</h2>
            <p className="text-slate-400 text-sm mt-1">Research platform — authorised users only</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Email address</label>
              <input
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@institution.ac.uk"
                className={clsx(
                  'w-full bg-slate-800 border rounded-xl px-4 py-2.5 text-sm text-white',
                  'placeholder:text-slate-500 focus:outline-none focus:border-brand-500',
                  'transition-colors border-slate-600',
                )}
                disabled={loading}
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-300">Password</label>
                <Link href="/forgot-password"
                  className="text-xs text-brand-400 hover:text-brand-300 transition-colors">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="••••••••"
                  className={clsx(
                    'w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 pr-11',
                    'text-sm text-white placeholder:text-slate-500',
                    'focus:outline-none focus:border-brand-500 transition-colors',
                  )}
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-3 mt-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-400">
            Don't have an account?{' '}
            <Link href="/register" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
              Register
            </Link>
          </p>
        </div>

        {/* Compliance note */}
        <p className="text-center text-xs text-slate-600 px-4">
          Access is restricted to authorised researchers and clinicians. All access is logged for audit compliance (NHS DSP Toolkit / UK GDPR Article 30).
        </p>
      </div>
    </div>
  );
}
