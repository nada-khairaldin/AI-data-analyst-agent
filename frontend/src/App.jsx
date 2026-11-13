import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import WelcomeScreen from './components/WelcomeScreen';
import DatasetOverview from './components/DatasetOverview';
import ChatInterface from './components/ChatInterface';
import DatasetRejected from './components/DatasetRejected';
import ErrorBanner from './components/ErrorBanner';
import ConfirmDialog from './components/ConfirmDialog';
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
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

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

  // The report belongs to whichever dataset is active, so it loads from one
  // place keyed on the id. It used to be fetched inside openDataset only,
  // which meant an upload — which sets the id directly — left the quality
  // card and the preparation tab empty until the page was reloaded.
  useEffect(() => {
    if (!activeDatasetId) {
      setReport(null);
      return;
    }
    let cancelled = false;
    setReport(null);
    setIsReportLoading(true);
    (async () => {
      try {
        const body = await api.getReport(activeDatasetId);
        if (!cancelled) setReport(body);
      } catch (cause) {
        // The overview still works without it; only the quality card and the
        // preparation tab need the report.
        if (!cancelled) setError(cause instanceof ApiError ? cause.message : String(cause));
      } finally {
        if (!cancelled) setIsReportLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeDatasetId]);

  // Takes a File, not an event, so the picker and the drop zone share one
  // path and cannot validate differently.
  const handleFileUpload = async (file) => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setRejection(null);

    try {
      const dataset = await api.uploadDataset(file);
      await refreshDatasets();
      setActiveDatasetId(dataset.id);
      setActiveConversationId(null);
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

  const openDataset = (id) => {
    setActiveDatasetId(id);   // the effect above loads the report
    setActiveConversationId(null);
    setCurrentView('overview');
    setIsMobileOpen(false);
    setError(null);
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

  // Deleting is confirmed through a dialog, so the click only records what
  // was asked for; confirmDelete does the work.
  const askDeleteDataset = (dataset) =>
    setPendingDelete({ kind: 'dataset', id: dataset.id, name: dataset.name,
      conversationCount: dataset.conversations?.length || 0 });

  const askDeleteConversation = (datasetId, conversation) =>
    setPendingDelete({ kind: 'conversation', id: conversation.id,
      name: conversation.title, datasetId });

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setIsDeleting(true);
    setError(null);
    try {
      if (pendingDelete.kind === 'dataset') {
        await api.deleteDataset(pendingDelete.id);
        const remaining = await refreshDatasets();
        // Only move if the thing being looked at is the thing deleted.
        if (pendingDelete.id === activeDatasetId) {
          const next = remaining[0];
          setActiveConversationId(null);
          setActiveDatasetId(next ? next.id : null);
          setCurrentView(next ? 'overview' : 'welcome');
        }
      } else {
        await api.deleteConversation(pendingDelete.id);
        await refreshDatasets();
        if (pendingDelete.id === activeConversationId) {
          setActiveConversationId(null);
          setCurrentView('overview');
        }
      }
      setPendingDelete(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
      setPendingDelete(null);
    } finally {
      setIsDeleting(false);
    }
  };

  const activeDataset = datasets.find((d) => d.id === activeDatasetId) || null;
  const activeConversation =
    activeDataset?.conversations?.find((c) => c.id === activeConversationId) || null;

  return (
    <div className="flex h-screen bg-paper font-sans overflow-hidden">
      <Sidebar
        datasets={datasets}
        activeDatasetId={activeDatasetId}
        activeConversationId={activeConversationId}
        onSelectDataset={openDataset}
        onSelectConversation={openConversation}
        onNewConversation={startConversation}
        onUploadDataset={() => setCurrentView('welcome')}
        onDeleteDataset={askDeleteDataset}
        onDeleteConversation={askDeleteConversation}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
        isLoading={isLoading}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <div className="lg:hidden flex items-center justify-between p-4 bg-surface border-b border-rule z-10">
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 -ml-2 text-graphite hover:text-ink"
          >
            <Menu size={20} strokeWidth={1.5} />
          </button>
          <div className="text-ink">Data analyst</div>
          <button
            onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
            className="w-10 h-10 flex items-center justify-center -mr-2 text-graphite hover:text-ink"
          >
            {theme === 'dark' ? <Sun size={18} strokeWidth={1.5} /> : <Moon size={18} strokeWidth={1.5} />}
          </button>
        </div>

        <button
          onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
          className="hidden lg:flex absolute top-3 right-5 z-50 w-9 h-9 items-center justify-center rounded-md text-graphite hover:text-ink hover:bg-surface"
          title="Toggle Theme"
        >
          {theme === 'dark' ? <Sun size={18} strokeWidth={1.5} /> : <Moon size={18} strokeWidth={1.5} />}
        </button>

        {error && (
          <ErrorBanner
            message={error}
            onRetry={async () => {
              setError(null);
              setIsLoading(true);
              await refreshDatasets();
              setIsLoading(false);
            }}
            onDismiss={() => setError(null)}
          />
        )}

        <main className="flex-1 overflow-hidden flex flex-col relative">
          {currentView === 'welcome' && (
            <WelcomeScreen onFileUpload={handleFileUpload} isUploading={isUploading} />
          )}

          {currentView === 'overview' && activeDataset && (
            <DatasetOverview
              dataset={activeDataset}
              report={report}
              isReportLoading={isReportLoading}
              onBack={() => setCurrentView('welcome')}
              onNewConversation={startConversation}
              onSelectConversation={openConversation}
            />
          )}

          {currentView === 'chat' && activeDataset && activeConversation && (
            <ChatInterface
              dataset={activeDataset}
              conversation={activeConversation}
              onTurnComplete={refreshDatasets}
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

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        isBusy={isDeleting}
        title={
          pendingDelete?.kind === 'dataset' ? 'Delete this dataset?' : 'Delete this conversation?'
        }
        body={
          pendingDelete?.kind === 'dataset' ? (
            <>
              <strong className="text-ink">{pendingDelete?.name}</strong>{' '}
              and its stored file will be deleted.
              {pendingDelete?.conversationCount > 0 && (
                <>
                  {' '}
                  Its {pendingDelete.conversationCount} conversation
                  {pendingDelete.conversationCount === 1 ? '' : 's'} will be deleted too.
                </>
              )}{' '}
              This cannot be undone.
            </>
          ) : (
            <>
              <strong className="text-ink">{pendingDelete?.name}</strong>{' '}
              and all of its messages will be deleted. This cannot be undone.
            </>
          )
        }
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
