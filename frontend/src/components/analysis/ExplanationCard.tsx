'use client';
import { FileText } from 'lucide-react';

export function ExplanationCard({ explanation }: { explanation: string }) {
  // Render markdown-like bold and line breaks
  const lines = explanation.split('\n');
  return (
    <div className="glass-card p-5 space-y-4">
      <h3 className="section-title flex items-center gap-2">
        <FileText className="w-4 h-4 text-brand-400" />
        Natural Language Explanation
      </h3>
      <div className="prose prose-invert prose-sm max-w-none space-y-2">
        {lines.map((line, i) => {
          if (!line.trim()) return <div key={i} className="h-2" />;
          // Bold headings via **text**
          const parts = line.split(/(\*\*[^*]+\*\*)/g);
          return (
            <p key={i} className="text-sm text-slate-300 leading-relaxed">
              {parts.map((part, j) =>
                part.startsWith('**') && part.endsWith('**') ? (
                  <strong key={j} className="text-white font-semibold">
                    {part.slice(2, -2)}
                  </strong>
                ) : (
                  <span key={j}>{part}</span>
                ),
              )}
            </p>
          );
        })}
      </div>
    </div>
  );
}
