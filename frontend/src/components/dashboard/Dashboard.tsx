'use client';
import { useHRIStore } from '@/store/hriStore';
import { useAuthStore } from '@/store/authStore';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { UploadPanel }   from '@/components/upload/UploadPanel';
import { AnalysisPanel } from '@/components/analysis/AnalysisPanel';
import { ResultsPanel }  from '@/components/analysis/ResultsPanel';
import { HistoryPanel }  from './HistoryPanel';

export function Dashboard() {
  const { activeTab }     = useHRIStore();
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) return null;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-950">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          {activeTab === 'upload'   && <UploadPanel />}
          {activeTab === 'analysis' && <AnalysisPanel />}
          {activeTab === 'results'  && <ResultsPanel />}
          {activeTab === 'history'  && <HistoryPanel />}
        </main>
      </div>
    </div>
  );
}
