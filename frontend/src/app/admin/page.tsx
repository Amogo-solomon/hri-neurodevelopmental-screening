'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  Shield, Users, ScrollText, Loader2, AlertCircle,
  UserPlus, Trash2, CheckCircle2, ArrowLeft,
  ToggleLeft, ToggleRight, Eye, EyeOff,
} from 'lucide-react';
import {
  apiAdminListUsers, apiAdminUpdateUser,
  apiAdminDeleteUser, apiAdminCreateUser, apiAuditLog,
} from '@/lib/authApi';
import { useAuthStore } from '@/store/authStore';
import type { AuthUser } from '@/types/auth';
import { format } from 'date-fns';
import { clsx } from 'clsx';

const ROLE_BADGE: Record<string, string> = {
  admin:      'bg-purple-500/20 text-purple-300',
  clinician:  'bg-blue-500/20   text-blue-300',
  researcher: 'bg-cyan-500/20   text-cyan-300',
};

const ACTION_COLOUR: Record<string, string> = {
  login:                    'text-green-400',
  logout:                   'text-slate-400',
  register:                 'text-blue-400',
  login_failed:             'text-red-400',
  password_changed:         'text-amber-400',
  password_reset_requested: 'text-amber-400',
  token_replay_detected:    'text-red-500',
  admin_created_user:       'text-purple-400',
  admin_updated_user:       'text-purple-400',
  admin_deleted_user:       'text-red-400',
};

export default function AdminPage() {
  const router          = useRouter();
  const { user }        = useAuthStore();
  const qc              = useQueryClient();
  const [tab, setTab]   = useState<'users' | 'audit'>('users');

  const [showNewUser, setShowNewUser] = useState(false);
  const [newUser, setNewUser] = useState({
    full_name: '', email: '', password: '', role: 'researcher', institution: '',
  });
  const [showNewPw, setShowNewPw] = useState(false);
  const [formMsg, setFormMsg]     = useState<{ ok: boolean; text: string } | null>(null);

  // ── ALL HOOKS MUST BE BEFORE ANY CONDITIONAL RETURN ──────────────────────
  const { data: users = [], isLoading: loadingUsers } = useQuery({
    queryKey: ['admin-users'],
    queryFn: apiAdminListUsers,
    enabled: tab === 'users' && user?.role === 'admin',
  });

  const { data: auditLogs = [], isLoading: loadingAudit } = useQuery({
    queryKey: ['audit-log'],
    queryFn: apiAuditLog,
    enabled: tab === 'audit' && user?.role === 'admin',
  });

  const { mutate: toggleActive } = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiAdminUpdateUser(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const { mutate: changeRole } = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      apiAdminUpdateUser(id, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const { mutate: deleteUser } = useMutation({
    mutationFn: apiAdminDeleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const { mutate: createUser, isPending: creating } = useMutation({
    mutationFn: () => apiAdminCreateUser({
      email: newUser.email,
      full_name: newUser.full_name,
      password: newUser.password,
      role: newUser.role,
      institution: newUser.institution || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setNewUser({ full_name: '', email: '', password: '', role: 'researcher', institution: '' });
      setShowNewUser(false);
      setFormMsg({ ok: true, text: 'User created successfully.' });
      setTimeout(() => setFormMsg(null), 3000);
    },
    onError: (e: any) =>
      setFormMsg({ ok: false, text: e?.response?.data?.detail || 'Failed to create user.' }),
  });
  // ── END OF HOOKS ──────────────────────────────────────────────────────────

  // Now safe to do conditional renders
  if (user && user.role !== 'admin') {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="glass-card p-8 text-center space-y-3 max-w-sm">
          <Shield className="w-10 h-10 text-red-400 mx-auto" />
          <p className="text-white font-semibold">Access Denied</p>
          <p className="text-slate-400 text-sm">This page is restricted to administrators.</p>
          <button onClick={() => router.push('/')} className="btn-secondary py-2 px-4 w-full justify-center">
            Go home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">

        <div className="flex items-center gap-4">
          <button onClick={() => router.push('/')} className="text-slate-400 hover:text-white transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Shield className="w-6 h-6 text-purple-400" /> Admin Panel
            </h1>
            <p className="text-slate-400 text-sm">User management and audit trail</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-800/60 rounded-xl p-1 w-fit">
          {[
            { id: 'users', icon: Users,      label: 'Users' },
            { id: 'audit', icon: ScrollText, label: 'Audit Log' },
          ].map(({ id, icon: Icon, label }) => (
            <button key={id} onClick={() => setTab(id as any)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                tab === id ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white',
              )}>
              <Icon className="w-4 h-4" />{label}
            </button>
          ))}
        </div>

        {/* Users tab */}
        {tab === 'users' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-slate-400 text-sm">{users.length} registered users</p>
              <button onClick={() => setShowNewUser(!showNewUser)} className="btn-primary py-2 px-4 text-sm">
                <UserPlus className="w-4 h-4" /> New user
              </button>
            </div>

            {showNewUser && (
              <div className="glass-card p-5 space-y-4 animate-slide-up border border-brand-600/30">
                <h3 className="section-title text-sm">Create new user</h3>
                {formMsg && (
                  <div className={clsx(
                    'flex items-center gap-2 p-3 rounded-xl text-sm',
                    formMsg.ok ? 'bg-green-500/10 text-green-300' : 'bg-red-500/10 text-red-300',
                  )}>
                    {formMsg.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                    {formMsg.text}
                  </div>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    { key: 'full_name',    label: 'Full name',    ph: 'Dr Jane Smith' },
                    { key: 'email',        label: 'Email',        ph: 'user@institution.ac.uk' },
                    { key: 'institution',  label: 'Institution',  ph: 'University of Lincoln' },
                  ].map(({ key, label, ph }) => (
                    <div key={key} className="space-y-1">
                      <label className="text-xs text-slate-300">{label}</label>
                      <input
                        value={(newUser as any)[key]}
                        onChange={(e) => setNewUser({ ...newUser, [key]: e.target.value })}
                        placeholder={ph}
                        disabled={creating}
                        className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2
                                   text-sm text-white placeholder:text-slate-500 focus:outline-none
                                   focus:border-brand-500 transition-colors disabled:opacity-50"
                      />
                    </div>
                  ))}
                  <div className="space-y-1">
                    <label className="text-xs text-slate-300">Password</label>
                    <div className="relative">
                      <input
                        type={showNewPw ? 'text' : 'password'}
                        value={newUser.password}
                        onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                        placeholder="Min 8 chars, mixed case + digit + symbol"
                        disabled={creating}
                        className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2 pr-9
                                   text-sm text-white placeholder:text-slate-500 focus:outline-none
                                   focus:border-brand-500 transition-colors disabled:opacity-50"
                      />
                      <button type="button" tabIndex={-1} onClick={() => setShowNewPw(!showNewPw)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                        {showNewPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-300">Role</label>
                    <select
                      value={newUser.role}
                      onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                      disabled={creating}
                      className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2
                                 text-sm text-white focus:outline-none focus:border-brand-500
                                 transition-colors disabled:opacity-50"
                    >
                      <option value="researcher">Researcher</option>
                      <option value="clinician">Clinician</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => createUser()}
                    disabled={creating || !newUser.email || !newUser.full_name || !newUser.password}
                    className="btn-primary py-2 px-4 text-sm"
                  >
                    {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                    {creating ? 'Creating...' : 'Create user'}
                  </button>
                  <button onClick={() => setShowNewUser(false)} className="btn-secondary py-2 px-4 text-sm">
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="glass-card overflow-hidden">
              {loadingUsers ? (
                <div className="py-12 flex justify-center">
                  <Loader2 className="w-6 h-6 text-brand-400 animate-spin" />
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700/50 text-xs text-slate-400 uppercase tracking-wider">
                      {['User', 'Role', 'Status', 'Joined', 'Actions'].map((h) => (
                        <th key={h} className="text-left px-5 py-3 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/20">
                    {users.map((u: AuthUser) => (
                      <tr key={u.id} className="hover:bg-slate-800/20 transition-colors">
                        <td className="px-5 py-3.5">
                          <p className="font-medium text-white">{u.full_name}</p>
                          <p className="text-xs text-slate-400">{u.email}</p>
                          {u.institution && <p className="text-xs text-slate-500">{u.institution}</p>}
                        </td>
                        <td className="px-5 py-3.5">
                          <select
                            value={u.role}
                            onChange={(e) => {
                              if (u.id === user?.id) return;
                              changeRole({ id: u.id, role: e.target.value });
                            }}
                            disabled={u.id === user?.id}
                            className={clsx(
                              'text-xs px-2 py-1 rounded-lg border-0 cursor-pointer focus:outline-none',
                              'focus:ring-1 focus:ring-brand-500',
                              ROLE_BADGE[u.role] ?? 'bg-slate-600/20 text-slate-300',
                              'disabled:cursor-default disabled:opacity-70',
                            )}
                          >
                            <option value="researcher">researcher</option>
                            <option value="clinician">clinician</option>
                            <option value="admin">admin</option>
                          </select>
                        </td>
                        <td className="px-5 py-3.5">
                          <button
                            onClick={() => { if (u.id !== user?.id) toggleActive({ id: u.id, is_active: !u.is_active }); }}
                            disabled={u.id === user?.id}
                            className="flex items-center gap-1.5 text-xs disabled:opacity-50 disabled:cursor-default"
                          >
                            {u.is_active
                              ? <><ToggleRight className="w-4 h-4 text-green-400" /><span className="text-green-400">Active</span></>
                              : <><ToggleLeft  className="w-4 h-4 text-slate-500" /><span className="text-slate-500">Disabled</span></>
                            }
                          </button>
                        </td>
                        <td className="px-5 py-3.5 text-slate-400 text-xs">
                          {format(new Date(u.created_at), 'dd MMM yyyy')}
                        </td>
                        <td className="px-5 py-3.5">
                          <button
                            onClick={() => {
                              if (u.id === user?.id) return;
                              if (confirm(`Delete ${u.email}? This cannot be undone.`)) deleteUser(u.id);
                            }}
                            disabled={u.id === user?.id}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10
                                       transition-colors disabled:opacity-30 disabled:cursor-default"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* Audit log tab */}
        {tab === 'audit' && (
          <div className="glass-card overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-700/50">
              <h3 className="section-title">Audit Log</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                NHS DSP Toolkit · UK GDPR Article 30 — all access events recorded
              </p>
            </div>
            {loadingAudit ? (
              <div className="py-12 flex justify-center"><Loader2 className="w-6 h-6 text-brand-400 animate-spin" /></div>
            ) : (
              <div className="max-h-[60vh] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-slate-900">
                    <tr className="border-b border-slate-700/50 text-xs text-slate-400 uppercase">
                      {['Timestamp', 'Action', 'User', 'Resource', 'IP'].map((h) => (
                        <th key={h} className="text-left px-5 py-3 font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/20">
                    {(auditLogs as any[]).map((log: any) => (
                      <tr key={log.id} className="hover:bg-slate-800/20 transition-colors">
                        <td className="px-5 py-2.5 text-xs text-slate-400 font-mono whitespace-nowrap">
                          {format(new Date(log.created_at), 'dd MMM HH:mm:ss')}
                        </td>
                        <td className={clsx('px-5 py-2.5 text-xs font-mono font-medium',
                          ACTION_COLOUR[log.action] ?? 'text-slate-300')}>
                          {log.action}
                        </td>
                        <td className="px-5 py-2.5 text-xs text-slate-300 max-w-[140px] truncate">
                          {log.user_id?.slice(0, 8) ?? '—'}
                        </td>
                        <td className="px-5 py-2.5 text-xs text-slate-400 font-mono max-w-[120px] truncate">
                          {log.resource ?? '—'}
                        </td>
                        <td className="px-5 py-2.5 text-xs text-slate-400 font-mono">
                          {log.ip_address ?? '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {auditLogs.length === 0 && (
                  <div className="py-12 text-center text-slate-400 text-sm">No audit events yet.</div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
