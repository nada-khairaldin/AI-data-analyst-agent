import React, { useState, useEffect } from 'react';
import { Plus, Search, Settings, FileText, ChevronDown, ChevronRight, MessageSquare, UploadCloud, Database } from 'lucide-react';

export default function Sidebar({ 
  datasets = [], 
  activeDatasetId, 
  onSelectDataset, 
  onNewConversation, 
  onUploadDataset,
  activeConversationId,
  onSelectConversation,
  isMobileOpen,
  setIsMobileOpen
}) {
  const [expandedId, setExpandedId] = useState(activeDatasetId);

  useEffect(() => {
    if (activeDatasetId) {
      setExpandedId(activeDatasetId);
    }
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
      {/* Mobile overlay */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-dark-sidebar border-r border-dark-border text-slate-300
        transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0
        flex flex-col h-screen
        ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Header */}
        <div className="p-5 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/20 text-primary flex items-center justify-center flex-shrink-0">
            <Database size={18} />
          </div>
          <div>
            <h1 className="text-white font-semibold text-lg leading-tight">AI Data Analyst</h1>
            <p className="text-xs text-slate-500">Your data. Just ask.</p>
          </div>
        </div>

        {/* Global Actions */}
        <div className="px-4 pb-4 space-y-2">
          <button 
            onClick={onUploadDataset}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-200 bg-white/5 hover:bg-white/10 rounded-md transition-colors border border-white/5"
          >
            <UploadCloud size={16} />
            <span>Upload dataset</span>
          </button>
          
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input 
              type="text" 
              placeholder="Search conversations..." 
              className="w-full bg-dark-bg border border-dark-border rounded-md py-1.5 pl-9 pr-3 text-sm text-slate-300 focus:outline-none focus:border-primary/50 transition-colors placeholder:text-slate-600"
            />
          </div>
        </div>

        {/* Datasets List */}
        <div className="flex-1 overflow-y-auto px-4 py-2 custom-scrollbar">
          <div className="text-xs font-semibold text-slate-500 tracking-wider mb-3 px-1">YOUR DATASETS</div>
          
          <div className="space-y-1">
            {datasets.map(dataset => {
              const isActive = dataset.id === activeDatasetId;
              const isExpanded = dataset.id === expandedId;
              
              return (
                <div key={dataset.id} className="mb-2">
                  <button 
                    onClick={() => handleDatasetClick(dataset.id)}
                    className={`w-full flex items-center justify-between px-2 py-1.5 rounded-md text-sm transition-colors ${
                      isActive ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-white/5 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center gap-2 overflow-hidden">
                      <FileText size={16} className={isActive ? 'text-primary' : 'text-slate-500'} />
                      <span className="truncate">{dataset.name}</span>
                    </div>
                    {dataset.conversations?.length > 0 && (
                      <div className="flex-shrink-0 text-slate-500">
                        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </div>
                    )}
                  </button>
                  
                  {isExpanded && dataset.conversations?.length > 0 && (
                    <div className="ml-6 mt-1 space-y-0.5 border-l border-dark-border/50 pl-2">
                      {dataset.conversations.map(conv => (
                        <button
                          key={conv.id}
                          onClick={() => onSelectConversation(dataset.id, conv.id)}
                          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors text-left ${
                            conv.id === activeConversationId 
                              ? 'text-white bg-white/5' 
                              : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                          }`}
                        >
                          <MessageSquare size={14} className={conv.id === activeConversationId ? 'text-primary/70' : 'text-slate-600'} />
                          <span className="truncate">{conv.title}</span>
                        </button>
                      ))}
                      
                      <button
                        onClick={() => onNewConversation(dataset.id)}
                        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors mt-1"
                      >
                        <Plus size={14} />
                        <span>New conversation</span>
                      </button>
                    </div>
                  )}
                  
                  {/* Show info sub-text if not expanded to match design */}
                  {!isExpanded && (
                    <div className="ml-8 text-[11px] text-slate-500 mt-0.5 truncate">
                      {dataset.rowCount?.toLocaleString()} rows • {dataset.colCount} columns
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 mt-auto border-t border-dark-border">
          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-medium text-sm flex-shrink-0">
                U
              </div>
              <div className="overflow-hidden">
                <div className="text-sm text-slate-200 font-medium truncate">User Name</div>
                <div className="text-xs text-slate-500 truncate">user@example.com</div>
              </div>
            </div>
            <button className="text-slate-400 hover:text-slate-200 transition-colors p-1.5 rounded-md hover:bg-white/5" title="Settings">
              <Settings size={18} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
