import React, { useState, useRef } from 'react';
import { UploadCloud } from 'lucide-react';
import SampleDatasets from './SampleDatasets';
import Logo from './Logo';
import ExampleAnswer from './ExampleAnswer';

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
  const inputRef = useRef(null);
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
    if (event.dataTransfer?.files?.length > 1) {
      setLocalError('Please drop one file at a time.');
      return;
    }
    accept(event.dataTransfer?.files?.[0]);
  };

  return (
    // `my-auto` rather than `justify-center`: centring a flex child taller
    // than its scroll container makes the TOP of it unreachable. Auto margins
    // centre when there is room and collapse when there is not.
    <div className="flex-1 h-full overflow-y-auto bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary">
      <div className="min-h-full flex flex-col px-4 sm:px-6 py-6">
        <div className="max-w-xl w-full mx-auto my-auto">
          <div className="flex items-center gap-3">
            <Logo size={40} variant="intro" className="shrink-0 text-slate-800 dark:text-slate-100" />
            <div className="min-w-0">
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                Ask your spreadsheet a question
              </h2>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Upload a CSV and get the answer as a table, a chart and a sentence.
              </p>
            </div>
          </div>

          {/* The drop target is a plain div and the picker is a real button.
              A <button> nested in the old <label> would have fired the label
              as well and opened the dialog twice; a bare label cannot take
              keyboard focus. This way both work. */}
          <div
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
            className={`mt-5 flex flex-col items-center justify-center gap-2.5 text-center border-2 border-dashed rounded-2xl px-5 py-6 min-h-[180px] transition-colors ${
              isDragging
                ? 'border-primary bg-primary/5 dark:bg-primary/10'
                : 'border-slate-300 dark:border-dark-border bg-white dark:bg-dark-card'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              className="sr-only"
              accept=".csv,text/csv"
              disabled={isUploading}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = ''; // so the same file re-triggers
                accept(file);
              }}
            />

            {isUploading ? (
              <Logo size={28} variant="loading" className="text-slate-700 dark:text-slate-200" />
            ) : (
              <UploadCloud
                size={26}
                className={isDragging ? 'text-primary' : 'text-slate-400 dark:text-slate-500'}
              />
            )}

            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
              {isUploading
                ? 'Uploading…'
                : isDragging
                  ? 'Drop it to upload'
                  : 'Drag a CSV here'}
            </p>

            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={isUploading}
              className="px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-white text-sm font-semibold shadow-sm transition-colors disabled:opacity-50"
            >
              Choose a CSV file
            </button>

            <p className="text-xs text-slate-500 dark:text-slate-500">.csv, up to 5 MB</p>
          </div>

          {localError && (
            <p className="mt-3 text-sm text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/30 rounded-lg px-3 py-2">
              {localError}
            </p>
          )}

          <div className="mt-5">
            <SampleDatasets onFileUpload={accept} isUploading={isUploading} />
          </div>

          <div className="mt-8 pt-6 border-t border-slate-200 dark:border-dark-border">
            <ExampleAnswer />
          </div>
        </div>
      </div>
    </div>
  );
}
