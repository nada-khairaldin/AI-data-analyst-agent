import React, { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';
import DataPreparation from './DataPreparation';
import ColumnsTable from './ColumnsTable';
import PreviewTable from './PreviewTable';
import { Bar } from './Skeleton';
import QualityRing from './QualityRing';
import { api, ApiError } from '../api/client';

const TABS = ['Overview', 'Data preparation', 'Columns', 'Preview'];

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-2xl text-ink tabular">{value}</div>
      <div className="text-sm text-graphite mt-0.5">{label}</div>
    </div>
  );
}

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
    const wantsColumns = activeTab === 'Columns' && !columns;
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

  const conversations = dataset.conversations || [];
  const score = report ? parseFloat(report.qualityScore) : null;

  return (
    <div className="flex-1 flex flex-col h-full bg-paper text-ink overflow-hidden">
      <header className="border-b border-rule px-6 pt-4 shrink-0">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-graphite hover:text-ink"
        >
          <ArrowLeft size={15} strokeWidth={1.5} />
          All datasets
        </button>

        <h2 className="text-xl text-ink mt-3">{dataset.name}</h2>
        <p className="text-sm text-graphite mt-0.5 tabular">
          {dataset.rowCount?.toLocaleString()} rows · {dataset.colCount} columns · {dataset.size}
        </p>

        <div className="flex items-center gap-6 mt-5 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-2.5 text-sm whitespace-nowrap border-b-2 -mb-px ${
                activeTab === tab
                  ? 'text-ink border-verdigris'
                  : 'text-graphite border-transparent hover:text-ink'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        {tabError && activeTab !== 'Overview' && (
          <p className="max-w-6xl mx-auto mb-4 text-sm text-ink border-l-2 border-rule pl-3">
            {tabError}
          </p>
        )}

        {activeTab === 'Overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
            <div className="lg:col-span-2 flex flex-col gap-8">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                <Stat label="Rows" value={dataset.rowCount?.toLocaleString()} />
                <Stat label="Columns" value={dataset.colCount} />
                <Stat label="Missing values" value={dataset.missingRate} />
                <Stat label="Duplicate rows" value={dataset.duplicateRate} />
              </div>

              <div className="flex-1 min-h-0 flex flex-col border-t border-rule pt-4">
                <div className="shrink-0 flex items-baseline justify-between pb-3">
                  <h3 className="text-ink">All conversations</h3>
                  {conversations.length > 0 && (
                    <span className="text-sm text-graphite tabular">{conversations.length}</span>
                  )}
                </div>

                {/* The scroller is absolutely positioned on purpose.
                    overflow-y-auto does NOT constrain intrinsic sizing: a
                    growable flex item still reports its full content height,
                    so the grid row grew with the list instead of the list
                    scrolling. Out of flow, it contributes nothing, the row is
                    sized by the right column, and this box stretches to it. */}
                <div className="relative flex-1 min-h-48">
                  <div className="absolute inset-0 overflow-y-auto border-t border-rule">
                    {conversations.map((conv) => (
                      <button
                        key={conv.id}
                        onClick={() => onSelectConversation(dataset.id, conv.id)}
                        className="w-full text-left py-2.5 border-b border-rule hover:bg-surface"
                      >
                        <div className="text-ink truncate">{conv.title}</div>
                        <div className="text-sm text-graphite">
                          {conv.date} · {conv.messageCount} message
                          {conv.messageCount === 1 ? '' : 's'}
                        </div>
                      </button>
                    ))}
                    {conversations.length === 0 && (
                      <p className="py-6 text-sm text-graphite">
                        No conversations yet.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-8">
              <div>
                <h3 className="text-ink mb-3">Data quality</h3>

                {isReportLoading || !report ? (
                  <div className="flex flex-col items-center">
                    <Bar className="w-32 h-32 rounded-full mb-5" />
                    <Bar className="h-3 w-40 mb-2.5" />
                    <Bar className="h-3 w-36" />
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <QualityRing
                      score={score}
                      scoreText={report.qualityScore}
                      label={report.qualityLabel}
                      animationKey={datasetId}
                    />
                    <div className="w-full mt-4 text-sm text-graphite space-y-1">
                      <div>
                        {report.excludedColumnCount} column
                        {report.excludedColumnCount === 1 ? '' : 's'} excluded
                      </div>
                      <div>
                        {report.convertedColumnCount} column
                        {report.convertedColumnCount === 1 ? '' : 's'} converted
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-rule pt-4 space-y-2">
                <button
                  onClick={() => onNewConversation(dataset.id)}
                  className="w-full py-2.5 px-4 bg-verdigris text-paper rounded-md hover:brightness-110"
                >
                  Ask a question
                </button>
                <button
                  onClick={() => setActiveTab('Data preparation')}
                  className="w-full py-2.5 px-4 border border-rule rounded-md text-ink hover:border-graphite"
                >
                  See what was cleaned
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'Data preparation' && (
          <div className="max-w-3xl mx-auto">
            <DataPreparation report={report} isLoading={isReportLoading} />
          </div>
        )}

        {activeTab === 'Columns' && (
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
