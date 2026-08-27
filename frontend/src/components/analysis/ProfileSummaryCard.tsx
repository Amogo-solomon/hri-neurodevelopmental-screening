'use client';
import { clsx } from 'clsx';
import type { ProfileSummary } from '@/types';

// Replaces AQ10PredictionCard. No published, validated formula exists for
// predicting AQ-10 from visual-only behavioural indicators (confirmed with
// supervisor) — this shows the single most notable ADOS/HRI profile
// indicator instead, using the same visual weight as the old headline card.

const TIER_CONFIG = {
  'typical':          { label: 'Typical',          bg: 'bg-green-500/10',   border: 'border-green-500/30',   text: 'text-green-300',   bar: 'bg-green-500' },
  'mildly atypical':  { label: 'Mildly Atypical',   bg: 'bg-amber-500/10',   border: 'border-amber-500/30',   text: 'text-amber-300',   bar: 'bg-amber-500' },
  'notably atypical': { label: 'Notably Atypical',  bg: 'bg-red-500/10',     border: 'border-red-500/30',     text: 'text-red-300',     bar: 'bg-red-500'   },
};

export function ProfileSummaryCard({ summary }: { summary: ProfileSummary }) {
  const top = summary.feature_importance?.[0] ?? null;
  const cfg = top ? TIER_CONFIG[top.tier] : TIER_CONFIG['typical'];
  const deviation = top?.deviation ?? 0;
  const pct = deviation * 100;

  return (
    <div className={clsx('glass-card p-6 space-y-4', cfg.bg, 'border', cfg.border)}>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="section-title">Behavioural Profile Summary</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Most notable indicator, based on deviation from typical/neutral
          </p>
        </div>
        <span className={clsx('metric-badge px-3 py-1.5 text-sm font-semibold', cfg.bg, cfg.border, cfg.text, 'border')}>
          {cfg.label}
        </span>
      </div>

      {top ? (
        <>
          <div className="flex items-end gap-4">
            <span className={clsx('text-3xl font-bold tracking-tight', cfg.text)}>
              {top.label}
            </span>
          </div>

          <div className="space-y-2">
            <div className="h-3 rounded-full bg-slate-800 relative overflow-hidden">
              <div className={clsx('h-full rounded-full transition-all duration-700', cfg.bar)}
                   style={{ width: `${pct}%` }} />
              <div className="absolute top-0 bottom-0 w-0.5 bg-slate-600" style={{ left: '20%' }} />
              <div className="absolute top-0 bottom-0 w-0.5 bg-slate-600" style={{ left: '50%' }} />
            </div>
            <div className="flex text-xs text-slate-500 justify-between">
              <span>0 — Typical</span>
              <span>0.2 — Mild</span>
              <span>0.5 — Notable</span>
              <span>1.0</span>
            </div>
          </div>

          <p className="text-xs text-slate-400">
            Deviation from typical/neutral: {deviation.toFixed(2)} (raw value: {String(top.raw_value)}).
            See the Profile Deviation chart below for all indicators. This is a description of the
            behavioural profile — it is not a diagnostic prediction or risk score.
          </p>
        </>
      ) : (
        <p className="text-sm text-slate-400">No profile data available for this session.</p>
      )}
    </div>
  );
}