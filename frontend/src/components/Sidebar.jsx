import React, { useState, useEffect } from 'react';
import { Plus, ChevronDown, ChevronRight, Trash2 } from 'lucide-react';
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
          className="fixed inset-0 bg-ink/40 z-40 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 bg-surface border-r border-rule
        transform transition-transform duration-200 ease-out lg:relative lg:translate-x-0
        flex flex-col h-screen
        ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* One scroll area: the title, the upload button and the whole dataset
            tree scroll together. A scrollable list nested in a scrollable
            sidebar traps the wheel. */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 pt-5 pb-4">
            <h1 className="text-ink">Data analyst</h1>
          </div>

          <div className="px-4 pb-5">
            <button
              onClick={onUploadDataset}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm text-paper bg-verdigris rounded-md hover:brightness-110"
            >
              <Plus size={15} strokeWidth={1.5} />
              Upload a CSV
            </button>
          </div>

          <div className="px-4 pb-4">
            <div className="text-sm text-graphite mb-2">Datasets</div>

            {isLoading && <SidebarSkeleton />}

            {!isLoading && datasets.length === 0 && (
              <p className="text-sm text-graphite py-1">Nothing yet. Upload a CSV to start.</p>
            )}

            <div>
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
                      className={`group flex items-center rounded-md ${
                        isActive ? 'bg-verdigris/10' : 'hover:bg-paper'
                      }`}
                    >
                      <button
                        onClick={() => handleDatasetClick(dataset.id)}
                        className="flex-1 flex items-center justify-between px-2 py-1.5 text-sm min-w-0"
                      >
                        <span className={`truncate ${isActive ? 'text-verdigris' : 'text-ink'}`}>
                          {dataset.name}
                        </span>
                        {conversations.length > 0 &&
                          (isExpanded ? (
                            <ChevronDown
                              size={14}
                              strokeWidth={1.5}
                              className="text-graphite ml-2 shrink-0"
                            />
                          ) : (
                            <ChevronRight
                              size={14}
                              strokeWidth={1.5}
                              className="text-graphite ml-2 shrink-0"
                            />
                          ))}
                      </button>
                      <button
                        onClick={() => onDeleteDataset?.(dataset)}
                        aria-label={`Delete ${dataset.name}`}
                        className="shrink-0 p-1.5 mr-1 rounded text-graphite opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-ink"
                      >
                        <Trash2 size={14} strokeWidth={1.5} />
                      </button>
                    </div>

                    {isExpanded ? (
                      <div className="ml-3 mt-1 border-l border-rule pl-2">
                        {visible.map((conv) => (
                          <div
                            key={conv.id}
                            className={`group/conv flex items-center rounded-md ${
                              conv.id === activeConversationId ? 'bg-paper' : 'hover:bg-paper'
                            }`}
                          >
                            <button
                              onClick={() => onSelectConversation(dataset.id, conv.id)}
                              className={`flex-1 px-2 py-1.5 text-sm text-left truncate min-w-0 ${
                                conv.id === activeConversationId ? 'text-ink' : 'text-graphite'
                              }`}
                            >
                              {conv.title}
                            </button>
                            <button
                              onClick={() => onDeleteConversation?.(dataset.id, conv)}
                              aria-label={`Delete ${conv.title}`}
                              className="shrink-0 p-1.5 mr-1 rounded text-graphite opacity-0 group-hover/conv:opacity-100 focus:opacity-100 hover:text-ink"
                            >
                              <Trash2 size={13} strokeWidth={1.5} />
                            </button>
                          </div>
                        ))}

                        {hidden > 0 && (
                          <button
                            onClick={() =>
                              setShowAllFor((current) => ({ ...current, [dataset.id]: true }))
                            }
                            className="w-full text-left px-2 py-1.5 text-sm text-verdigris hover:underline"
                          >
                            Show all ({conversations.length})
                          </button>
                        )}

                        {showAll && conversations.length > COLLAPSED_COUNT && (
                          <button
                            onClick={() =>
                              setShowAllFor((current) => ({ ...current, [dataset.id]: false }))
                            }
                            className="w-full text-left px-2 py-1.5 text-sm text-graphite hover:text-ink"
                          >
                            Show fewer
                          </button>
                        )}

                        <button
                          onClick={() => onNewConversation(dataset.id)}
                          className="w-full flex items-center gap-1.5 px-2 py-1.5 text-sm text-graphite hover:text-ink"
                        >
                          <Plus size={14} strokeWidth={1.5} />
                          New conversation
                        </button>
                      </div>
                    ) : (
                      <div className="ml-2 text-sm text-graphite truncate tabular">
                        {dataset.rowCount?.toLocaleString()} rows
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="px-4 py-4 border-t border-rule shrink-0">
          <p className="text-sm text-graphite">Your workspace is saved in this browser.</p>
        </div>
      </aside>
    </>
  );
}
