import React, { useState, useEffect } from 'react';
import {
  Plus,
  FileText,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  UploadCloud,
  Trash2,
} from 'lucide-react';
import { SidebarSkeleton } from './Skeleton';

// Conversations arrive ordered by last_message_at DESC, so the newest few are
// simply the first few.
const COLLAPSED_COUNT = 4;

export default function Sidebar({
  isLoading,
  datasets = [],
  activeDatasetId,
  onSelectDataset,
  onNewConversation,
  onUploadDataset,
  activeConversationId,
  onSelectConversation,
  isMobileOpen,
  setIsMobileOpen,
  onDeleteDataset,
  onDeleteConversation,
}) {
  const [expandedId, setExpandedId] = useState(activeDatasetId);
  const [showAllFor, setShowAllFor] = useState({});

  useEffect(() => {
    if (activeDatasetId) setExpandedId(activeDatasetId);
  }, [activeDatasetId]);

  const handleDatasetClick = (id) => {
    if (expandedId === id) {
      setExpandedId(null);
    } else {
      setExpandedId(id);
      onSelectDataset(id);
    }
  };

  return (
    <>
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 bg-dark-sidebar border-r border-dark-border text-slate-300
        transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0
        flex flex-col h-screen
        ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* One scroll area: the brand, the upload button and the whole dataset
            tree scroll together. A scrollable list nested in a scrollable
            sidebar traps the wheel and is why long lists felt stuck. */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="p-5 flex items-center gap-3">
            <img
              src={`${import.meta.env.BASE_URL}logo.png`}
              alt=""
              width="32"
              height="32"
              className="w-8 h-8 shrink-0"
            />
            <div>
              <h1 className="text-white font-semibold text-lg leading-tight">AI Data Analyst</h1>
              <p className="text-xs text-slate-400">Your data. Just ask.</p>
            </div>
          </div>

          <div className="px-4 pb-4">
            <button
              onClick={onUploadDataset}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-200 bg-white/5 hover:bg-white/10 rounded-md transition-colors border border-white/5"
            >
              <UploadCloud size={16} />
              <span>Upload dataset</span>
            </button>
          </div>

          <div className="px-4 pb-4">
            <div className="text-xs font-semibold text-slate-400 tracking-wider mb-3 px-1">
              YOUR DATASETS
            </div>

            {isLoading && <SidebarSkeleton />}

            {!isLoading && datasets.length === 0 && (
              <div className="px-1 py-2 text-sm text-slate-400">
                No datasets yet. Upload a CSV to start.
              </div>
            )}

            <div className="space-y-1">
              {datasets.map((dataset) => {
                const isActive = dataset.id === activeDatasetId;
                const isExpanded = dataset.id === expandedId;
                const conversations = dataset.conversations || [];
                const showAll = showAllFor[dataset.id];
                const visible = showAll
                  ? conversations
                  : conversations.slice(0, COLLAPSED_COUNT);
                const hidden = conversations.length - visible.length;

                return (
                  <div key={dataset.id} className="mb-2">
                    <div
                      className={`group flex items-center rounded-md transition-colors ${
                        isActive
                          ? 'bg-primary/10 text-primary font-medium'
                          : 'hover:bg-white/5 text-slate-300'
                      }`}
                    >
                      <button
                        onClick={() => handleDatasetClick(dataset.id)}
                        className="flex-1 flex items-center justify-between px-2 py-1.5 text-sm min-w-0"
                      >
                        <div className="flex items-center gap-2 overflow-hidden">
                          <FileText
                            size={16}
                            className={isActive ? 'text-primary' : 'text-slate-400'}
                          />
                          <span className="truncate">{dataset.name}</span>
                        </div>
                        {conversations.length > 0 && (
                          <div className="shrink-0 text-slate-400 ml-2">
                            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </div>
                        )}
                      </button>
                      <button
                        onClick={() => onDeleteDataset?.(dataset)}
                        aria-label={`Delete ${dataset.name}`}
                        title="Delete dataset"
                        className="shrink-0 p-1.5 mr-1 rounded text-slate-500 opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-rose-400 hover:bg-white/5 transition-all"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>

                    {isExpanded ? (
                      <div className="ml-6 mt-1 space-y-0.5 border-l border-dark-border/50 pl-2">
                        {visible.map((conv) => (
                          <div
                            key={conv.id}
                            className={`group/conv flex items-center rounded-md transition-colors ${
                              conv.id === activeConversationId
                                ? 'text-white bg-white/5'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                            }`}
                          >
                            <button
                              onClick={() => onSelectConversation(dataset.id, conv.id)}
                              className="flex-1 flex items-center gap-2 px-2 py-1.5 text-sm text-left min-w-0"
                            >
                              <MessageSquare
                                size={14}
                                className={
                                  conv.id === activeConversationId
                                    ? 'text-primary/70'
                                    : 'text-slate-500'
                                }
                              />
                              <span className="truncate">{conv.title}</span>
                            </button>
                            <button
                              onClick={() => onDeleteConversation?.(dataset.id, conv)}
                              aria-label={`Delete ${conv.title}`}
                              title="Delete conversation"
                              className="shrink-0 p-1.5 mr-1 rounded text-slate-500 opacity-0 group-hover/conv:opacity-100 focus:opacity-100 hover:text-rose-400 transition-all"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        ))}

                        {hidden > 0 && (
                          <button
                            onClick={() =>
                              setShowAllFor((current) => ({ ...current, [dataset.id]: true }))
                            }
                            className="w-full text-left px-2 py-1.5 rounded-md text-xs text-primary hover:bg-white/5 transition-colors"
                          >
                            Show all ({conversations.length})
                          </button>
                        )}

                        {showAll && conversations.length > COLLAPSED_COUNT && (
                          <button
                            onClick={() =>
                              setShowAllFor((current) => ({ ...current, [dataset.id]: false }))
                            }
                            className="w-full text-left px-2 py-1.5 rounded-md text-xs text-slate-400 hover:bg-white/5 transition-colors"
                          >
                            Show fewer
                          </button>
                        )}

                        <button
                          onClick={() => onNewConversation(dataset.id)}
                          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors mt-1"
                        >
                          <Plus size={14} />
                          <span>New conversation</span>
                        </button>
                      </div>
                    ) : (
                      <div className="ml-8 text-[11px] text-slate-400 mt-0.5 truncate">
                        {dataset.rowCount?.toLocaleString()} rows &middot; {dataset.colCount}{' '}
                        columns
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-dark-border shrink-0">
          <p className="text-xs text-slate-400 leading-relaxed px-1">
            Your workspace is saved in this browser.
          </p>
        </div>
      </aside>
    </>
  );
}
