import React, { useState, useRef, useEffect, useCallback } from 'react';
import { MessagesSkeleton } from './Skeleton';
import { suggestQuestions } from '../lib/suggestions';
import { splitOnFigure } from '../lib/highlight';
import { Send, ChevronRight } from 'lucide-react';
import ResultBlock from './ResultBlock';
import { api, ApiError } from '../api/client';
import { streamMessage } from '../api/stream';

// The real pipeline stages. `label` comes from the server so wording can
// change without a frontend deploy.
const STAGE_ORDER = ['condensing', 'planning', 'validating', 'executing', 'explaining'];

// One thin line and the current stage, in place of a checklist of spinners.
// Progress is a fact the server already tells us; it does not need five rows
// of chrome to say it.
function StageLine({ stages, current }) {
  const label = stages.find((s) => s.stage === current)?.label ?? 'Working';
  const step = STAGE_ORDER.indexOf(current) + 1;
  const progress = step > 0 ? (step / STAGE_ORDER.length) * 100 : 8;

  return (
    <div className="max-w-md">
      <div className="h-px w-full bg-rule">
        <div
          className="h-px bg-verdigris transition-[width] duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mt-2 text-sm text-graphite">{label}</div>
    </div>
  );
}

// The one bold moment in the interface.
function Answer({ text, resultData, highlight }) {
  const split = highlight ? splitOnFigure(text, resultData) : null;

  return (
    <div className="text-[15px] leading-relaxed text-ink whitespace-pre-wrap">
      {split ? (
        <>
          {split.before}
          <mark className="marker">{split.figure}</mark>
          {split.after}
        </>
      ) : (
        text
      )}
    </div>
  );
}

function AgentMessage({ message }) {
  const failed = message.status === 'failed';
  const advisory =
    message.status === 'needs_clarification' || message.status === 'cannot_answer';

  return (
    <div className="space-y-4">
      {message.condensedQuestion && (
        <p className="text-sm text-graphite">
          Understood as: {message.condensedQuestion}
        </p>
      )}

      {failed || advisory ? (
        <div className="text-[15px] leading-relaxed whitespace-pre-wrap text-graphite border-l-2 border-rule pl-3">
          {message.content}
        </div>
      ) : (
        <Answer text={message.content} resultData={message.resultData} highlight />
      )}

      <ResultBlock
        resultData={message.resultData}
        resultKind={message.resultKind}
        chartPlan={message.chartPlan}
        chartTitle={message.chartTitle}
      />

      {message.plan && (
        <details className="group max-w-2xl border-t border-rule pt-3">
          <summary className="flex items-center gap-1.5 cursor-pointer select-none text-sm text-graphite hover:text-ink">
            <ChevronRight
              size={15}
              strokeWidth={1.5}
              className="group-open:rotate-90 transition-transform"
            />
            How this was worked out
          </summary>

          <div className="mt-3 pl-[22px] space-y-3 text-sm text-graphite">
            <div>
              <div className="text-ink">Question</div>
              <p>{message.plan.question}</p>
            </div>
            <div>
              <div className="text-ink">Steps</div>
              <ol className="list-decimal pl-5 space-y-0.5">
                {message.plan.steps?.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-ink">Columns used</div>
                <p>{message.plan.columnsUsed?.join(', ')}</p>
              </div>
              <div>
                <div className="text-ink">Filters</div>
                <p>{message.plan.filters || 'None'}</p>
              </div>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

export default function ChatInterface({ dataset, conversation, onTurnComplete }) {
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
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

  // Starter questions are built from this dataset's own columns, with fixed
  // templates and no LLM call: a suggestion has to be certain to run, and a
  // free-tier call spent before the user asks anything is one they cannot
  // spend on a real question. A failure here just leaves the chips off.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const body = await api.getColumns(dataset.id);
        if (!cancelled) setSuggestions(suggestQuestions(body.columns));
      } catch {
        if (!cancelled) setSuggestions([]);
      }
    })();
    return () => { cancelled = true; };
  }, [dataset.id]);

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
    <div className="flex-1 flex flex-col h-full bg-paper">
      <header className="border-b border-rule px-6 py-4 flex items-center shrink-0 min-h-[64px]">
        <h2 className="text-sm text-ink">
          <span className="text-graphite">{dataset.name}</span>
          <span className="text-graphite mx-2">/</span>
          {conversation.title}
        </h2>
      </header>

      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-6">
        <div className="max-w-3xl mx-auto space-y-8">
          {isLoading && <MessagesSkeleton />}

          {!isLoading && messages.length === 0 && !isStreaming && (
            <div className="py-8">
              <h3 className="text-lg text-ink">Ask a question about your data</h3>
              <p className="text-sm text-graphite mt-1">
                {dataset.rowCount?.toLocaleString()} rows, {dataset.colCount} columns.
              </p>
              {suggestions.length > 0 && (
                <ul className="mt-5 border-t border-rule">
                  {suggestions.map((suggestion) => (
                    <li key={suggestion} className="border-b border-rule">
                      <button
                        onClick={() => setInput(suggestion)}
                        className="w-full text-left py-2.5 text-[15px] text-ink hover:text-verdigris"
                      >
                        {suggestion}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {messages.map((msg, idx) =>
            msg.role === 'user' ? (
              <div key={idx} className="flex justify-end">
                <div className="max-w-[85%] bg-surface border border-rule rounded-md px-4 py-2.5 text-[15px] text-ink">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div key={idx} className="max-w-full min-w-0">
                <AgentMessage message={msg} />
              </div>
            ),
          )}

          {isStreaming && (
            <div className="space-y-4 min-w-0">
              {condensed && (
                <p className="text-sm text-graphite">Understood as: {condensed}</p>
              )}

              <StageLine stages={stages} current={stage} />

              {/* result arrives BEFORE the first token: the table is the
                  answer, the sentence is commentary */}
              {liveResult && (
                <ResultBlock
                  resultData={liveResult.resultData}
                  resultKind={liveResult.resultKind}
                  chartPlan={liveResult.chartPlan}
                />
              )}

              {/* No marker while streaming: the sweep belongs to the finished
                  reply, and a half-written sentence has no figure yet. */}
              {tokens && (
                <div className="text-[15px] leading-relaxed text-ink whitespace-pre-wrap">
                  {tokens}
                  <span className="inline-block w-[2px] h-4 bg-graphite ml-0.5 align-middle animate-pulse" />
                </div>
              )}
            </div>
          )}

          {turnError && (
            <p className="text-sm text-ink border-l-2 border-rule pl-3">{turnError}</p>
          )}

          <div ref={endRef} />
        </div>
      </div>

      <div className="border-t border-rule px-4 md:px-6 py-4">
        <form onSubmit={handleSend} className="max-w-3xl mx-auto flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder={isStreaming ? 'Analysing' : 'Ask a question about your data'}
            className="flex-1 bg-surface border border-rule rounded-md px-4 py-2.5 text-[15px] text-ink placeholder:text-graphite focus:border-verdigris focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            aria-label="Send"
            disabled={!input.trim() || isStreaming}
            className="shrink-0 w-10 h-10 bg-verdigris text-paper rounded-md flex items-center justify-center hover:brightness-110 disabled:opacity-40"
          >
            <Send size={17} strokeWidth={1.5} />
          </button>
        </form>
      </div>
    </div>
  );
}
