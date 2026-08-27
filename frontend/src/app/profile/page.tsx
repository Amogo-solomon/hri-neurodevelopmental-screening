'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  User, Shield, Key, LogOut, Save, Loader2,
  AlertCircle, CheckCircle2, Eye, EyeOff, ArrowLeft,
  Check, X,
} from 'lucide-react';
import { api, apiLogout, apiChangePassword } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import type { AuthUser } from '@/types/auth';
import { format } from 'date-fns';
import { clsx } from 'clsx';

const RULES = [
  { id: 'len',   label: 'At least 8 chars',   test: (p: string) => p.length >= 8 },
  { id: 'upper', label: 'Uppercase',           test: (p: string) => /[A-Z]/.test(p) },
  { id: 'lower', label: 'Lowercase',           test: (p: string) => /[a-z]/.test(p) },
  { id: 'digit', label: 'Number',              test: (p: string) => /\d/.test(p) },
  { id: 'spec',  label: 'Special char',        test: (p: string) => /[@$!%*?&_\-#]/.test(p) },
];

const ROLE_BADGE: Record<string, string> = {
  admin:      'bg-purple-500/20 text-purple-300 border-purple-500/30',
  clinician:  'bg-blue-500/20   text-blue-300   border-blue-500/30',
  researcher: 'bg-cyan-500/20   text-cyan-300   border-cyan-500/30',
};

export default function ProfilePage() {
  const router    = useRouter();
  const qc        = useQueryClient();
  const { logout: storeLogout, setUser } = useAuthStore();

  // Profile edit state
  const [editName, setEditName]   = useState('');
  const [editInst, setEditInst]   = useState('');
  const [editMode, setEditMode]   = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Password state
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' });
  const [showCur, setShowCur] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [pwMsg, setPwMsg]    = useState<{ ok: boolean; text: string } | null>(null);

  const score   = RULES.filter(r => r.test(pwForm.next)).length;
  const pwMatch = pwForm.next === pwForm.confirm && pwForm.confirm.length > 0;

  const { data: me, isLoading } = useQuery<AuthUser>({
    queryKey: ['me'],
    queryFn: async () => {
      const { data } = await api.get('/auth/me');
      return data;
    },
    onSuccess: (u: AuthUser) => {
      if (!editMode) { setEditName(u.full_name); setEditInst(u.institution || ''); }
    },
  } as any);

  const { mutate: saveProfile, isPending: savingProfile } = useMutation({
    mutationFn: () => api.put('/auth/me', { full_name: editName, institution: editInst }),
    onSuccess: (res: any) => {
      setUser(res.data);
      qc.invalidateQueries({ queryKey: ['me'] });
      setEditMode(false);
      setProfileMsg({ ok: true, text: 'Profile updated successfully.' });
      setTimeout(() => setProfileMsg(null), 3000);
    },
    onError: () => setProfileMsg({ ok: false, text: 'Failed to update profile.' }),
  });

  const { mutate: changePw, isPending: changingPw } = useMutation({
    mutationFn: () => apiChangePassword(pwForm.current, pwForm.next),
    onSuccess: () => {
      setPwForm({ current: '', next: '', confirm: '' });
      setPwMsg({ ok: true, text: 'Password changed. All other sessions have been signed out.' });
      setTimeout(() => setPwMsg(null), 5000);
    },
    onError: (e: any) =>
      setPwMsg({ ok: false, text: e?.response?.data?.detail || 'Password change failed.' }),
  });

  const handleLogout = async () => {
    await apiLogout();
    storeLogout();
    router.replace('/login');
  };

  if (isLoading || !me) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950">
        <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">

        {/* Back */}
        <button onClick={() => router.push('/')}
          className="flex items-center gap-2 text-slate-400 hover:text-white text-sm transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to platform
        </button>

        <h1 className="text-2xl font-bold text-white">Account Settings</h1>

        {/* ── Profile card ─────────────────────────────────────────────── */}
        <div className="glass-card overflow-hidden">
          <div className="flex items-center gap-4 px-6 py-5 border-b border-slate-700/50">
            <div className="w-14 h-14 rounded-full bg-brand-600/30 flex items-center justify-center flex-shrink-0">
              <User className="w-7 h-7 text-brand-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-lg font-semibold text-white truncate">{me.full_name}</p>
              <p className="text-sm text-slate-400 truncate">{me.email}</p>
            </div>
            <span className={clsx(
              'metric-badge border text-sm flex-shrink-0',
              ROLE_BADGE[me.role] ?? 'bg-slate-600/20 text-slate-300 border-slate-600',
            )}>
              <Shield className="w-3.5 h-3.5" />
              {me.role}
            </span>
          </div>

          <div className="p-6 space-y-5">
            {profileMsg && (
              <div className={clsx(
                'flex items-center gap-2 p-3 rounded-xl text-sm border',
                profileMsg.ok
                  ? 'bg-green-500/10 border-green-500/30 text-green-300'
                  : 'bg-red-500/10   border-red-500/30   text-red-300',
              )}>
                {profileMsg.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                {profileMsg.text}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">Full name</label>
                <input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  disabled={!editMode || savingProfile}
                  className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 text-sm
                             text-white focus:outline-none focus:border-brand-500 transition-colors
                             disabled:opacity-60 disabled:cursor-default"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">Institution</label>
                <input
                  value={editInst}
                  onChange={e => setEditInst(e.target.value)}
                  disabled={!editMode || savingProfile}
                  placeholder="University / Organisation"
                  className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 text-sm
                             text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500
                             transition-colors disabled:opacity-60 disabled:cursor-default"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs text-slate-400">
              <div>Member since: <span className="text-slate-300">{format(new Date(me.created_at), 'dd MMM yyyy')}</span></div>
              {me.last_login_at && (
                <div>Last login: <span className="text-slate-300">{format(new Date(me.last_login_at), 'dd MMM yyyy HH:mm')}</span></div>
              )}
            </div>

            <div className="flex gap-3">
              {editMode ? (
                <>
                  <button
                    onClick={() => saveProfile()}
                    disabled={savingProfile}
                    className="btn-primary py-2 px-4"
                  >
                    {savingProfile ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Save changes
                  </button>
                  <button onClick={() => { setEditMode(false); setEditName(me.full_name); setEditInst(me.institution || ''); }}
                    className="btn-secondary py-2 px-4">
                    Cancel
                  </button>
                </>
              ) : (
                <button onClick={() => setEditMode(true)} className="btn-secondary py-2 px-4">
                  Edit profile
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ── Change password ───────────────────────────────────────────── */}
        <div className="glass-card p-6 space-y-5">
          <h2 className="section-title flex items-center gap-2">
            <Key className="w-4 h-4 text-brand-400" />
            Change Password
          </h2>

          {pwMsg && (
            <div className={clsx(
              'flex items-center gap-2 p-3 rounded-xl text-sm border',
              pwMsg.ok
                ? 'bg-green-500/10 border-green-500/30 text-green-300'
                : 'bg-red-500/10   border-red-500/30   text-red-300',
            )}>
              {pwMsg.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
              {pwMsg.text}
            </div>
          )}

          <div className="space-y-4">
            {/* Current password */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Current password</label>
              <div className="relative">
                <input
                  type={showCur ? 'text' : 'password'}
                  value={pwForm.current}
                  onChange={e => setPwForm({ ...pwForm, current: e.target.value })}
                  disabled={changingPw}
                  placeholder="••••••••"
                  className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 pr-11
                             text-sm text-white placeholder:text-slate-500 focus:outline-none
                             focus:border-brand-500 transition-colors disabled:opacity-50"
                />
                <button type="button" tabIndex={-1}
                  onClick={() => setShowCur(!showCur)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                  {showCur ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* New password */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">New password</label>
              <div className="relative">
                <input
                  type={showNew ? 'text' : 'password'}
                  value={pwForm.next}
                  onChange={e => setPwForm({ ...pwForm, next: e.target.value })}
                  disabled={changingPw}
                  placeholder="••••••••"
                  className="w-full bg-slate-800 border border-slate-600 rounded-xl px-4 py-2.5 pr-11
                             text-sm text-white placeholder:text-slate-500 focus:outline-none
                             focus:border-brand-500 transition-colors disabled:opacity-50"
                />
                <button type="button" tabIndex={-1}
                  onClick={() => setShowNew(!showNew)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                  {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {pwForm.next && (
                <div className="grid grid-cols-2 gap-1 pt-1">
                  {RULES.map(r => (
                    <div key={r.id} className={clsx(
                      'flex items-center gap-1 text-xs',
                      r.test(pwForm.next) ? 'text-green-400' : 'text-slate-500',
                    )}>
                      {r.test(pwForm.next) ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
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
                value={pwForm.confirm}
                onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })}
                disabled={changingPw}
                placeholder="••••••••"
                className={clsx(
                  'w-full bg-slate-800 border rounded-xl px-4 py-2.5 text-sm text-white',
                  'placeholder:text-slate-500 focus:outline-none transition-colors disabled:opacity-50',
                  pwForm.confirm.length > 0
                    ? pwMatch ? 'border-green-500' : 'border-red-500'
                    : 'border-slate-600 focus:border-brand-500',
                )}
              />
            </div>

            <button
              onClick={() => changePw()}
              disabled={changingPw || score < 5 || !pwMatch || !pwForm.current}
              className="btn-primary py-2.5 px-5"
            >
              {changingPw ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
              {changingPw ? 'Changing…' : 'Change password'}
            </button>
          </div>
        </div>

        {/* ── Sign out ──────────────────────────────────────────────────── */}
        <div className="glass-card p-6 space-y-3">
          <h2 className="section-title flex items-center gap-2">
            <LogOut className="w-4 h-4 text-red-400" />
            Sign Out
          </h2>
          <p className="text-sm text-slate-400">
            This will sign you out of this device and revoke your current session.
          </p>
          <button onClick={handleLogout}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium
                       bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300
                       transition-colors">
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
