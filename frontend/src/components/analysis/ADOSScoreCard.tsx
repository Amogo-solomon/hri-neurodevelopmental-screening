'use client';
import { clsx } from 'clsx';
import type { ADOSCoreScores } from '@/types';

const ADOS_ITEMS = [
  {
    field: 'eye_contact_score' as const,
    label: 'Eye Contact',
    item: 'Item 1',
    desc: 'Flexible, socially modulated gaze',
    codes: { 0: 'Typical', 2: 'Atypical' },
    valClass: (v: number | null) => v === 0 ? 'text-green-400' : v === 2 ? 'text-red-400' : 'text-slate-400',
  },
  {
    field: 'directed_expression_score' as const,
    label: 'Directed Expressions',
    item: 'Item 2',
    desc: 'Facial affect aimed at robot',
    codes: { 0: 'Range directed', 1: 'Some direction', 2: 'Limited/absent' },
    valClass: (v: number | null) => v === 0 ? 'text-green-400' : v === 1 ? 'text-amber-400' : v === 2 ? 'text-red-400' : 'text-slate-400',
  },
  {
    field: 'descriptive_gesture_score' as const,
    label: 'Descriptive Gestures',
    item: 'Item 4',
    desc: 'Story-acting spontaneous gestures',
    codes: { 0: 'Several spontaneous', 1: 'Some/limited', 2: 'Very limited', 3: 'Absent', 8: 'N/A' },
    valClass: (v: number | null) => v === 0 ? 'text-green-400' : v === 1 ? 'text-amber-400' : (v === 2 || v === 3) ? 'text-red-400' : 'text-slate-400',
  },
  {
    field: 'hand_mannerism_score' as const,
    label: 'Hand & Finger Mannerisms',
    item: 'Item 6',
    desc: 'Repetitive non-communicative movement',
    codes: { 0: 'None/typical', 1: 'Occasionally', 2: 'Frequently' },
    valClass: (v: number | null) => v === 0 ? 'text-green-400' : v === 1 ? 'text-amber-400' : v === 2 ? 'text-red-400' : 'text-slate-400',
  },
];

export function ADOSScoreCard({ scores }: { scores: ADOSCoreScores }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-700/50">
        <h3 className="section-title">ADOS-Grounded Core Items</h3>
        <p className="text-xs text-slate-400 mt-0.5">4 clinically-validated visual behavioural indicators</p>
      </div>
      <ul className="divide-y divide-slate-700/30">
        {ADOS_ITEMS.map(({ field, label, item, desc, codes, valClass }) => {
          const value = scores[field];
          const codeLabel = value != null ? codes[value as keyof typeof codes] ?? `Code ${value}` : '—';
          return (
            <li key={field} className="flex items-center gap-3 px-5 py-3.5 hover:bg-slate-800/20">
              <div className="w-14 flex-shrink-0 text-center">
                <div className={clsx('text-2xl font-bold font-mono', valClass(value))}>
                  {value ?? '—'}
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-white">{label}</p>
                  <span className="text-xs text-slate-500">{item}</span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">{desc}</p>
              </div>
              <span className={clsx('text-xs font-medium flex-shrink-0 px-2 py-0.5 rounded-md bg-slate-800', valClass(value))}>
                {codeLabel}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}