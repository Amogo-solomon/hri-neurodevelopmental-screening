'use client';
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, Film, CheckCircle2, AlertCircle, X, FileVideo, Trash2, Play } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadVideo, listVideos, deleteVideo } from '@/lib/api';
import { useHRIStore } from '@/store/hriStore';
import { clsx } from 'clsx';
import { format } from 'date-fns';
import type { VideoUpload } from '@/types';

function formatBytes(b: number) {
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}
function formatDuration(s: number | null) {
  if (!s) return '—';
  return `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, '0')}`;
}

export function UploadPanel() {
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError]       = useState<string | null>(null);
  const { addVideo, setVideos, setActiveJobId, setActiveTab } = useHRIStore();
  const qc = useQueryClient();

  const { data: videos = [], isLoading } = useQuery({
    queryKey: ['videos'],
    queryFn: listVideos,
  });

  const { mutate: doDelete } = useMutation({
    mutationFn: deleteVideo,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['videos'] }),
  });

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0];
    if (!file) return;
    setUploadError(null);
    setUploadProgress(0);

    if (file.size > 8 * 1024 * 1024 * 1024) {
      setUploadError('File exceeds the 8 GB maximum size.');
      setUploadProgress(null);
      return;
    }
    try {
      const video = await uploadVideo(file, (p) => setUploadProgress(p));
      addVideo(video);
      qc.invalidateQueries({ queryKey: ['videos'] });
      setUploadProgress(null);
    } catch (err: any) {
      setUploadError(err?.response?.data?.detail || err.message || 'Upload failed.');
      setUploadProgress(null);
    }
  }, [addVideo, qc]);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: { 'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm'] },
    maxFiles: 1,
    disabled: uploadProgress !== null,
  });

  const handleAnalyse = (video: VideoUpload) => {
    setVideos([video, ...videos.filter((v) => v.id !== video.id)]);
    setActiveJobId(null);
    setActiveTab('analysis');
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold text-white">Upload Video Session</h2>
        <p className="text-slate-400 mt-1 text-sm">
          Upload child-robot interaction recordings for explainable behavioural analysis.
          Supports MP4, AVI, MOV, MKV, WebM — up to 8 GB.
        </p>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={clsx(
          'relative flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed',
          'px-8 py-14 text-center transition-all duration-200 cursor-pointer select-none',
          isDragActive && !isDragReject ? 'border-brand-500 bg-brand-500/10' :
          isDragReject                  ? 'border-red-500   bg-red-500/10'   :
          uploadProgress !== null       ? 'border-slate-600 bg-slate-800/40 cursor-not-allowed' :
          'border-slate-600 bg-slate-800/30 hover:border-brand-500/70 hover:bg-brand-500/5',
        )}
      >
        <input {...getInputProps()} />

        {uploadProgress !== null ? (
          <div className="w-full max-w-xs space-y-3">
            <div className="flex items-center justify-center w-14 h-14 mx-auto rounded-full bg-brand-600/20">
              <Upload className="w-7 h-7 text-brand-400 animate-pulse" />
            </div>
            <p className="text-white font-semibold">Uploading…</p>
            <div className="progress-bar w-full">
              <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
            <p className="text-sm text-slate-400">{uploadProgress}% complete</p>
          </div>
        ) : (
          <>
            <div className={clsx(
              'flex items-center justify-center w-16 h-16 rounded-2xl',
              isDragActive ? 'bg-brand-500/30' : 'bg-slate-700/60',
            )}>
              <FileVideo className={clsx('w-8 h-8', isDragActive ? 'text-brand-400' : 'text-slate-400')} />
            </div>
            <div>
              <p className="text-lg font-semibold text-white">
                {isDragActive ? 'Drop to upload' : 'Drag & drop video here'}
              </p>
              <p className="text-sm text-slate-400 mt-1">
                or <span className="text-brand-400 underline underline-offset-2">click to browse</span>
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 text-xs text-slate-500">
              {['.mp4', '.avi', '.mov', '.mkv', '.webm'].map((ext) => (
                <span key={ext} className="px-2 py-0.5 rounded bg-slate-700/60">{ext}</span>
              ))}
            </div>
            <p className="text-xs text-slate-500">Maximum file size: 8 GB</p>
          </>
        )}
      </div>

      {/* Error */}
      {uploadError && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-300 flex-1">{uploadError}</p>
          <button onClick={() => setUploadError(null)}>
            <X className="w-4 h-4 text-red-400 hover:text-red-200" />
          </button>
        </div>
      )}

      {/* Video list */}
      <div className="glass-card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700/50">
          <h3 className="section-title">Uploaded Sessions</h3>
          <span className="text-xs text-slate-400">{videos.length} video{videos.length !== 1 ? 's' : ''}</span>
        </div>

        {isLoading ? (
          <div className="py-12 text-center text-slate-400 text-sm">Loading…</div>
        ) : videos.length === 0 ? (
          <div className="py-12 text-center space-y-2">
            <Film className="w-10 h-10 text-slate-600 mx-auto" />
            <p className="text-slate-400 text-sm">No videos uploaded yet</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-700/30">
            {videos.map((v) => (
              <li key={v.id} className="flex items-center gap-4 px-5 py-4 hover:bg-slate-800/30 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-brand-600/20 flex items-center justify-center flex-shrink-0">
                  <Film className="w-5 h-5 text-brand-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{v.original_filename}</p>
                  <div className="flex items-center flex-wrap gap-3 mt-0.5 text-xs text-slate-400">
                    <span>{formatBytes(v.file_size)}</span>
                    {v.duration_seconds != null && <span>{formatDuration(v.duration_seconds)}</span>}
                    {v.width && v.height && <span>{v.width}×{v.height}</span>}
                    <span>{format(new Date(v.created_at), 'dd MMM yyyy HH:mm')}</span>
                  </div>
                </div>
                <span className={clsx(
                  'metric-badge flex-shrink-0',
                  v.status === 'uploaded'   ? 'bg-blue-500/15   text-blue-300'   :
                  v.status === 'processing' ? 'bg-amber-500/15  text-amber-300'  :
                  v.status === 'complete'   ? 'bg-green-500/15  text-green-300'  :
                  'bg-red-500/15 text-red-300',
                )}>
                  {v.status === 'complete' && <CheckCircle2 className="w-3 h-3" />}
                  {v.status}
                </span>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={() => handleAnalyse(v)} className="btn-primary py-1.5 px-3 text-xs">
                    <Play className="w-3.5 h-3.5" /> Analyse
                  </button>
                  <button
                    onClick={() => { if (confirm('Delete this video and all associated data?')) doDelete(v.id); }}
                    className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="Delete (GDPR Article 17)"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Compliance notice */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-green-500/8 border border-green-500/20">
        <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
        <div className="text-xs text-green-300/80 space-y-0.5">
          <p className="font-medium text-green-300">Data Security & Compliance</p>
          <p>
            All video data is stored locally. VLM inference runs on your local Ollama instance —
            no data is sent to external APIs (UK GDPR Article 44 compliant). Files are integrity-verified
            with SHA-256 checksums. Delete at any time to exercise your right to erasure (Article 17).
          </p>
        </div>
      </div>
    </div>
  );
}
