'use client';
import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Play, Loader2, CheckCircle2, XCircle, Cpu, Zap, BrainCircuit, BarChart3, Info } from 'lucide-react';
import { listVideos, startAnalysis, getJob, getResult, createProgressWebSocket, getHealth } from '@/lib/api';
import { useHRIStore } from '@/store/hriStore';
import type { ProgressUpdate } from '@/types';
import { clsx } from 'clsx';

const PIPELINE_STAGES = [
  { key: 'Extracting video frames',               icon: '🎞', pct: 10 },
  { key: 'Applying Set-of-Mark visual prompting', icon: '🏷', pct: 25 },
  { key: 'Running VLM behavioural analysis',      icon: '🤖', pct: 65 },
  { key: 'Computing ADOS-grounded scores',        icon: '📋', pct: 75 },
  { key: 'Computing HRI extension metrics',       icon: '📐', pct: 82 },
  { key: 'Running AQ-10 predictive model',        icon: '📊', pct: 88 },
  { key: 'Computing SHAP feature attribution',    icon: '🔍', pct: 94 },
  { key: 'Generating explainable report',         icon: '📝', pct: 99 },
];

// ── VLM model catalogue ───────────────────────────────────────────────────────
// All models are run locally via Ollama — no data leaves the system.
// Pull command: docker exec hri_ollama ollama pull <model_id>
const VLM_MODELS = [
  // ── Tier 1: Best accuracy for HRI behavioural analysis ──────────────────
  {
    id:       'llava:13b',
    label:    'LLaVA 13B',
    tier:     1,
    badge:    'Best accuracy',
    badgeColour: 'bg-green-500/20 text-green-300',
    size:     '~8 GB',
    notes:    'Original LLaVA — strong at spatial reasoning and region-based prompting. Best overall for ADOS scoring.',
  },
  {
    id:       'llama3.2-vision:11b',
    label:    'Llama 3.2 Vision 11B',
    tier:     1,
    badge:    'Recommended',
    badgeColour: 'bg-brand-500/20 text-brand-300',
    size:     '~7 GB',
    notes:    'Meta\'s latest multimodal model. Excellent instruction following and structured JSON output. Highly recommended for this pipeline.',
  },
  {
    id:       'qwen2.5vl:7b',
    label:    'Qwen 2.5 VL 7B',
    tier:     1,
    badge:    'Top performer',
    badgeColour: 'bg-purple-500/20 text-purple-300',
    size:     '~5 GB',
    notes:    'Alibaba\'s Qwen2.5-VL ranks top on visual grounding benchmarks. Excellent at fine-grained spatial analysis — ideal for SoM prompting.',
  },
  {
    id:       'internvl2.5:8b',
    label:    'InternVL 2.5 8B',
    tier:     1,
    badge:    'High accuracy',
    badgeColour: 'bg-cyan-500/20 text-cyan-300',
    size:     '~5 GB',
    notes:    'Shanghai AI Lab model. State-of-the-art on MMBench. Strong at region description and multi-turn visual understanding.',
  },
  // ── Tier 2: Good balance of speed and quality ────────────────────────────
  {
    id:       'llava-llama3:8b',
    label:    'LLaVA-LLaMA3 8B',
    tier:     2,
    badge:    'Balanced',
    badgeColour: 'bg-amber-500/20 text-amber-300',
    size:     '~5 GB',
    notes:    'LLaVA fine-tuned on LLaMA 3. Better instruction following than original LLaVA 7B, good speed/quality balance.',
  },
  {
    id:       'minicpm-v:latest',
    label:    'MiniCPM-V 8B',
    tier:     2,
    badge:    'Fast + accurate',
    badgeColour: 'bg-amber-500/20 text-amber-300',
    size:     '~5 GB',
    notes:    'Tsinghua/ModelBest. Exceptional performance for its size, very fast on CPU. Good structured output quality.',
  },
  {
    id:       'moondream2',
    label:    'Moondream 2',
    tier:     2,
    badge:    'Lightweight',
    badgeColour: 'bg-slate-400/20 text-slate-300',
    size:     '~2 GB',
    notes:    'Tiny but capable. Fastest option for low-resource environments. Useful for rapid prototyping.',
  },
  // ── Tier 3: Experimental / large ────────────────────────────────────────
  {
    id:       'gemma4',
    label:    'Gemma 4 (Vision)',
    tier:     3,
    badge:    'Experimental',
    badgeColour: 'bg-rose-500/20 text-rose-300',
    size:     '~12 GB',
    notes:    'Google Gemma 4 multimodal. Experimental in Ollama — check ollama.com for current availability.',
  },
  {
    id:       'llava:7b',
    label:    'LLaVA 7B',
    tier:     3,
    badge:    'Lightweight',
    badgeColour: 'bg-slate-400/20 text-slate-300',
    size:     '~4 GB',
    notes:    'Fastest option. Lower accuracy on fine-grained behavioural scoring but useful when GPU/RAM is limited.',
  },
];

const TIER_LABELS: Record<number, string> = {
  1: '— Tier 1: Best for HRI Analysis —',
  2: '— Tier 2: Balanced Speed / Quality —',
  3: '— Tier 3: Lightweight / Experimental —',
};

export function AnalysisPanel() {
  const {
    videos: storeVideos,
    activeJobId, setActiveJobId,
    upsertJob, setProgress, setResult, setActiveTab,
    progress: allProgress,
  } = useHRIStore();

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn:  getHealth,
    refetchInterval: 15_000,
  });

  const { data: allVideos = [] } = useQuery({
    queryKey: ['videos'],
    queryFn:  listVideos,
  });

  const defaultVideoId = storeVideos[0]?.id || allVideos[0]?.id || '';
  const [selectedVideoId, setSelectedVideoId] = useState<string>('');
  const [selectedModel,   setSelectedModel]   = useState('llama3.2-vision:11b');
  const [showModelInfo,   setShowModelInfo]   = useState(false);
  const [wsError,         setWsError]         = useState<string | null>(null);

  useEffect(() => {
    if (!selectedVideoId && defaultVideoId) setSelectedVideoId(defaultVideoId);
  }, [defaultVideoId, selectedVideoId]);

  const selectedModelInfo = VLM_MODELS.find(m => m.id === selectedModel);

  // Poll job status as fallback
  const { data: jobData } = useQuery({
    queryKey: ['job', activeJobId],
    queryFn:  () => getJob(activeJobId!),
    enabled:  !!activeJobId,
    refetchInterval: (query) => {
      const d = query.state.data;
      return d?.status === 'running' || d?.status === 'queued' ? 2000 : false;
    },
  });

  useEffect(() => { if (jobData) upsertJob(jobData); }, [jobData, upsertJob]);

  // WebSocket for real-time progress
  useEffect(() => {
    if (!activeJobId) return;
    const ws = createProgressWebSocket(
      activeJobId,
      (data) => {
        const update = data as ProgressUpdate;
        if (!update.job_id) return;
        setProgress(activeJobId, update);
        if (update.status === 'complete') {
          getResult(activeJobId).then((r) => {
            setResult(activeJobId, r);
            setActiveTab('results');
          });
        }
      },
      () => setWsError('Live updates unavailable — polling instead'),
    );
    return () => ws.close();
  }, [activeJobId, setProgress, setResult, setActiveTab]);

  const { mutate: doStart, isPending } = useMutation({
    mutationFn: () => startAnalysis(selectedVideoId, selectedModel),
    onSuccess:  (job) => { setActiveJobId(job.id); upsertJob(job); },
  });

  const currentProgress = activeJobId ? allProgress[activeJobId] : null;
  const progressPct  = currentProgress?.progress ?? jobData?.progress ?? 0;
  const currentStage = currentProgress?.stage    ?? jobData?.stage    ?? '';
  const jobStatus    = currentProgress?.status   ?? jobData?.status   ?? 'idle';

  // Group models by tier for the optgroup dropdown
  const tier1 = VLM_MODELS.filter(m => m.tier === 1);
  const tier2 = VLM_MODELS.filter(m => m.tier === 2);
  const tier3 = VLM_MODELS.filter(m => m.tier === 3);

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Run Behavioural Analysis</h2>
        <p className="text-slate-400 mt-1 text-sm">
          7-stage VLM pipeline: frame extraction → SoM prompting → ADOS scoring → AQ-10 prediction → SHAP attribution.
        </p>
      </div>

      {/* Configuration */}
      <div className="glass-card p-6 space-y-5">
        <h3 className="section-title flex items-center gap-2">
          <Cpu className="w-4 h-4 text-brand-400" /> Pipeline Configuration
        </h3>

        <div className="grid grid-cols-1 gap-4">
          {/* Video selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Video Session</label>
            <select
              value={selectedVideoId}
              onChange={(e) => setSelectedVideoId(e.target.value)}
              disabled={jobStatus === 'running' || isPending}
              className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm
                         text-white focus:outline-none focus:border-brand-500 disabled:opacity-50"
            >
              <option value="">— Select a video —</option>
              {allVideos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.original_filename} ({(v.file_size / 1024 / 1024).toFixed(1)} MB)
                </option>
              ))}
            </select>
            {allVideos.length === 0 && (
              <p className="text-xs text-amber-400">No videos yet — upload one first.</p>
            )}
          </div>

          {/* VLM model selector */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-300">VLM Model</label>
              <button
                onClick={() => setShowModelInfo(!showModelInfo)}
                className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors"
              >
                <Info className="w-3.5 h-3.5" />
                {showModelInfo ? 'Hide' : 'About models'}
              </button>
            </div>

            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={jobStatus === 'running' || isPending}
              className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm
                         text-white focus:outline-none focus:border-brand-500 disabled:opacity-50"
            >
              <optgroup label={TIER_LABELS[1]}>
                {tier1.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} — {m.size} [{m.badge}]
                  </option>
                ))}
              </optgroup>
              <optgroup label={TIER_LABELS[2]}>
                {tier2.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} — {m.size} [{m.badge}]
                  </option>
                ))}
              </optgroup>
              <optgroup label={TIER_LABELS[3]}>
                {tier3.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} — {m.size} [{m.badge}]
                  </option>
                ))}
              </optgroup>
            </select>

            {/* Model info panel */}
            {showModelInfo && selectedModelInfo && (
              <div className="mt-2 p-3 rounded-xl bg-slate-800/60 border border-slate-700/50 space-y-2 animate-fade-in">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-white">{selectedModelInfo.label}</span>
                  <span className={clsx('metric-badge text-xs', selectedModelInfo.badgeColour)}>
                    {selectedModelInfo.badge}
                  </span>
                  <span className="text-xs text-slate-400">{selectedModelInfo.size}</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">{selectedModelInfo.notes}</p>
                <p className="text-xs text-slate-500 font-mono">
                  Pull: docker exec hri_ollama ollama pull {selectedModelInfo.id}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* VLM not ready warning */}
        {health && !health.ollama_available && (
          <div className="flex items-start gap-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
            <span className="text-amber-400 text-lg flex-shrink-0">⚠</span>
            <div className="text-xs text-amber-300 space-y-1">
              <p className="font-semibold">VLM model not ready</p>
              <p>Pull the selected model first:</p>
              <code className="block bg-slate-900 rounded px-2 py-1 font-mono text-amber-200 mt-1">
                docker exec hri_ollama ollama pull {selectedModel}
              </code>
            </div>
          </div>
        )}

        <button
          onClick={() => doStart()}
          disabled={
            !selectedVideoId ||
            jobStatus === 'running' ||
            isPending ||
            (health !== undefined && !health.ollama_available)
          }
          className="btn-primary w-full justify-center py-3"
        >
          {isPending || jobStatus === 'running'
            ? <Loader2 className="w-5 h-5 animate-spin" />
            : <Zap className="w-5 h-5" />}
          {isPending ? 'Starting…' : jobStatus === 'running' ? 'Analysing…' : 'Start Analysis Pipeline'}
        </button>
      </div>

      {/* Progress */}
      {activeJobId && (
        <div className="glass-card p-6 space-y-5 animate-slide-up">
          <div className="flex items-center justify-between">
            <h3 className="section-title flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-brand-400" /> Pipeline Progress
            </h3>
            <div className={clsx(
              'flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium',
              jobStatus === 'running'  ? 'bg-amber-500/15 text-amber-300'  :
              jobStatus === 'complete' ? 'bg-green-500/15 text-green-300'  :
              jobStatus === 'failed'   ? 'bg-red-500/15   text-red-300'    :
              'bg-slate-600/30 text-slate-300',
            )}>
              {jobStatus === 'running'  && <Loader2     className="w-3 h-3 animate-spin" />}
              {jobStatus === 'complete' && <CheckCircle2 className="w-3 h-3" />}
              {jobStatus === 'failed'   && <XCircle     className="w-3 h-3" />}
              {jobStatus}
            </div>
          </div>

          {/* Active model badge */}
          {selectedModelInfo && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Running:</span>
              <span className={clsx('metric-badge text-xs', selectedModelInfo.badgeColour)}>
                {selectedModelInfo.label}
              </span>
            </div>
          )}

          {/* Progress bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-400">
              <span>{currentStage || 'Initialising…'}</span>
              <span className="font-mono">{progressPct}%</span>
            </div>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${progressPct}%` }} />
            </div>
          </div>

          {/* Stage checklist */}
          <div className="space-y-1.5">
            {PIPELINE_STAGES.map((stage) => {
              const done   = progressPct >= stage.pct;
              const active = currentStage === stage.key;
              return (
                <div key={stage.key} className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all',
                  active ? 'bg-brand-600/20 text-white' : done ? 'text-slate-300' : 'text-slate-500',
                )}>
                  <span className="text-base w-6 text-center">{stage.icon}</span>
                  <span className="flex-1">{stage.key}</span>
                  {done && !active && <CheckCircle2 className="w-4 h-4 text-green-400" />}
                  {active && <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />}
                </div>
              );
            })}
          </div>

          {jobStatus === 'complete' && (
            <button onClick={() => setActiveTab('results')} className="btn-primary w-full justify-center py-3">
              <BarChart3 className="w-5 h-5" /> View Results & Behavioural Profile
            </button>
          )}

          {jobStatus === 'failed' && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-sm text-red-300">
              <strong>Pipeline error:</strong> {jobData?.error_message || 'Unknown error. Check logs.'}
            </div>
          )}

          {wsError && <p className="text-xs text-amber-300">⚠ {wsError}</p>}
        </div>
      )}

      {/* Model comparison table */}
      <div className="glass-card p-5 space-y-4">
        <h3 className="section-title text-sm">Available VLM Models</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700/50 text-slate-400 uppercase tracking-wider">
                <th className="text-left pb-2 pr-3">Model</th>
                <th className="text-left pb-2 pr-3">Size</th>
                <th className="text-left pb-2 pr-3">Tier</th>
                <th className="text-left pb-2">Best for</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/20">
              {VLM_MODELS.map((m) => (
                <tr
                  key={m.id}
                  className={clsx(
                    'transition-colors cursor-pointer',
                    selectedModel === m.id
                      ? 'bg-brand-600/10'
                      : 'hover:bg-slate-800/40',
                  )}
                  onClick={() => setSelectedModel(m.id)}
                >
                  <td className="py-2 pr-3">
                    <span className={clsx(
                      'font-medium',
                      selectedModel === m.id ? 'text-brand-300' : 'text-white',
                    )}>
                      {m.label}
                    </span>
                    {selectedModel === m.id && (
                      <span className="ml-1.5 text-brand-400">← selected</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-slate-400 font-mono">{m.size}</td>
                  <td className="py-2 pr-3">
                    <span className={clsx('metric-badge', m.badgeColour)}>{m.badge}</span>
                  </td>
                  <td className="py-2 text-slate-400 leading-relaxed max-w-xs">{m.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500">
          Click any row to select a model. All models run locally via Ollama — no data leaves the system.
          Pull a model with: <code className="font-mono bg-slate-800 px-1.5 py-0.5 rounded">docker exec hri_ollama ollama pull &lt;model_id&gt;</code>
        </p>
      </div>
    </div>
  );
}