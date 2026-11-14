import React, { useState, useRef } from 'react';
import { UploadCloud, ShieldCheck, Lock, BarChart2, AlertTriangle } from 'lucide-react';
import SampleDatasets from './SampleDatasets';
import Logo from './Logo';

// Matches the server's limit. Checking here too turns a 5 MB upload over a
// slow connection, answered with a 413, into an instant, specific message.
const MAX_BYTES = 5 * 1024 * 1024;

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

// The browser's type for a CSV is unreliable (Windows reports
// application/vnd.ms-excel), so the extension is what decides.
function rejectionReason(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    return `${file.name} is not a CSV file. Only .csv files can be analysed.`;
  }
  if (file.size > MAX_BYTES) {
    return `${file.name} is ${formatBytes(file.size)}. The limit is 5 MB.`;
  }
  if (file.size === 0) return `${file.name} is empty.`;
  return null;
}

export default function WelcomeScreen({ onFileUpload, isUploading }) {
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState(null);
  // dragenter/dragleave fire for every child element, so a plain boolean
  // flickers. Counting enters and leaves does not.
  const dragDepth = useRef(0);

  // Returns the upload's promise so a caller can keep a spinner up until it
  // finishes -- the sample list needs that.
  const accept = (file) => {
    if (!file) return undefined;
    const reason = rejectionReason(file);
    if (reason) {
      setLocalError(reason);
      return undefined;
    }
    setLocalError(null);
    return onFileUpload(file);
  };

  const onDrop = (event) => {
    event.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);
    if (isUploading) return;
    const file = event.dataTransfer?.files?.[0];
    if (event.dataTransfer?.files?.length > 1) {
      setLocalError('Please drop one file at a time.');
      return;
    }
    accept(file);
  };

  return (
    // `my-auto` rather than `justify-center`: centring a flex child taller
    // than its scroll container makes the TOP of it unreachable. Adding the
    // sample list pushed this page past the fold and the heading vanished.
    // Auto margins centre when there is room and collapse when there is not.
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary">
      <div className="min-h-full flex flex-col px-4 sm:px-6 py-8">
        <div className="max-w-2xl w-full mx-auto my-auto text-center space-y-6">
          <div className="space-y-4">
            <Logo size={56} className="mx-auto mb-4 text-slate-800 dark:text-slate-100" />
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
              Analyse your data with AI
            </h2>
            <p className="text-slate-600 dark:text-slate-400 max-w-lg mx-auto text-lg leading-relaxed">
              Upload a CSV file, ask questions in plain language, and get clear
              answers with charts and insights.
            </p>
          </div>

          <div className="max-w-xl mx-auto">
            <label
              onDragEnter={(event) => {
                event.preventDefault();
                dragDepth.current += 1;
                if (!isUploading) setIsDragging(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={(event) => {
                event.preventDefault();
                dragDepth.current -= 1;
                if (dragDepth.current <= 0) setIsDragging(false);
              }}
              onDrop={onDrop}
              className={`block relative border-2 border-dashed rounded-3xl p-8 md:p-10 transition-all cursor-pointer ${
                isDragging
                  ? 'border-primary bg-primary/10 dark:bg-primary/15 scale-[1.02]'
                  : isUploading
                    ? 'border-primary bg-primary/5 dark:bg-primary/10'
                    : 'border-slate-300 dark:border-dark-border bg-white dark:bg-dark-card hover:border-primary/50 hover:bg-slate-50 dark:hover:bg-dark-elevated shadow-sm'
              }`}
            >
              <input
                type="file"
                className="hidden"
                accept=".csv,text/csv"
                disabled={isUploading}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = ''; // so the same file re-triggers
                  accept(file);
                }}
              />

              <div className="flex flex-col items-center justify-center text-center space-y-4 pointer-events-none">
                <div className="p-4 bg-slate-100 dark:bg-dark-bg rounded-full">
                  <UploadCloud
                    size={32}
                    className={
                      isUploading
                        ? 'text-primary animate-bounce'
                        : isDragging
                          ? 'text-primary'
                          : 'text-slate-500 dark:text-slate-400'
                    }
                  />
                </div>
                <div>
                  <p className="text-lg font-semibold text-slate-700 dark:text-slate-200">
                    {isUploading
                      ? 'Uploading…'
                      : isDragging
                        ? 'Drop it to upload'
                        : 'Drag & drop your CSV file here'}
                  </p>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">or click to browse</p>
                </div>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-dark-bg px-3 py-1 rounded-full">
                  .csv files only &middot; up to 5 MB
                </p>
              </div>
            </label>

            {localError && (
              <div className="mt-4 flex items-start gap-2.5 text-sm text-left bg-rose-50 dark:bg-error/10 border border-rose-200 dark:border-error/30 rounded-lg p-3 text-slate-800 dark:text-slate-200">
                <AlertTriangle
                  size={16}
                  className="mt-0.5 shrink-0 text-rose-600 dark:text-error"
                />
                <span>{localError}</span>
              </div>
            )}

            <div className="mt-6">
              <SampleDatasets onFileUpload={accept} isUploading={isUploading} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-6 max-w-3xl mx-auto border-t border-slate-200 dark:border-dark-border">
            {[
              [Lock, 'No coding required', 'Just ask your question'],
              [BarChart2, 'Clear & visual results', 'Tables, charts and insights'],
              [ShieldCheck, 'Full transparency', 'See the analysis plan'],
            ].map(([Icon, title, subtitle]) => (
              <div key={title} className="flex flex-col items-center text-center space-y-1.5">
                <div className="text-slate-500 dark:text-slate-400">
                  <Icon size={20} />
                </div>
                <h3 className="font-semibold text-slate-700 dark:text-slate-300">{title}</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">{subtitle}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
