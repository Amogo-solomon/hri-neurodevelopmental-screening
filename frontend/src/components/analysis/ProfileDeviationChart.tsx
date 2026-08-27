'use client';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts';
import type { ProfileFeature } from '@/types';

// Replaces SHAPChart. No published, validated formula exists for predicting
// AQ-10 from visual-only behavioural indicators (confirmed with supervisor),
// so there is no downstream prediction to attribute. This instead shows,
// for each of the 6 retained indicators, how far it deviates from
// typical/neutral (0 = typical, 1 = maximally atypical) — explaining the
// ADOS/HRI profile directly, per BehaviouralScoringEngine.compute_profile_summary().

const TICK = { fill: '#94a3b8', fontSize: 11 };

const TIER_COLOR: Record<ProfileFeature['tier'], string> = {
  'typical': '#22c55e',
  'mildly atypical': '#f59e0b',
  'notably atypical': '#ef4444',
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as ProfileFeature & { shortLabel: string };
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-xl p-3 text-xs space-y-1 max-w-xs shadow-xl">
      <p className="font-semibold text-white">{d.label}</p>
      <p className="text-slate-300">
        Deviation from typical: <span style={{ color: TIER_COLOR[d.tier] }}>{d.deviation.toFixed(2)}</span>
      </p>
      <p className="text-slate-400">
        Raw value: {typeof d.raw_value === 'number' ? d.raw_value.toFixed(2) : String(d.raw_value)}
      </p>
      <p style={{ color: TIER_COLOR[d.tier] }}>
        {d.tier.charAt(0).toUpperCase() + d.tier.slice(1)}
      </p>
    </div>
  );
};

export function ProfileDeviationChart({ features }: { features: ProfileFeature[] }) {
  const data = features.map((f) => ({
    ...f,
    shortLabel: f.label
      .replace(/ \(ADOS Item \d\)/, '')
      .replace(' (HRI Extension)', ''),
  }));

  return (
    <div className="glass-card p-5 space-y-4">
      <div>
        <h3 className="section-title">Profile Deviation Ranking</h3>
        <p className="text-xs text-slate-400 mt-0.5">
          Which behavioural indicators deviate most from typical/neutral, across the ADOS-grounded
          and HRI-extension profile. This describes the observed profile — it is not a predictive
          or diagnostic score.
        </p>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 40, bottom: 4, left: 180 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 1]}
              tick={TICK}
              axisLine={{ stroke: '#475569' }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="shortLabel"
              width={175}
              tick={TICK}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(99,102,241,0.08)' }} />
            <ReferenceLine x={0} stroke="#64748b" strokeWidth={1.5} />
            <Bar dataKey="deviation" radius={[0, 4, 4, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={TIER_COLOR[entry.tier]} opacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center gap-6 text-xs text-slate-400 justify-center">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm bg-green-500" />
          Typical
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm bg-amber-500" />
          Mildly atypical
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm bg-red-500" />
          Notably atypical
        </div>
      </div>
    </div>
  );
}