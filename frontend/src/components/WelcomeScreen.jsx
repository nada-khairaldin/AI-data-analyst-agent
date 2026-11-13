import React, { useState, useRef } from 'react';
import { UploadCloud } from 'lucide-react';
import SampleDatasets from './SampleDatasets';

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
    <div className="flex-1 h-full overflow-y-auto bg-paper">
      <div className="min-h-full flex flex-col px-5 sm:px-6 py-10">
        <div className="max-w-xl w-full mx-auto my-auto">
          <h2 className="text-2xl text-ink">Upload a CSV</h2>
          <p className="text-graphite mt-1.5">
            Ask questions about it in plain language and get the figures back.
          </p>

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
            className={`mt-6 block border border-dashed rounded-md px-6 py-10 cursor-pointer text-center transition-colors ${
              isDragging
                ? 'border-verdigris bg-verdigris/5'
                : 'border-rule hover:border-graphite'
            }`}
          >
            <input
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

            <div className="pointer-events-none">
              <UploadCloud
                size={22}
                strokeWidth={1.5}
                className={`mx-auto mb-3 ${isDragging ? 'text-verdigris' : 'text-graphite'}`}
              />
              <div className="text-ink">
                {isUploading
                  ? 'Uploading'
                  : isDragging
                    ? 'Drop it to upload'
                    : 'Drop a file here, or click to choose one'}
              </div>
              <div className="text-sm text-graphite mt-1">CSV, up to 5 MB</div>
            </div>
          </label>

          {localError && (
            <p className="mt-3 text-sm text-ink border-l-2 border-rule pl-3">{localError}</p>
          )}

          <div className="mt-10">
            <SampleDatasets onFileUpload={accept} isUploading={isUploading} />
          </div>
        </div>
      </div>
    </div>
  );
}
