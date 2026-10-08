import React from 'react';
import { AlertTriangle, FileText, UploadCloud, X } from 'lucide-react';

export default function DatasetRejected({ filename, fileSize, missingRate, onUploadAnother, onClose }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 h-full bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary relative">
      
      {onClose && (
        <button onClick={onClose} className="absolute top-6 right-6 p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors">
          <X size={24} />
        </button>
      )}

      <div className="max-w-md w-full bg-white dark:bg-dark-card rounded-2xl border border-slate-200 dark:border-dark-border shadow-lg overflow-hidden">
        
        <div className="p-8 flex flex-col items-center text-center border-b border-slate-100 dark:border-dark-border">
          <div className="w-16 h-16 bg-error/10 text-error rounded-full flex items-center justify-center mb-6">
            <AlertTriangle size={32} />
          </div>
          
          <h2 className="text-2xl font-bold text-error mb-3">This dataset can't be analyzed</h2>
          <p className="text-slate-600 dark:text-slate-400">
            The dataset contains too many missing values to provide reliable analysis.
          </p>
        </div>

        <div className="p-6 space-y-6">
          
          {/* File Info */}
          <div className="flex items-center gap-4 bg-slate-50 dark:bg-dark-bg border border-slate-200 dark:border-dark-border rounded-xl p-4">
            <div className="text-slate-400 dark:text-slate-500">
              <FileText size={24} />
            </div>
            <div className="flex-1 overflow-hidden">
              <div className="font-medium text-slate-800 dark:text-slate-200 truncate">{filename || 'problematic.csv'}</div>
              <div className="text-sm text-slate-500 mt-0.5">{fileSize || '28 KB'}</div>
            </div>
          </div>

          {/* Issue Details */}
          <div className="space-y-4">
            <div className="flex justify-between text-sm">
              <span className="font-medium text-slate-700 dark:text-slate-300">Missing values</span>
              <span className="font-bold text-error">{missingRate || '47.3%'}</span>
            </div>
            
            {/* Progress Bar */}
            <div className="h-3 w-full bg-slate-100 dark:bg-dark-bg rounded-full overflow-hidden relative">
              <div 
                className="absolute left-0 top-0 bottom-0 bg-error rounded-full" 
                style={{ width: missingRate || '47.3%' }}
              ></div>
              {/* Max allowed marker */}
              <div 
                className="absolute top-0 bottom-0 w-0.5 bg-slate-400 dark:bg-slate-500 z-10" 
                style={{ left: '40%' }}
              ></div>
            </div>
            
            <div className="flex justify-between text-xs text-slate-500">
              <span>0%</span>
              <span className="text-slate-400 ml-4 relative -left-4">Maximum allowed 40%</span>
              <span>100%</span>
            </div>
          </div>

          <div className="bg-error/5 border border-error/20 rounded-lg p-3 text-sm text-error/90 flex items-start gap-2">
            <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
            <p>Please upload a different file with better data quality.</p>
          </div>

        </div>

        <div className="p-6 bg-slate-50 dark:bg-dark-bg border-t border-slate-100 dark:border-dark-border flex justify-center">
          <button 
            onClick={onUploadAnother}
            className="flex items-center gap-2 px-6 py-2.5 bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border hover:bg-slate-50 dark:hover:bg-dark-elevated text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-colors shadow-sm"
          >
            <UploadCloud size={18} />
            Upload another file
          </button>
        </div>

      </div>
    </div>
  );
}
