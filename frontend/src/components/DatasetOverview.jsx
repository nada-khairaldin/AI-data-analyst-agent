import React, { useState, useEffect } from 'react';
import { ArrowLeft, FileText, CheckCircle2, MessageSquare, AlertCircle } from 'lucide-react';
import DataPreparation from './DataPreparation';
import ColumnsTable from './ColumnsTable';
import PreviewTable from './PreviewTable';
import { Bar } from './Skeleton';
import QualityRing from './QualityRing';
import { api, ApiError } from '../api/client';

const TABS = ['Overview', 'Data Preparation', 'Columns & Types', 'Preview'];

export default function DatasetOverview({
  dataset,
  report,
  isReportLoading,
  onBack,
  onNewConversation,
  onSelectConversation,
}) {
  const [activeTab, setActiveTab] = useState('Overview');
  const [columns, setColumns] = useState(null);
  const [preview, setPreview] = useState(null);
  const [tabError, setTabError] = useState(null);

  const datasetId = dataset?.id;

  // A different dataset invalidates everything the tabs are showing.
  useEffect(() => {
    setActiveTab('Overview');
    setColumns(null);
    setPreview(null);
    setTabError(null);
  }, [datasetId]);

  // Columns and preview are fetched the first time their tab is opened, not
  // on every dataset: most of the time nobody looks, and the demo runs on a
  // free instance where each request costs a round trip to the other coast.
  useEffect(() => {
    if (!datasetId) return undefined;
    const wantsColumns = activeTab === 'Columns & Types' && !columns;
    const wantsPreview = activeTab === 'Preview' && !preview;
    if (!wantsColumns && !wantsPreview) return undefined;

    let cancelled = false;
    (async () => {
      try {
        if (wantsColumns) {
          const body = await api.getColumns(datasetId);
          if (!cancelled) setColumns(body.columns);
        } else {
          const body = await api.getPreview(datasetId);
          if (!cancelled) setPreview(body);
        }
      } catch (cause) {
        if (!cancelled) {
          setTabError(cause instanceof ApiError ? cause.message : String(cause));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [datasetId, activeTab, columns, preview]);

  if (!dataset) return null;

  // The circle is a 283-unit circumference; the offset is the unfilled part.
  const score = report ? parseFloat(report.qualityScore) : null;
  const scoreColor =
    report?.qualityLabel === 'Good'
      ? 'text-success'
      : report?.qualityLabel === 'Fair'
        ? 'text-warning'
        : 'text-error';

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary overflow-hidden">
      <header className="bg-white dark:bg-dark-sidebar border-b border-slate-200 dark:border-dark-border px-6 py-4 shrink-0">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200 mb-4 transition-colors"
        >
          <ArrowLeft size={16} />
          Back to datasets
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4 min-w-0">
            <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center border border-primary/20 shrink-0">
              <FileText size={24} />
            </div>
            <div className="min-w-0">
              <h2 className="text-2xl font-bold text-slate-800 dark:text-white truncate">
                {dataset.name}
              </h2>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
                {dataset.rowCount?.toLocaleString()} rows &middot; {dataset.colCount} columns
                &middot; {dataset.size}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-success/10 text-success border border-success/20 rounded-full text-sm font-medium shrink-0">
            <CheckCircle2 size={16} />
            Ready for analysis
          </div>
        </div>

        <div className="flex items-center gap-6 mt-6 overflow-x-auto custom-scrollbar">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium whitespace-nowrap transition-colors relative ${
                activeTab === tab
                  ? 'text-primary'
                  : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
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

      <div className="flex-1 overflow-y-auto p-6">
        {tabError && activeTab !== 'Overview' && (
          <div className="max-w-6xl mx-auto mb-4 text-sm text-rose-700 dark:text-error bg-rose-50 dark:bg-error/10 border border-rose-200 dark:border-error/30 rounded-lg px-4 py-3">
            {tabError}
          </div>
        )}

        {activeTab === 'Overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-5 shadow-sm">
                <h3 className="text-base font-semibold mb-4 text-slate-800 dark:text-slate-200">
                  Dataset Summary
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {[
                    ['Rows', dataset.rowCount?.toLocaleString()],
                    ['Columns', dataset.colCount],
                    ['Missing values', dataset.missingRate],
                    ['Duplicate rows', dataset.duplicateRate],
                  ].map(([label, value], index) => (
                    <div
                      key={label}
                      className={`space-y-1 ${index ? 'border-l border-slate-100 dark:border-dark-border pl-4' : ''}`}
                    >
                      <div className="text-2xl font-bold text-slate-800 dark:text-white">
                        {value}
                      </div>
                      <div className="text-xs text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                        {label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border shadow-sm overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-dark-border">
                  <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
                    Recent Conversations
                  </h3>
                </div>

                <div className="divide-y divide-slate-100 dark:divide-dark-border">
                  {dataset.conversations?.slice(0, 3).map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => onSelectConversation(dataset.id, conv.id)}
                      className="w-full text-left p-4 hover:bg-slate-50 dark:hover:bg-dark-elevated transition-colors flex items-start gap-3"
                    >
                      <div className="mt-0.5 text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-dark-bg p-2 rounded-lg">
                        <MessageSquare size={16} />
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-slate-800 dark:text-slate-200 truncate">
                          {conv.title}
                        </div>
                        <div className="text-sm text-slate-600 dark:text-slate-400 flex gap-2">
                          <span>{conv.date}</span>
                          <span>&middot;</span>
                          <span>
                            {conv.messageCount} message{conv.messageCount === 1 ? '' : 's'}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                  {(!dataset.conversations || dataset.conversations.length === 0) && (
                    <div className="p-8 text-center text-slate-600 dark:text-slate-400">
                      No conversations yet. Start one to analyse this data.
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-5 shadow-sm">
                <h3 className="text-base font-semibold mb-4 text-slate-800 dark:text-slate-200">
                  Data Quality
                </h3>

                {isReportLoading || !report ? (
                  <div className="flex flex-col items-center p-4">
                    <Bar className="w-32 h-32 rounded-full mb-6" />
                    <Bar className="h-3 w-40 mb-2.5" />
                    <Bar className="h-3 w-36" />
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center p-4">
                    <QualityRing
                      score={score}
                      scoreText={report.qualityScore}
                      label={report.qualityLabel}
                      colorClass={scoreColor}
                      animationKey={datasetId}
                    />

                    <div className="w-full space-y-2 mt-2 text-sm">
                      <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                        <AlertCircle size={14} className="text-warning shrink-0" />
                        {report.excludedColumnCount} column
                        {report.excludedColumnCount === 1 ? '' : 's'} excluded
                      </div>
                      <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                        <CheckCircle2 size={14} className="text-success shrink-0" />
                        {report.convertedColumnCount} column
                        {report.convertedColumnCount === 1 ? '' : 's'} converted
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border p-5 shadow-sm">
                <h3 className="text-base font-semibold mb-4 text-slate-800 dark:text-slate-200">
                  Quick Actions
                </h3>
                <div className="space-y-3">
                  <button
                    onClick={() => onNewConversation(dataset.id)}
                    className="w-full py-2.5 px-4 bg-primary hover:brightness-110 text-slate-900 rounded-lg font-semibold transition-all shadow-sm"
                  >
                    Start new conversation
                  </button>
                  <button
                    onClick={() => setActiveTab('Data Preparation')}
                    className="w-full py-2.5 px-4 bg-white dark:bg-dark-bg border border-slate-200 dark:border-dark-border hover:bg-slate-50 dark:hover:bg-dark-elevated text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-colors"
                  >
                    View preprocessing report
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'Data Preparation' && (
          <div className="max-w-3xl mx-auto">
            <DataPreparation report={report} isLoading={isReportLoading} />
          </div>
        )}

        {activeTab === 'Columns & Types' && (
          <div className="max-w-5xl mx-auto">
            <ColumnsTable columns={columns} report={report} isLoading={!columns && !tabError} />
          </div>
        )}

        {activeTab === 'Preview' && (
          <div className="max-w-6xl mx-auto">
            <PreviewTable preview={preview} isLoading={!preview && !tabError} />
          </div>
        )}
      </div>
    </div>
  );
}
