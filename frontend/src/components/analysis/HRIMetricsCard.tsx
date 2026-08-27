'use client';
import { clsx } from 'clsx';
import type { HRIExtensionScores } from '@/types';

const HRI_METRICS = [
  {
    field: 'joint_attention_mean' as const,
    label: 'Joint Attention',
    desc: 'Child→object→robot gaze shift within 2s window',
    source: 'HRI Extension',
    icon: '👁',
    lowLabel: 'Low engagement',
    highLabel: 'Active joint attention',
  },
  {
    field: 'postural_orientation_mean' as const,
    label: 'Postural Orientation',
    desc: 'Shoulder angle to robot, forward lean, head nod rhythm',
    source: 'HRI Extension',
    icon: '🧍',
    lowLabel: 'Disengaged',
    highLabel: 'Fully oriented',
  },
];

function getColour(val: number | null) {
  if (val === null) return { bar: 'bg-slate-600', text: 'text-slate-400' };
  if (val >= 0.7) return { bar: 'bg-green-500', text: 'text-green-400' };
  if (val >= 0.4) return { bar: 'bg-amber-500', text: 'text-amber-400' };
  return { bar: 'bg-red-500', text: 'text-red-400' };
}

export function HRIMetricsCard({ metrics }: { metrics: HRIExtensionScores }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-700/50">
        <h3 className="section-title">HRI Extension Metrics</h3>
        <p className="text-xs text-slate-400 mt-0.5">2 child-robot interaction specific measures (visual-only)</p>
      </div>
      <div className="divide-y divide-slate-700/30">
        {HRI_METRICS.map(({ field, label, desc, source, icon, lowLabel, highLabel }) => {
          const value = metrics[field];
          const pct = value != null ? Math.round(value * 100) : null;
          const { bar, text } = getColour(value);
          return (
            <div key={field} className="px-5 py-4 space-y-2.5 hover:bg-slate-800/20">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{icon}</span>
                  <div>
                    <p className="text-sm font-medium text-white">{label}</p>
                    <p className="text-xs text-slate-400">{desc}</p>
                  </div>
                </div>
                <div className="flex-shrink-0 text-right">
                  <span className={clsx('text-xl font-bold font-mono', value != null ? text : 'text-slate-500')}>
                    {value != null ? value.toFixed(2) : 'N/A'}
                  </span>
                  <p className="text-xs text-slate-500">{source}</p>
                </div>
              </div>
              {value != null ? (
                <div className="space-y-1">
                  <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div className={clsx('h-full rounded-full transition-all duration-700', bar)}
                         style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>{lowLabel}</span>
                    <span>{highLabel}</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">
                  Insufficient valid frames for this metric — re-run with a clearer video segment.
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}