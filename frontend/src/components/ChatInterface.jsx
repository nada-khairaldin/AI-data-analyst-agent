import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MessagesSkeleton } from './Skeleton';
import { Send, CheckCircle2, ChevronRight, BarChart2, AlertTriangle, Lightbulb } from 'lucide-react';
import ResultBlock from './ResultBlock';
import { api, ApiError } from '../api/client';
import { streamMessage } from '../api/stream';

// The real pipeline stages. `label` comes from the server so wording can
// change without a frontend deploy.
const STAGE_ORDER = ['condensing', 'planning', 'validating', 'executing', 'explaining'];

function StageList({ stages, current }) {
  return (
    <div className="flex flex-col gap-2">
      {stages.map(({ stage, label }) => {
        const done = STAGE_ORDER.indexOf(stage) < STAGE_ORDER.indexOf(current);
        return (
          <div key={stage} className="flex items-center gap-2">
            {done ? (
              <CheckCircle2 size={14} className="text-success" />
            ) : (
              <div className="w-3.5 h-3.5 rounded-full border-[1.5px] border-primary border-t-transparent animate-spin ml-0.5 mr-[1px]" />
            )}
            <span className={done ? 'text-slate-700 dark:text-slate-300' : 'text-primary font-medium'}>
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function AgentMessage({ message }) {
  const failed = message.status === 'failed';
  const advisory = message.status === 'needs_clarification' || message.status === 'cannot_answer';

  return (
    <div className="space-y-4">
      {/* "Understood as", only when the condenser actually resolved something */}
      {message.condensedQuestion && (
        <div className="flex items-start gap-2 text-xs text-slate-500 bg-slate-100 dark:bg-dark-elevated border border-slate-200 dark:border-dark-border rounded-lg px-3 py-2 max-w-2xl">
          <Lightbulb size={14} className="text-primary shrink-0 mt-0.5" />
          <span>
            <span className="font-medium">Understood as:</span> {message.condensedQuestion}
          </span>
        </div>
      )}

      <div
        className={`text-[15px] leading-relaxed whitespace-pre-wrap ${
          failed
            ? 'text-error'
            : advisory
              ? 'text-amber-600 dark:text-amber-400'
              : 'text-slate-800 dark:text-slate-200'
        }`}
      >
        {failed && <AlertTriangle size={16} className="inline mr-1.5 -mt-0.5" />}
        {message.content}
      </div>

      <ResultBlock
        resultData={message.resultData}
        resultKind={message.resultKind}
        chartPlan={message.chartPlan}
        chartTitle={message.chartTitle}
      />

      {message.plan && (
        <details className="group bg-slate-50 dark:bg-dark-elevated border border-slate-200 dark:border-dark-border rounded-lg overflow-hidden max-w-2xl">
          <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer select-none text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-dark-card transition-colors">
            <ChevronRight size={16} className="text-slate-400 group-open:rotate-90 transition-transform" />
            <span className="flex items-center gap-2">
              <BarChart2 size={16} className="text-primary" />
              Analysis performed
              <span className="text-slate-400 font-normal text-xs ml-1">(click to expand)</span>
            </span>
          </summary>
          <div className="px-5 py-4 border-t border-slate-200 dark:border-dark-border bg-white dark:bg-dark-card space-y-4 text-sm">
            <div>
              <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Question</h5>
              <p className="text-slate-600 dark:text-slate-400">{message.plan.question}</p>
            </div>
            <div>
              <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-2">Analysis Steps</h5>
              <ol className="list-decimal pl-5 space-y-1 text-slate-600 dark:text-slate-400">
                {message.plan.steps?.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Data Used</h5>
                <p className="text-slate-600 dark:text-slate-400">{message.plan.columnsUsed?.join(', ')}</p>
              </div>
              <div>
                <h5 className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Filters</h5>
                <p className="text-slate-600 dark:text-slate-400">{message.plan.filters || 'None'}</p>
              </div>
            </div>
            <div className="pt-2 flex items-center gap-1.5 text-success font-medium text-xs bg-success/10 w-fit px-2 py-1 rounded-full">
              <CheckCircle2 size={14} />
              Plan validated
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

export default function ChatInterface({ dataset, conversation, onTurnComplete }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [turnError, setTurnError] = useState(null);

  // The live turn.
  const [stages, setStages] = useState([]);
  const [stage, setStage] = useState(null);
  const [condensed, setCondensed] = useState(null);
  const [liveResult, setLiveResult] = useState(null);
  const [tokens, setTokens] = useState('');

  const endRef = useRef(null);
  const isStreaming = stage !== null;

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setTurnError(null);
    (async () => {
      try {
        const body = await api.getMessages(conversation.id);
        if (!cancelled) setMessages(body.messages);
      } catch (cause) {
        if (!cancelled) setTurnError(cause instanceof ApiError ? cause.message : String(cause));
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [conversation.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, tokens, stage, liveResult]);

  const resetTurn = useCallback(() => {
    setStages([]);
    setStage(null);
    setCondensed(null);
    setLiveResult(null);
    setTokens('');
  }, []);

  const handleSend = async (e) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || isStreaming) return;

    setInput('');
    setTurnError(null);
    resetTurn();
    // Optimistic, but the server is authoritative: the `done` event replaces
    // everything below with what was actually persisted.
    setMessages((prev) => [...prev, { role: 'user', content: question }]);

    try {
      await streamMessage(conversation.id, question, (event, data) => {
        if (event === 'status') {
          setStage(data.stage);
          setStages((prev) =>
            prev.some((s) => s.stage === data.stage) ? prev : [...prev, data],
          );
        } else if (event === 'condensed') {
          setCondensed(data.question);
        } else if (event === 'result') {
          setLiveResult(data);
        } else if (event === 'token') {
          setTokens((prev) => prev + data.text);
        } else if (event === 'done') {
          setMessages((prev) => {
            // Drop the optimistic user row and take the server's pair.
            const withoutOptimistic = prev.slice(0, -1);
            return [
              ...withoutOptimistic,
              { role: 'user', content: question },
              data.message,
            ];
          });
          resetTurn();
          onTurnComplete?.();
        } else if (event === 'error') {
          setTurnError(data.message || 'The analysis failed.');
          resetTurn();
          // The server persisted a `failed` agent message, so reload to show
          // it rather than leaving the question hanging.
          api.getMessages(conversation.id)
            .then((body) => setMessages(body.messages))
            .catch(() => {});
          onTurnComplete?.();
        }
      });
    } catch (cause) {
      // The stream never opened: a 4xx/5xx, or the network.
      setTurnError(cause instanceof ApiError ? cause.message : String(cause));
      resetTurn();
    }
  };

  if (!dataset || !conversation) return null;

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 dark:bg-dark-bg">
      <header className="bg-white/80 dark:bg-dark-sidebar/80 backdrop-blur-md border-b border-slate-200 dark:border-dark-border px-6 py-4 flex items-center shrink-0 min-h-[72px]">
        <h2 className="text-sm font-medium text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <span className="text-slate-500 font-normal">{dataset.name}</span>
          <span className="text-slate-400">/</span>
          {conversation.title}
        </h2>
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {isLoading && (
          <MessagesSkeleton />
        )}

        {!isLoading && messages.length === 0 && !isStreaming && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4">
            <div className="w-16 h-16 bg-blue-100 dark:bg-primary/10 rounded-2xl flex items-center justify-center text-primary mb-2">
              <BarChart2 size={32} />
            </div>
            <h3 className="text-lg font-medium text-slate-800 dark:text-slate-200">Start your analysis</h3>
            <div className="flex flex-wrap justify-center gap-2 max-w-md">
              {[
                'Which product has the highest total quantity sold?',
                'Now show it per month',
                'What is the average price?',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="px-3 py-1.5 bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-full text-sm hover:border-primary/50 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'agent' && (
              <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center shrink-0 mt-1">
                <BarChart2 size={16} />
              </div>
            )}
            <div
              className={
                msg.role === 'user'
                  ? 'max-w-[85%] bg-slate-200/50 dark:bg-white/10 text-slate-800 dark:text-white px-4 py-3 rounded-2xl rounded-tr-sm text-[15px]'
                  : 'max-w-[85%] min-w-0'
              }
            >
              {msg.role === 'user' ? msg.content : <AgentMessage message={msg} />}
            </div>
          </div>
        ))}

        {/* The live turn */}
        {isStreaming && (
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0 mt-1 border border-primary/30">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
            <div className="max-w-[85%] min-w-0 space-y-4">
              {condensed && (
                <div className="flex items-start gap-2 text-xs text-slate-500 bg-slate-100 dark:bg-dark-elevated border border-slate-200 dark:border-dark-border rounded-lg px-3 py-2">
                  <Lightbulb size={14} className="text-primary shrink-0 mt-0.5" />
                  <span><span className="font-medium">Understood as:</span> {condensed}</span>
                </div>
              )}

              <div className="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border px-4 py-3 rounded-2xl rounded-tl-sm text-sm shadow-sm min-w-[220px] w-fit">
                <StageList stages={stages} current={stage} />
              </div>

              {/* result arrives BEFORE the first token: the table is the
                  answer, the sentence is commentary */}
              {liveResult && (
                <ResultBlock
                  resultData={liveResult.resultData}
                  resultKind={liveResult.resultKind}
                  chartPlan={liveResult.chartPlan}
                />
              )}

              {tokens && (
                <div className="text-slate-800 dark:text-slate-200 text-[15px] leading-relaxed whitespace-pre-wrap">
                  {tokens}
                  <span className="inline-block w-1.5 h-4 bg-primary/70 ml-0.5 align-middle animate-pulse" />
                </div>
              )}
            </div>
          </div>
        )}

        {turnError && (
          <div className="flex items-start gap-2 text-sm bg-error/10 border border-error/30 rounded-lg px-4 py-3 text-slate-700 dark:text-slate-200">
            <AlertTriangle size={16} className="text-error shrink-0 mt-0.5" />
            <span>{turnError}</span>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="p-4 md:p-6 bg-white dark:bg-dark-sidebar border-t border-slate-200 dark:border-dark-border">
        <form onSubmit={handleSend} className="max-w-4xl mx-auto relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder={isStreaming ? 'Analysing…' : 'Ask a question about your data...'}
            className="w-full bg-slate-100 dark:bg-dark-bg border border-slate-200 dark:border-dark-border text-slate-800 dark:text-white rounded-full py-3.5 pl-6 pr-14 focus:outline-none focus:border-primary/50 transition-colors shadow-sm disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="absolute right-2 top-1.5 bottom-1.5 w-10 h-10 bg-primary hover:bg-primary/90 text-white rounded-full flex items-center justify-center transition-transform active:scale-95 disabled:opacity-50 disabled:active:scale-100"
          >
            <Send size={18} className="ml-1" />
          </button>
        </form>
      </div>
    </div>
  );
}
