import { create } from 'zustand';
import type { VideoUpload, AnalysisJob, AnalysisResult, ProgressUpdate } from '@/types';

interface HRIStore {
  // Videos
  videos: VideoUpload[];
  setVideos: (v: VideoUpload[]) => void;
  addVideo: (v: VideoUpload) => void;
  removeVideo: (id: string) => void;

  // Active job
  activeJobId: string | null;
  setActiveJobId: (id: string | null) => void;

  // Jobs
  jobs: AnalysisJob[];
  setJobs: (j: AnalysisJob[]) => void;
  upsertJob: (j: AnalysisJob) => void;

  // Progress
  progress: Record<string, ProgressUpdate>;
  setProgress: (jobId: string, p: ProgressUpdate) => void;

  // Results
  results: Record<string, AnalysisResult>;
  setResult: (jobId: string, r: AnalysisResult) => void;

  // UI
  activeTab: 'upload' | 'analysis' | 'results' | 'history';
  setActiveTab: (t: 'upload' | 'analysis' | 'results' | 'history') => void;
}

export const useHRIStore = create<HRIStore>((set) => ({
  videos: [],
  setVideos: (videos) => set({ videos }),
  addVideo: (v) => set((s) => ({ videos: [v, ...s.videos] })),
  removeVideo: (id) => set((s) => ({ videos: s.videos.filter((v) => v.id !== id) })),

  activeJobId: null,
  setActiveJobId: (id) => set({ activeJobId: id }),

  jobs: [],
  setJobs: (jobs) => set({ jobs }),
  upsertJob: (j) =>
    set((s) => {
      const idx = s.jobs.findIndex((jj) => jj.id === j.id);
      if (idx >= 0) {
        const updated = [...s.jobs];
        updated[idx] = j;
        return { jobs: updated };
      }
      return { jobs: [j, ...s.jobs] };
    }),

  progress: {},
  setProgress: (jobId, p) =>
    set((s) => ({ progress: { ...s.progress, [jobId]: p } })),

  results: {},
  setResult: (jobId, r) =>
    set((s) => ({ results: { ...s.results, [jobId]: r } })),

  activeTab: 'upload',
  setActiveTab: (t) => set({ activeTab: t }),
}));
