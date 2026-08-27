'use client';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getResult, getFrameSummaries, exportResults } from '@/lib/api';
import { useHRIStore } from '@/store/hriStore';
import { ADOSScoreCard }          from './ADOSScoreCard';
import { HRIMetricsCard }         from './HRIMetricsCard';
import { ProfileSummaryCard }     from './ProfileSummaryCard';
import { ProfileDeviationChart }  from './ProfileDeviationChart';
import { TimelineCard }           from './TimelineCard';
import { ExplanationCard }        from './ExplanationCard';
import { ClinicalDisclaimerBanner } from './ClinicalDisclaimerBanner';
import {
  Loader2, BarChart3, Download, FileJson, FileSpreadsheet,
  ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Code2, Printer, Camera,
} from 'lucide-react';
import { clsx } from 'clsx';
import { format } from 'date-fns';
import type { FrameSummary } from '@/types';

// ── Export button ─────────────────────────────────────────────────────────────
function ExportButtons({ jobId }: { jobId: string }) {
  const [downloading, setDownloading] = useState<'json' | 'xlsx' | null>(null);
  const [error, setError]             = useState<string | null>(null);

  const handleExport = async (fmt: 'json' | 'xlsx') => {
    setDownloading(fmt);
    setError(null);
    try {
      await exportResults(jobId, fmt);
    } catch (e: any) {
      setError(e?.message || 'Export failed');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <button
          onClick={() => handleExport('json')}
          disabled={!!downloading}
          className="btn-secondary py-1.5 px-3 text-xs"
          title="Download full results as JSON (includes raw VLM responses)"
        >
          {downloading === 'json'
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <FileJson className="w-3.5 h-3.5" />}
          JSON
        </button>
        <button
          onClick={() => handleExport('xlsx')}
          disabled={!!downloading}
          className="btn-secondary py-1.5 px-3 text-xs"
          title="Download results as Excel (6 sheets: summary, frames, ADOS, HRI, profile summary, explanation)"
        >
          {downloading === 'xlsx'
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <FileSpreadsheet className="w-3.5 h-3.5" />}
          Excel
        </button>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

// ── Print button ──────────────────────────────────────────────────────────────
function PrintButton() {
  return (
    <button
      onClick={() => window.print()}
      className="btn-secondary py-1.5 px-3 text-xs no-print"
      title="Print this report, or save it as a PDF"
    >
      <Printer className="w-3.5 h-3.5" />
      Print
    </button>
  );
}

// ── Screenshot button ─────────────────────────────────────────────────────────
// Captures #report-printable-area exactly as rendered on screen — original
// dark theme, gradients, tier colours, everything — and downloads it as a
// PNG. Useful for pasting straight into a thesis/report as an image, as
// opposed to Print (which reflows into a printable/PDF page layout).
function ScreenshotButton({ jobId }: { jobId: string }) {
  const [capturing, setCapturing] = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const handleScreenshot = async () => {
    setCapturing(true);
    setError(null);
    try {
      const { default: html2canvas } = await import('html2canvas');
      const el = document.getElementById('report-printable-area');
      if (!el) throw new Error('Report area not found');

      const canvas = await html2canvas(el, {
        backgroundColor: '#0b1120', // app's dark background — keeps original colours, no white gaps
        useCORS: true,
        scale: 2,                  // sharper output for thesis/print use
        windowWidth: el.scrollWidth,
        windowHeight: el.scrollHeight,
        onclone: (clonedDoc) => {
          // html2canvas doesn't support backdrop-filter, so the semi-transparent
          // glass-card background (bg-slate-900/60 + backdrop-blur) renders as a
          // flat, washed-out gray instead of the intended frosted look. Make
          // cards fully opaque in the cloned document used for capture only —
          // the live page/UI is never touched.
          const cards = clonedDoc.querySelectorAll('#report-printable-area .glass-card');
          cards.forEach((card) => {
            (card as HTMLElement).style.backgroundColor = '#0f172a'; // solid slate-900
            (card as HTMLElement).style.backdropFilter = 'none';
          });
        },
      });

      const link = document.createElement('a');
      link.download = `hri-report-${jobId.slice(0, 8)}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch (e: any) {
      setError(e?.message || 'Screenshot failed');
    } finally {
      setCapturing(false);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1 no-print">
      <button
        onClick={handleScreenshot}
        disabled={capturing}
        className="btn-secondary py-1.5 px-3 text-xs"
        title="Capture the full report as an image (original colours), for use as evidence in your report"
      >
        {capturing
          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
          : <Camera  className="w-3.5 h-3.5" />}
        Screenshot
      </button>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

// ── Frame summaries panel ─────────────────────────────────────────────────────
function FrameSummariesPanel({ jobId }: { jobId: string }) {
  const [open, setOpen]         = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['frame-summaries', jobId],
    queryFn:  () => getFrameSummaries(jobId),
    enabled:  open,                    // only fetch when the user expands
    staleTime: Infinity,               // frame summaries don't change
  });

  const frames = data?.frame_summaries ?? [];
  const errorCount = frames.filter(f => f.parse_error).length;

  return (
    <div className="glass-card overflow-hidden">
      {/* Header / toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4
                   hover:bg-slate-800/30 transition-colors text-left"
      >
        <div>
          <h3 className="section-title flex items-center gap-2">
            <Code2 className="w-4 h-4 text-brand-400" />
            Frame-by-Frame VLM Summaries
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Raw VLM output per frame — useful for diagnosing model behaviour
          </p>
        </div>
        {open
          ? <ChevronUp   className="w-5 h-5 text-slate-400" />
          : <ChevronDown className="w-5 h-5 text-slate-400" />}
      </button>

      {open && (
        <div className="border-t border-slate-700/50">
          {isLoading && (
            <div className="py-10 flex justify-center">
              <Loader2 className="w-6 h-6 text-brand-400 animate-spin" />
            </div>
          )}

          {error && (
            <div className="px-5 py-4 text-sm text-red-300">
              Failed to load frame summaries.
            </div>
          )}

          {data && (
            <>
              {/* Stats bar */}
              <div className="flex items-center gap-6 px-5 py-3 bg-slate-800/30 text-xs text-slate-400">
                <span>{frames.length} frames</span>
                <span>Model: <span className="text-slate-300">{data.vlm_model}</span></span>
                {errorCount > 0 && (
                  <span className="flex items-center gap-1 text-amber-400">
                    <AlertCircle className="w-3 h-3" />
                    {errorCount} parse errors
                  </span>
                )}
              </div>

              {/* Frame list */}
              <ul className="divide-y divide-slate-700/20 max-h-[520px] overflow-y-auto">
                {frames.map((f: FrameSummary) => (
                  <li key={f.frame_index} className="hover:bg-slate-800/20 transition-colors">
                    <button
                      className="w-full flex items-center gap-3 px-5 py-3 text-left"
                      onClick={() =>
                        setExpanded(expanded === f.frame_index ? null : f.frame_index)
                      }
                    >
                      {/* Frame number + status */}
                      <div className="w-8 h-8 rounded-lg bg-slate-700/60 flex items-center
                                      justify-center flex-shrink-0 text-xs font-mono text-slate-300">
                        {f.frame_index}
                      </div>

                      {/* Timestamp */}
                      <span className="text-xs font-mono text-slate-500 w-16 flex-shrink-0">
                        {f.timestamp.toFixed(1)}s
                      </span>

                      {/* Summary */}
                      <span className="flex-1 text-sm text-slate-300 truncate">
                        {f.summary}
                      </span>

                      {/* Tokens */}
                      <span className="text-xs text-slate-500 flex-shrink-0 w-16 text-right">
                        {f.tokens > 0 ? `${f.tokens} tok` : '—'}
                      </span>

                      {/* Status icon */}
                      <span className="flex-shrink-0 ml-1">
                        {f.parse_error
                          ? <AlertCircle  className="w-4 h-4 text-amber-400" />
                          : <CheckCircle2 className="w-4 h-4 text-green-400/60" />}
                      </span>
                    </button>

                    {/* Expanded raw response */}
                    {expanded === f.frame_index && f.raw_response && (
                      <div className="px-5 pb-4">
                        <pre className="text-xs text-slate-300 bg-slate-900/70 rounded-xl
                                        p-3 overflow-x-auto whitespace-pre-wrap break-words
                                        border border-slate-700/30 max-h-64 overflow-y-auto">
                          {f.raw_response}
                        </pre>
                      </div>
                    )}

                    {expanded === f.frame_index && !f.raw_response && (
                      <p className="px-5 pb-3 text-xs text-slate-500 italic">
                        No raw response captured for this frame.
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main ResultsPanel ─────────────────────────────────────────────────────────
export function ResultsPanel() {
  const { activeJobId, results, setResult } = useHRIStore();

  const { data: result, isLoading, error } = useQuery({
    queryKey: ['result', activeJobId],
    queryFn:  () => getResult(activeJobId!),
    enabled:  !!activeJobId && !results[activeJobId!],
  });

  useEffect(() => {
    if (result && activeJobId) setResult(activeJobId, result);
  }, [result, activeJobId, setResult]);

  const displayResult = activeJobId ? results[activeJobId] ?? result : null;

  if (!activeJobId) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-400">
        <BarChart3 className="w-12 h-12 text-slate-600" />
        <p>No analysis selected. Run an analysis first.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full gap-3 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
        <span>Loading results…</span>
      </div>
    );
  }

  if (error || !displayResult) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        Results not yet available — complete an analysis first.
      </div>
    );
  }

  return (
    <div id="report-printable-area" className="max-w-5xl mx-auto space-y-6 animate-fade-in pb-12">

      {/* Title row + export/print buttons */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-white">Behavioural Analysis Report</h2>
          {displayResult.video_filename && (
            <p className="text-brand-400 font-medium mt-1">{displayResult.video_filename}</p>
          )}
          <p className="text-slate-400 mt-1">
            {displayResult.frames_analysed} frames analysed · Job {activeJobId?.slice(0, 8)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 no-print">
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
            <Download className="w-3.5 h-3.5" />
            Export results
          </div>
          <div className="flex items-center gap-2">
            <ExportButtons jobId={activeJobId} />
            <PrintButton />
            <ScreenshotButton jobId={activeJobId} />
          </div>
        </div>
      </div>

      {/* Clinical disclaimer */}
      <ClinicalDisclaimerBanner text={displayResult.clinical_disclaimer} />

      {/* Profile summary hero */}
      <ProfileSummaryCard summary={displayResult.profile_summary} />

      {/* ADOS + HRI side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ADOSScoreCard scores={displayResult.ados_scores} />
        <HRIMetricsCard metrics={displayResult.hri_extensions} />
      </div>

      {/* Profile deviation chart */}
      {displayResult.profile_summary?.feature_importance && (
        <ProfileDeviationChart features={displayResult.profile_summary.feature_importance} />
      )}

      {/* NL explanation */}
      {displayResult.natural_language_explanation && (
        <ExplanationCard explanation={displayResult.natural_language_explanation} />
      )}

      {/* Behaviour timeline */}
      {displayResult.segment_timeline && displayResult.segment_timeline.length > 0 && (
        <TimelineCard events={displayResult.segment_timeline} />
      )}

      {/* Frame summaries — collapsible, loads on demand, excluded from print (raw diagnostic data) */}
      <div className="no-print">
        <FrameSummariesPanel jobId={activeJobId} />
      </div>

    </div>
  );
}