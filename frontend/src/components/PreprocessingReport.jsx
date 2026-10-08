import React from 'react';
import { ArrowLeft, CheckCircle2, AlertTriangle, AlertCircle, Info, Database } from 'lucide-react';

export default function PreprocessingReport({ dataset, onBack }) {
  if (!dataset) return null;

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 dark:bg-dark-bg text-slate-900 dark:text-dark-text-primary overflow-hidden">
      
      {/* Header */}
      <header className="bg-white dark:bg-dark-sidebar border-b border-slate-200 dark:border-dark-border px-6 py-6 flex-shrink-0">
        <button 
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 mb-6 transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </button>
        
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-2">Data Preparation Report</h2>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="font-medium text-slate-700 dark:text-slate-300">{dataset.name}</span>
          <span>•</span>
          <span>{dataset.rowCount?.toLocaleString()} rows</span>
          <span>•</span>
          <span>{dataset.colCount} columns</span>
        </div>

        <div className="flex items-center gap-4 mt-6">
          <div className="flex items-center gap-1.5 px-3 py-1 bg-success/10 text-success rounded-full text-sm font-medium">
            <CheckCircle2 size={16} />
            6 checks completed
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 bg-warning/10 text-warning rounded-full text-sm font-medium">
            <AlertTriangle size={16} />
            2 notices
          </div>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-4">
          
          <div className="bg-blue-50/50 dark:bg-primary/5 border border-blue-100 dark:border-primary/20 rounded-xl p-4 flex gap-3 text-sm mb-6">
            <Info size={20} className="text-blue-500 dark:text-primary flex-shrink-0" />
            <p className="text-blue-800 dark:text-blue-200 leading-relaxed">
              The original dataset is preserved. All changes are applied to a working copy for analysis, without modifying your file.
            </p>
          </div>

          <div className="space-y-4">
            
            {/* Validation */}
            <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-5 flex gap-4 shadow-sm">
              <div className="mt-0.5">
                <CheckCircle2 size={24} className="text-success" />
              </div>
              <div>
                <h4 className="font-bold text-slate-800 dark:text-slate-200 text-base">1. File validation</h4>
                <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">CSV file loaded successfully.</p>
              </div>
            </div>

            {/* Size */}
            <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-5 flex gap-4 shadow-sm">
              <div className="mt-0.5">
                <CheckCircle2 size={24} className="text-success" />
              </div>
              <div>
                <h4 className="font-bold text-slate-800 dark:text-slate-200 text-base">2. Dataset size</h4>
                <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">{dataset.rowCount?.toLocaleString()} rows • {dataset.colCount} columns</p>
              </div>
            </div>

            {/* Missing values */}
            <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-5 flex gap-4 shadow-sm">
              <div className="mt-0.5">
                <CheckCircle2 size={24} className="text-success" />
              </div>
              <div>
                <h4 className="font-bold text-slate-800 dark:text-slate-200 text-base">3. Missing values</h4>
                <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">Overall missing rate: 2.1% (within threshold).</p>
              </div>
            </div>

            {/* Excluded columns */}
            <div className="bg-white dark:bg-dark-card border border-warning/50 dark:border-warning/30 rounded-xl p-5 flex gap-4 shadow-sm relative overflow-hidden">
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-warning"></div>
              <div className="mt-0.5">
                <AlertCircle size={24} className="text-warning" />
              </div>
              <div>
                <h4 className="font-bold text-slate-800 dark:text-slate-200 text-base">4. Column excluded from analysis</h4>
                <div className="mt-2 space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-mono bg-slate-100 dark:bg-dark-bg px-2 py-0.5 rounded text-slate-700 dark:text-slate-300">customer_phone</span>
                    <span className="text-slate-500">(78.4% missing)</span>
                  </div>
                  <p className="text-slate-600 dark:text-slate-400">This column remains in the original dataset but will not be used for analysis.</p>
                </div>
              </div>
            </div>

            {/* Data type conversion */}
            <div className="bg-white dark:bg-dark-card border border-blue-100 dark:border-blue-900/30 rounded-xl p-5 flex gap-4 shadow-sm relative overflow-hidden">
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500"></div>
              <div className="mt-0.5">
                <Info size={24} className="text-blue-500" />
              </div>
              <div className="w-full">
                <h4 className="font-bold text-slate-800 dark:text-slate-200 text-base">5. Data type conversion</h4>
                <div className="mt-3 space-y-3 text-sm w-full max-w-lg">
                  
                  <div className="flex items-center justify-between border-b border-slate-100 dark:border-dark-border pb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-slate-700 dark:text-slate-300">order_date</span>
                      <span className="text-slate-400 text-xs">object &rarr; datetime</span>
                    </div>
                    <span className="text-success font-medium">99.7% converted</span>
                  </div>
                  
                  <div className="flex items-center justify-between pb-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-slate-700 dark:text-slate-300">quantity</span>
                      <span className="text-slate-400 text-xs">object &rarr; int64</span>
                    </div>
                    <span className="text-success font-medium">100% converted</span>
                  </div>

                </div>
              </div>
            </div>

            {/* Duplicate rows */}
            <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-xl p-5 flex gap-4 shadow-sm">
              <div className="mt-0.5">
                <CheckCircle2 size={24} className="text-success" />
              </div>
              <div>
                <h4 className="font-bold text-slate-800 dark:text-slate-200 text-base">6. Duplicate rows</h4>
                <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">0.4% detected (below threshold).</p>
              </div>
            </div>

          </div>
          
        </div>
      </div>
    </div>
  );
}
