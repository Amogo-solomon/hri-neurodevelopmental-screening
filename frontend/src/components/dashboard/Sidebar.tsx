'use client';
import { Upload, Play, BarChart3, History, ChevronRight } from 'lucide-react';
import { useHRIStore } from '@/store/hriStore';
import { clsx } from 'clsx';

const NAV = [
  { id: 'upload'   as const, icon: Upload,   label: 'Upload Video',   desc: 'Add new session' },
  { id: 'analysis' as const, icon: Play,     label: 'Run Analysis',   desc: 'Start pipeline' },
  { id: 'results'  as const, icon: BarChart3, label: 'View Results',  desc: 'Behavioural profile' },
  { id: 'history'  as const, icon: History,  label: 'History',        desc: 'Past sessions' },
];

export function Sidebar() {
  const { activeTab, setActiveTab, activeJobId, jobs } = useHRIStore();

  const activeJob = jobs.find((j) => j.id === activeJobId);

  return (
    <aside className="w-56 flex-shrink-0 bg-slate-900/50 border-r border-slate-700/50 flex flex-col py-4 gap-1 overflow-y-auto">
      {NAV.map(({ id, icon: Icon, label, desc }) => {
        const isActive = activeTab === id;
        const hasJob = id === 'analysis' && activeJob;
        return (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={clsx(
              'group mx-3 flex items-center gap-3 px-3 py-3 rounded-xl text-left transition-all duration-150',
              isActive
                ? 'bg-brand-600/20 border border-brand-600/40 text-brand-300'
                : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent',
            )}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium leading-tight">{label}</div>
              <div className="text-xs opacity-60 mt-0.5">{desc}</div>
            </div>
            {hasJob && (
              <div className={clsx(
                'w-1.5 h-1.5 rounded-full flex-shrink-0',
                activeJob.status === 'running' ? 'bg-amber-400 animate-pulse' :
                activeJob.status === 'complete' ? 'bg-green-400' :
                activeJob.status === 'failed'   ? 'bg-red-400' : 'bg-slate-500',
              )} />
            )}
            {isActive && <ChevronRight className="w-3 h-3 opacity-40" />}
          </button>
        );
      })}

      {/* Bottom: clinical disclaimer notice */}
      <div className="mt-auto mx-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
        <p className="text-xs text-amber-300/80 leading-relaxed">
          ⚠ Research use only. Not a medical device. NICE ESF Tier D.
        </p>
      </div>
    </aside>
  );
}
