'use client';
import { useQuery } from '@tanstack/react-query';
import { listJobs } from '@/lib/api';
import { useHRIStore } from '@/store/hriStore';
import { format } from 'date-fns';
import { clsx } from 'clsx';
import { CheckCircle2, XCircle, Clock, Loader2, BarChart3 } from 'lucide-react';

const STATUS_ICON = {
  complete: <CheckCircle2 className="w-4 h-4 text-green-400" />,
  failed:   <XCircle     className="w-4 h-4 text-red-400"   />,
  running:  <Loader2     className="w-4 h-4 text-amber-400 animate-spin" />,
  queued:   <Clock       className="w-4 h-4 text-slate-400" />,
};

export function HistoryPanel() {
  const { setActiveJobId, setActiveTab } = useHRIStore();
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: listJobs,
    refetchInterval: 10_000,
  });

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Analysis History</h2>
        <p className="text-slate-400 mt-1">Previous analysis sessions and their status.</p>
      </div>

      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-700/50">
          <h3 className="section-title">Recent Jobs</h3>
        </div>
        {isLoading ? (
          <div className="py-12 text-center text-slate-400">Loading…</div>
        ) : jobs.length === 0 ? (
          <div className="py-12 text-center text-slate-400">No analysis jobs yet.</div>
        ) : (
          <ul className="divide-y divide-slate-700/30">
            {jobs.map((job) => (
              <li key={job.id} className="flex items-center gap-4 px-5 py-4 hover:bg-slate-800/20">
                <div className="flex-shrink-0">
                  {STATUS_ICON[job.status] ?? STATUS_ICON.queued}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {job.video_filename ?? `${job.id.slice(0, 8)}…`}
                  </p>
                  <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                    {job.video_filename && (
                      <span className="font-mono" title="Job ID">{job.id.slice(0, 8)}…</span>
                    )}
                    <span className="font-mono" title="Video ID — matches saved frame filenames">
                      video: {job.video_id.slice(0, 8)}…
                    </span>
                    <span>{job.vlm_model}</span>
                    <span>{format(new Date(job.created_at), 'dd MMM yyyy HH:mm')}</span>
                    {job.completed_at && (
                      <span>
                        Duration:{' '}
                        {Math.round(
                          (new Date(job.completed_at).getTime() - new Date(job.created_at).getTime()) / 1000,
                        )}s
                      </span>
                    )}
                  </div>
                </div>
                {job.status === 'running' && (
                  <div className="w-24">
                    <div className="progress-bar">
                      <div className="progress-bar-fill" style={{ width: `${job.progress}%` }} />
                    </div>
                    <p className="text-xs text-slate-400 mt-1 text-right">{job.progress}%</p>
                  </div>
                )}
                <span className={clsx(
                  'metric-badge flex-shrink-0',
                  job.status === 'complete' ? 'bg-green-500/15 text-green-300' :
                  job.status === 'failed'   ? 'bg-red-500/15 text-red-300' :
                  job.status === 'running'  ? 'bg-amber-500/15 text-amber-300' :
                  'bg-slate-600/30 text-slate-300',
                )}>
                  {job.status}
                </span>
                {job.status === 'complete' && (
                  <button
                    onClick={() => { setActiveJobId(job.id); setActiveTab('results'); }}
                    className="btn-secondary py-1.5 px-3 text-xs flex-shrink-0"
                  >
                    <BarChart3 className="w-3.5 h-3.5" />
                    Results
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}