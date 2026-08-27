'use client';
import { AlertTriangle } from 'lucide-react';

export function ClinicalDisclaimerBanner({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-amber-500/10 border border-amber-500/40">
      <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-semibold text-amber-300">Clinical Disclaimer — NICE ESF Tier D</p>
        <p className="text-xs text-amber-300/80 mt-1 leading-relaxed">{text}</p>
      </div>
    </div>
  );
}
