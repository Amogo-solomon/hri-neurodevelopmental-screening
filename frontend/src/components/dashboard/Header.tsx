'use client';
import { Brain, Activity, Shield, User, LogOut, Settings, ChevronDown } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState, useRef, useEffect } from 'react';
import { getHealth } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import { useHRIStore } from '@/store/hriStore';
import { apiLogout } from '@/lib/authApi';
import { clsx } from 'clsx';
import { ThemeToggle } from '@/components/layout/ThemeToggle';

const ROLE_COLOUR: Record<string, string> = {
  admin:      'text-purple-400',
  clinician:  'text-blue-400',
  researcher: 'text-cyan-400',
};

export function Header() {
  const router                           = useRouter();
  const { user, logout: storeLogout }    = useAuthStore();
  const { activeJobId, jobs }            = useHRIStore();
  const [menuOpen, setMenuOpen]          = useState(false);
  const menuRef                          = useRef<HTMLDivElement>(null);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn:  getHealth,
    refetchInterval: 30_000,
  });

  // The health check always reports the container's *default* configured
  // model — it has no concept of a per-job selection. Previously the header
  // badge showed that default even while a job was actively running a
  // different, explicitly-selected model (e.g. "VLM Ready (qwen2.5vl:7b)"
  // while the Pipeline Progress panel correctly showed "Running: LLaVA 13B"
  // for the same job) — technically not wrong, but confusing, since the two
  // badges appeared to disagree about what was actually running. Prefer the
  // active job's real model when one is in progress; fall back to the
  // health check's default otherwise.
  const activeJob = jobs.find((j) => j.id === activeJobId);
  const isJobRunning = activeJob && (activeJob.status === 'running' || activeJob.status === 'queued');
  const displayedModel = isJobRunning ? activeJob!.vlm_model : health?.ollama_model;

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = async () => {
    await apiLogout();
    storeLogout();
    router.replace('/login');
  };

  return (
    <header className="flex items-center justify-between px-6 py-4 bg-slate-900/80 backdrop-blur
                       border-b border-slate-700/50 z-10 flex-shrink-0">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center flex-shrink-0">
          <Brain className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-base font-bold text-white leading-tight tracking-tight">
            HRI Behaviour Analysis
          </h1>
          <p className="text-xs text-slate-400">
            University of Lincoln · MSc Cloud Computing
          </p>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        {/* Theme toggle */}
        <ThemeToggle />

        {/* Compliance badge */}
        <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                        bg-slate-800/80 border border-slate-600/50">
          <Shield className="w-3.5 h-3.5 text-green-400" />
          <span className="text-xs text-slate-300 font-medium">
            UK GDPR · NHS DSP · Local Inference
          </span>
        </div>

        {/* VLM status */}
        {health && (
          <div className="hidden sm:flex items-center gap-2">
            <div className={clsx(
              'w-2 h-2 rounded-full flex-shrink-0',
              health.ollama_available ? 'bg-green-400 animate-pulse' : 'bg-amber-400 animate-pulse',
            )} />
            {health.ollama_available ? (
              <span className="text-xs text-slate-400">
                {isJobRunning ? `Running (${displayedModel})` : `VLM Ready (${displayedModel})`}
              </span>
            ) : (
              <span className="text-xs text-amber-400 font-medium" title="Run: docker exec hri_ollama ollama pull llava:13b">
                VLM not ready — pull model ↗
              </span>
            )}
          </div>
        )}

        {/* User menu */}
        {user && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2.5 px-3 py-2 rounded-xl
                         bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50
                         transition-colors"
            >
              <div className="w-7 h-7 rounded-full bg-brand-600/40 flex items-center justify-center flex-shrink-0">
                <User className="w-3.5 h-3.5 text-brand-300" />
              </div>
              <div className="hidden sm:block text-left">
                <p className="text-xs font-medium text-white leading-tight max-w-[120px] truncate">
                  {user.full_name}
                </p>
                <p className={clsx('text-xs leading-tight capitalize', ROLE_COLOUR[user.role] ?? 'text-slate-400')}>
                  {user.role}
                </p>
              </div>
              <ChevronDown className={clsx(
                'w-3.5 h-3.5 text-slate-400 transition-transform duration-150 flex-shrink-0',
                menuOpen && 'rotate-180',
              )} />
            </button>

            {/* Dropdown */}
            {menuOpen && (
              <div className="absolute right-0 mt-2 w-52 rounded-xl bg-slate-800 border border-slate-700/60
                              shadow-xl shadow-black/40 overflow-hidden z-50 animate-fade-in">
                {/* User info header */}
                <div className="px-4 py-3 border-b border-slate-700/50">
                  <p className="text-sm font-medium text-white truncate">{user.full_name}</p>
                  <p className="text-xs text-slate-400 truncate">{user.email}</p>
                </div>

                {/* Menu items */}
                <div className="py-1">
                  <button
                    onClick={() => { setMenuOpen(false); router.push('/profile'); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300
                               hover:bg-slate-700/60 hover:text-white transition-colors"
                  >
                    <Settings className="w-4 h-4" /> Account settings
                  </button>

                  {user.role === 'admin' && (
                    <button
                      onClick={() => { setMenuOpen(false); router.push('/admin'); }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300
                                 hover:bg-slate-700/60 hover:text-white transition-colors"
                    >
                      <Shield className="w-4 h-4 text-purple-400" /> Admin panel
                    </button>
                  )}
                </div>

                <div className="border-t border-slate-700/50 py-1">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-400
                               hover:bg-red-500/10 transition-colors"
                  >
                    <LogOut className="w-4 h-4" /> Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}