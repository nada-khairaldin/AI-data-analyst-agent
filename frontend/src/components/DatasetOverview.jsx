import React, { useState } from 'react';
import { ArrowLeft, FileText, CheckCircle2, MoreHorizontal, MessageSquare, AlertCircle } from 'lucide-react';

export default function DatasetOverview({ 
  dataset, 
  onBack, 
  onNewConversation, 
  onSelectConversation,
  onShowReport 
}) {
  const [activeTab, setActiveTab] = useState('Overview');
  const tabs = ['Overview', 'Data Preparation', 'Columns & Types', 'Preview', 'Conversations'];

  if (!dataset) return null;

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary overflow-hidden">
      
      {/* Header */}
      <header className="bg-white dark:bg-dark-sidebar border-b border-slate-200 dark:border-dark-border px-6 py-4 flex-shrink-0">
        <button 
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 mb-4 transition-colors"
        >
          <ArrowLeft size={16} />
          Back to datasets
        </button>
        
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center border border-primary/20">
              <FileText size={24} />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-slate-800 dark:text-white flex items-center gap-3">
                {dataset.name}
              </h2>
              <p className="text-sm text-slate-500 mt-0.5">
                {dataset.rowCount?.toLocaleString()} rows • {dataset.colCount} columns • {dataset.size || '45 KB'}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-success/10 text-success border border-success/20 rounded-full text-sm font-medium">
              <CheckCircle2 size={16} />
              Ready for analysis
            </div>
            <button className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors">
              <MoreHorizontal size={20} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-6 mt-6 overflow-x-auto custom-scrollbar">
          {tabs.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium whitespace-nowrap transition-colors relative ${
                activeTab === tab 
                  ? 'text-primary' 
                  : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              {tab}
              {activeTab === tab && (
                <span className="absolute bottom-0 left-0 w-full h-0.5 bg-primary rounded-t-full" />
              )}
            </button>
          ))}
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'Overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
            
            <div className="lg:col-span-2 space-y-6">
              {/* Dataset Summary */}
              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-5 shadow-sm">
                <h3 className="text-base font-semibold mb-4 text-slate-800 dark:text-slate-200">Dataset Summary</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="space-y-1">
                    <div className="text-2xl font-bold text-slate-800 dark:text-white">{dataset.rowCount?.toLocaleString()}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider">Rows</div>
                  </div>
                  <div className="space-y-1 border-l border-slate-100 dark:border-dark-border pl-4">
                    <div className="text-2xl font-bold text-slate-800 dark:text-white">{dataset.colCount}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider">Columns</div>
                  </div>
                  <div className="space-y-1 border-l border-slate-100 dark:border-dark-border pl-4">
                    <div className="text-2xl font-bold text-slate-800 dark:text-white">{dataset.missingRate || '2.1%'}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider">Missing values</div>
                  </div>
                  <div className="space-y-1 border-l border-slate-100 dark:border-dark-border pl-4">
                    <div className="text-2xl font-bold text-slate-800 dark:text-white">{dataset.duplicateRate || '0.4%'}</div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider">Duplicate rows</div>
                  </div>
                </div>
              </div>

              {/* Recent Conversations */}
              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-0 shadow-sm overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-dark-border">
                  <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">Recent Conversations</h3>
                  <button className="text-sm text-primary hover:text-primary/80 transition-colors">View all &rarr;</button>
                </div>
                
                <div className="divide-y divide-slate-100 dark:divide-dark-border">
                  {dataset.conversations?.slice(0, 3).map(conv => (
                    <button 
                      key={conv.id}
                      onClick={() => onSelectConversation(dataset.id, conv.id)}
                      className="w-full text-left p-4 hover:bg-slate-50 dark:hover:bg-dark-elevated transition-colors flex items-start gap-3"
                    >
                      <div className="mt-0.5 text-slate-400 bg-slate-100 dark:bg-dark-bg p-2 rounded-lg">
                        <MessageSquare size={16} />
                      </div>
                      <div>
                        <div className="font-medium text-slate-800 dark:text-slate-200">{conv.title}</div>
                        <div className="text-sm text-slate-500 flex gap-2">
                          <span>{conv.date || '2 hours ago'}</span>
                          <span>•</span>
                          <span>{conv.messageCount || 12} messages</span>
                        </div>
                      </div>
                    </button>
                  ))}
                  {(!dataset.conversations || dataset.conversations.length === 0) && (
                    <div className="p-8 text-center text-slate-500">
                      No conversations yet. Start one to analyze data.
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-6">
              {/* Data Quality */}
              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-5 shadow-sm">
                <h3 className="text-base font-semibold mb-4 text-slate-800 dark:text-slate-200">Data Quality</h3>
                
                <div className="flex flex-col items-center justify-center p-4">
                  {/* Mock Circular Progress */}
                  <div className="relative w-32 h-32 mb-4">
                    <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" className="text-slate-100 dark:text-dark-border" strokeWidth="8" />
                      <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" className="text-success" strokeWidth="8" strokeDasharray="283" strokeDashoffset="6" />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                      <span className="text-2xl font-bold text-slate-800 dark:text-white">97.9%</span>
                      <span className="text-xs text-success font-medium">Good</span>
                    </div>
                  </div>
                  
                  <div className="w-full space-y-2 mt-2 text-sm">
                    <div className="flex justify-between text-slate-600 dark:text-slate-400">
                      <span className="flex items-center gap-1.5"><AlertCircle size={14} className="text-warning"/> 1 column excluded</span>
                    </div>
                    <div className="flex justify-between text-slate-600 dark:text-slate-400">
                      <span className="flex items-center gap-1.5"><CheckCircle2 size={14} className="text-success"/> 2 columns converted</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-5 shadow-sm">
                <h3 className="text-base font-semibold mb-4 text-slate-800 dark:text-slate-200">Quick Actions</h3>
                <div className="space-y-3">
                  <button 
                    onClick={() => onNewConversation(dataset.id)}
                    className="w-full py-2.5 px-4 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium transition-colors shadow-sm"
                  >
                    Start new conversation
                  </button>
                  <button 
                    onClick={onShowReport}
                    className="w-full py-2.5 px-4 bg-white dark:bg-dark-bg border border-slate-200 dark:border-dark-border hover:bg-slate-50 dark:hover:bg-dark-elevated text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-colors"
                  >
                    View preprocessing report
                  </button>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* Other tabs placeholder */}
        {activeTab !== 'Overview' && (
          <div className="h-full flex items-center justify-center text-slate-500">
            {activeTab} content will be displayed here.
          </div>
        )}
      </div>
    </div>
  );
}
