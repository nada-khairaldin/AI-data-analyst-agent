import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import WelcomeScreen from './components/WelcomeScreen';
import DatasetOverview from './components/DatasetOverview';
import ChatInterface from './components/ChatInterface';
import PreprocessingReport from './components/PreprocessingReport';
import DatasetRejected from './components/DatasetRejected';
import ErrorBanner from './components/ErrorBanner';
import { api, ApiError } from './api/client';
import { Menu, Sun, Moon } from 'lucide-react';

export default function App() {
  const [datasets, setDatasets] = useState([]);
  const [activeDatasetId, setActiveDatasetId] = useState(null);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [currentView, setCurrentView] = useState('welcome');
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [rejection, setRejection] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const refreshDatasets = useCallback(async () => {
    try {
      const body = await api.listDatasets();
      setDatasets(body.datasets);
      return body.datasets;
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
      return [];
    }
  }, []);

  // First paint. A cold Render instance takes 30-60s to wake, so the spinner
  // has to resolve either way — never hang.
  useEffect(() => {
    (async () => {
      await refreshDatasets();
      setIsLoading(false);
    })();
  }, [refreshDatasets]);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ''; // so picking the same file again re-triggers

    setIsUploading(true);
    setError(null);
    setRejection(null);

    try {
      const dataset = await api.uploadDataset(file);
      await refreshDatasets();
      setActiveDatasetId(dataset.id);
      setActiveConversationId(null);
      setReport(null);
      setCurrentView('overview');
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === 'DATASET_REJECTED') {
        // The rejection screen renders these; fall back to the filename we
        // already know if the server sent no details.
        setRejection({ filename: file.name, ...(cause.details || {}) });
        setCurrentView('rejected');
      } else {
        setError(cause instanceof ApiError ? cause.message : String(cause));
      }
    } finally {
      setIsUploading(false);
    }
  };

  const openDataset = async (id) => {
    setActiveDatasetId(id);
    setActiveConversationId(null);
    setCurrentView('overview');
    setIsMobileOpen(false);
    setReport(null);
    setError(null);
    try {
      setReport(await api.getReport(id));
    } catch (cause) {
      // The overview still works without the report; only the quality card
      // and the report view need it.
      setError(cause instanceof ApiError ? cause.message : String(cause));
    }
  };

  const openConversation = (datasetId, conversationId) => {
    setActiveDatasetId(datasetId);
    setActiveConversationId(conversationId);
    setCurrentView('chat');
    setIsMobileOpen(false);
    setError(null);
  };

  const startConversation = async (datasetId) => {
    setError(null);
    try {
      const conversation = await api.createConversation(datasetId);
      await refreshDatasets();
      openConversation(datasetId, conversation.id);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    }
  };

  const activeDataset = datasets.find((d) => d.id === activeDatasetId) || null;
  const activeConversation =
    activeDataset?.conversations?.find((c) => c.id === activeConversationId) || null;

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-dark-bg font-sans overflow-hidden">
      <Sidebar
        datasets={datasets}
        activeDatasetId={activeDatasetId}
        activeConversationId={activeConversationId}
        onSelectDataset={openDataset}
        onSelectConversation={openConversation}
        onNewConversation={startConversation}
        onUploadDataset={() => setCurrentView('welcome')}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
        isLoading={isLoading}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <div className="lg:hidden flex items-center justify-between p-4 bg-white dark:bg-dark-sidebar border-b border-slate-200 dark:border-dark-border z-10">
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 -ml-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white"
          >
            <Menu size={24} />
          </button>
          <div className="font-semibold text-slate-800 dark:text-white">AI Data Analyst</div>
          <button
            onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
            className="w-10 h-10 flex items-center justify-center -mr-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white transition-colors"
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>

        <button
          onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
          className="hidden lg:flex absolute top-4 right-6 z-50 w-10 h-10 items-center justify-center bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-full shadow-sm text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white transition-colors"
          title="Toggle Theme"
        >
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <main className="flex-1 overflow-hidden flex flex-col relative">
          {currentView === 'welcome' && (
            <WelcomeScreen onFileUpload={handleFileUpload} isUploading={isUploading} />
          )}

          {currentView === 'overview' && activeDataset && (
            <DatasetOverview
              dataset={activeDataset}
              report={report}
              onBack={() => setCurrentView('welcome')}
              onNewConversation={startConversation}
              onSelectConversation={openConversation}
              onShowReport={() => setCurrentView('report')}
            />
          )}

          {currentView === 'chat' && activeDataset && activeConversation && (
            <ChatInterface
              dataset={activeDataset}
              conversation={activeConversation}
              onTurnComplete={refreshDatasets}
            />
          )}

          {currentView === 'report' && activeDataset && (
            <PreprocessingReport
              dataset={activeDataset}
              report={report}
              onBack={() => setCurrentView('overview')}
            />
          )}

          {currentView === 'rejected' && (
            <DatasetRejected
              {...(rejection || {})}
              onUploadAnother={() => setCurrentView('welcome')}
              onClose={() => setCurrentView('welcome')}
            />
          )}
        </main>
      </div>
    </div>
  );
}
