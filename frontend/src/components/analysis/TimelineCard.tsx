'use client';
import { clsx } from 'clsx';
import type { SegmentEvent } from '@/types';

function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

export function TimelineCard({ events }: { events: SegmentEvent[] }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-700/50">
        <h3 className="section-title">Behaviour Timeline</h3>
        <p className="text-xs text-slate-400 mt-0.5">{events.length} notable events detected</p>
      </div>
      <div className="max-h-72 overflow-y-auto">
        <ul className="divide-y divide-slate-700/20">
          {events.map((evt, i) => (
            <li key={i} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-800/20">
              <span className="font-mono text-xs text-slate-500 w-10 flex-shrink-0">{fmtTime(evt.time)}</span>
              <span className={clsx(
                'w-2 h-2 rounded-full flex-shrink-0',
                evt.severity === 'positive' ? 'bg-green-400' :
                evt.severity === 'warning'  ? 'bg-amber-400' : 'bg-blue-400',
              )} />
              <span className="text-sm text-slate-300 flex-1">{evt.event}</span>
              <span className={clsx(
                'text-xs px-2 py-0.5 rounded-md flex-shrink-0',
                evt.type === 'ados' ? 'bg-purple-500/20 text-purple-300' : 'bg-cyan-500/20 text-cyan-300',
              )}>
                {evt.type.toUpperCase()}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
