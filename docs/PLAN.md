# Implementation Plan — AI Data Analyst

Status: Task 0 output (discovery + plan). **No code has been written or
changed.** Companion document: [`API_CONTRACT.md`](./API_CONTRACT.md).

Revision 2 — all open questions are resolved (see
[§11 Decisions](#11-decisions-resolved)). Two requirements were added after
revision 1: a **question-condensation step** before the planner (§6) and
**real SSE streaming** of the answer (§6B).

Revision 3 — **Q2 changed: dataset storage moved from `bytea` in Postgres to
Neon Object Storage** (S3-compatible, Beta; private bucket `dataset`). Affects
§2, §3, §4 `dataset_files`, §7, §8 (region is now constrained), §9 features
0.5-2, and §10 risks 19-24. Written while implementing Phase A.

Revision 5 — **A9: surviving the free tier.** One planner call per question
instead of two (JSON mode plus a deterministic fence strip), model **fallback
chains** so the per-model daily quota multiplies, a development response
cache, and dirtier samples. Net effect: ~10 usable questions a day became
~40. Affects §7, §10 risks 2 and 3b, and `samples/`.

Revision 4 — **Q5 changed: the LLM provider is now Google Gemini**, via
`langchain-google-genai`, with **two models** (`gemini-3.6-flash` to plan,
`gemini-3.5-flash-lite` for everything else). The Hugging Face account had no
inference credits, so nothing could be verified there at all. Affects §2, §6,
§7 and §10 risks 1-3b. Streaming is now **confirmed working**, which closes the
one assumption §6B depended on. The new headline constraint is the free tier's
**20 requests per day per model** — see risk 2, because it changes what a demo
can be. §1 is left as the original audit of the starting codebase and is
deliberately not rewritten.

---

## 1. Current state

### Frontend — `frontend/`

| | |
|---|---|
| Framework | React **19.2** |
| Build tool | **Vite 8.3** (`vite.config.js`, plugins: `@vitejs/plugin-react`, `@tailwindcss/vite`) |
| Language | **JavaScript + JSX** — no TypeScript, despite `@types/react` being installed |
| Styling | **Tailwind CSS 4** via the Vite plugin, with a custom `@theme` palette in `src/index.css` and a class-based dark variant (`@variant dark (&:where(.dark, .dark *))`) |
| State | **`useState` in `App.jsx` only.** No Redux/Zustand/Context, no React Router, no React Query |
| HTTP client | **None.** No `axios`, no `fetch` call anywhere in `src/` |
| Charts | **Recharts 3.10** (only `BarChart` is used) |
| Icons | `lucide-react` |
| Lint | `oxlint` |

Routing is a single `currentView` string in `App.jsx:79` with five values:
`welcome`, `overview`, `chat`, `report`, `rejected`. There are no URLs, so
nothing is deep-linkable or refresh-safe.

**Screens**

1. **`WelcomeScreen.jsx`** — hero + CSV drop zone (`accept=".csv"`, single
   file) + three feature blurbs. Calls `onFileUpload`.
2. **`Sidebar.jsx`** — logo, "Upload dataset" button, a **non-functional**
   search input (no `value`/`onChange`), an expandable dataset tree with nested
   conversations, "New conversation" per dataset, and a footer hardcoding
   `U` / `"User Name"` / `"user@example.com"` plus a dead Settings button.
3. **`DatasetOverview.jsx`** — header with name/rows/cols/size, a hardcoded
   "Ready for analysis" badge, a dead `MoreHorizontal` button, and **five tabs**
   of which only `Overview` is implemented; `Data Preparation`,
   `Columns & Types`, `Preview` and `Conversations` all render
   `"{activeTab} content will be displayed here."` (lines 194-198). The Overview
   tab holds a Dataset Summary card, a Recent Conversations list, a Data Quality
   card (hardcoded `97.9%` / `Good` / `1 column excluded` /
   `2 columns converted`) and Quick Actions.
4. **`ChatInterface.jsx`** — message list, empty-state with three canned
   suggestion chips, an agent result card (table + bar chart), an expandable
   "Analysis performed" `<details>` panel, a fake three-step progress indicator,
   and the question input.
5. **`PreprocessingReport.jsx`** — six numbered data-preparation checks.
   **Every value is a literal in the JSX**; only `name`, `rowCount` and
   `colCount` come from props.
6. **`DatasetRejected.jsx`** — rejection card with a missing-values bar and a
   40 % threshold marker. Accepts `filename`, `fileSize`, `missingRate` props
   that `App.jsx` **never passes**, so it always shows its fallbacks
   (`problematic.csv`, `28 KB`, `47.3%`).

**All mock data and its users**

| Mock | Defined at | Used by |
|---|---|---|
| `MOCK_DATASETS` (3 datasets, 3 conversations, 1 full message) | `src/App.jsx:11-73` | `useState` initial value, `App.jsx:76` → `Sidebar`, `DatasetOverview`, `ChatInterface`, `PreprocessingReport` |
| Fake upload: 1.5 s `setTimeout`, `Math.random()` row/col counts, filename-based rejection (`includes('problem') \|\| includes('bad')`) | `src/App.jsx:98-127` | `WelcomeScreen` → `DatasetOverview` / `DatasetRejected` |
| Fake conversation creation (`'conv_' + Date.now()`, `date: 'Just now'`) | `src/App.jsx:143-158` | `Sidebar`, `DatasetOverview` |
| Fake agent reply: 2 s `setTimeout` → `"I've analyzed the data for your request."` | `src/App.jsx:180-200` | `ChatInterface` |
| Fake analysis progress: 2 s `setTimeout` toggling `isAnalyzing` | `src/components/ChatInterface.jsx:28-33` | its own spinner block (lines 184-204) |
| Hardcoded table headers `Product` / `Total Quantity Sold`, row keys `row.product` / `row.quantity`, `dataKey="product"` / `dataKey="quantity"`, chart title | `src/components/ChatInterface.jsx:96-128` | the agent result card |
| Hardcoded quality score `97.9%`, `1 column excluded`, `2 columns converted`, `dataset.size \|\| '45 KB'`, `missingRate \|\| '2.1%'`, `duplicateRate \|\| '0.4%'`, `conv.date \|\| '2 hours ago'`, `conv.messageCount \|\| 12` | `src/components/DatasetOverview.jsx:39-166` | Overview tab |
| Entire report body: `customer_phone 78.4%`, `order_date object → datetime 99.7%`, `quantity object → int64 100%`, `2.1%`, `0.4%`, `6 checks`, `2 notices` | `src/components/PreprocessingReport.jsx:32-143` | report view |
| Rejection fallbacks `problematic.csv` / `28 KB` / `47.3%` | `src/components/DatasetRejected.jsx:35-51` | rejected view |
| Sidebar user `U` / `User Name` / `user@example.com` | `src/components/Sidebar.jsx:150-156` | sidebar footer |

The API call each mock implies is mapped endpoint-by-endpoint in
[`API_CONTRACT.md`](./API_CONTRACT.md#endpoint--frontend-map).

**Does the UI expect streaming / charts / tables / file upload?**

- **Streaming: not today.** The three-step progress block is static JSX gated on
  a boolean that a `setTimeout` flips. There is no `EventSource`, no
  `ReadableStream`, no `text/event-stream` anywhere. **This is now a
  requirement** (§6B) — the fake progress is replaced by real `status` events,
  and the answer text types in as it is generated.
- **Charts: yes, but only one kind.** Recharts `BarChart`, horizontal layout,
  with `dataKey` hardcoded to `product`/`quantity`. The backend's agent can
  request `bar`, `line`, `pie` or `scatter`
  (`backend/agent/schemas.py:93-98`) — three of the four have no renderer.
- **Tables: yes**, with hardcoded two-column headers.
- **File upload: yes** — single CSV, `<input type="file" accept=".csv">`. There
  is no real drag-and-drop handler (no `onDrop`/`onDragOver`); the dashed border
  is a styled `<label>`, so "Drag & drop your CSV file here" works only because
  browsers handle drops onto file inputs natively.

### AI backend — `backend/`

**It is not just agent logic: a partial FastAPI app already exists.** This
materially changes the roadmap (see §9).

| | |
|---|---|
| Language | Python (`.pyc` files are `cpython-314`, so Python 3.14) |
| Framework | **FastAPI already present** in `backend/main.py` (143 lines) |
| Run today | `cd backend && uvicorn main:app --reload` — imports are flat (`from validation import ...`, `from tools import ...`), so it only runs with `backend/` as the working directory |
| LLM provider | **Google Gemini** via `langchain-google-genai` (`ChatGoogleGenerativeAI`), two models: `gemini-3.8-flash` for the planner and `gemini-3.5-flash-lite` for everything else. Replaced the Hugging Face router in A8, whose account had no inference credits. Only `app/agent/llm.py` talks to a provider |
| Model | `"Qwen/Qwen3.8-Flash-Next:featherless-ai"`, hardcoded twice (`agent/core.py:49`, `agent/explainer.py:82`) |
| Declared deps | `backend/requirements.txt`: `fastapi`, `uvicorn`, `python-multipart`, `pandas` |
| Actual deps | also `openai` and `python-dotenv` (imported in `agent/core.py` and `agent/explainer.py`) — **`requirements.txt` is incomplete and a fresh install will crash on import** |
| Conversation history | **No.** `sessions[sid]["history"]` is appended to (`main.py:85`) and never read. Nothing is ever sent back to the LLM |
| LangChain | **Not used, not installed.** The only matches in the repo are inside `.venv/.../streamlit/` |

**Structure and entry points**

```
backend/
├── main.py            FastAPI app: POST /api/upload, POST /api/analyze, GET /
├── validation.py      CSV load, quality thresholds, type normalisation (385 l)
├── data_utils.py      get_schema(df) -> {column: dtype_string}  (6 l)
├── tools.py           the 5 whitelisted pandas ops + execute_plan()
├── charting.py        chart validators — DEAD CODE, nothing imports it
├── agent/
│   ├── core.py        build prompt -> call LLM -> validate -> retry once
│   ├── prompts.py     the planner prompt (and a retry prompt)
│   ├── explainer.py   second LLM call that turns the result into a sentence
│   ├── schemas.py     STATUSES, TOOL_SCHEMAS, chart types
│   ├── state.py       create_agent_state(question, schema, unavailable_columns)
│   └── validators.py  strict validation of the model's JSON (376 l)
├── data/              empty
└── tests/             empty — there are no tests
```

**Input and output, from the code**

Input to the agent is a plain dict (`agent/state.py:9-22`):

```python
{"question": "...", "schema": {"Product": "object", "Quantity": "int64"},
 "unavailable_columns": {}, "status": "pending", "analysis_plan": [], ...}
```

The LLM is asked for **JSON only** — no function calling, no `response_format`
(`agent/prompts.py`). The expected shape, from the prompt's own example at
`agent/prompts.py:93-112`:

```json
{
  "status": "ready",
  "message": null,
  "analysis_plan": [
    { "tool": "aggregate_data", "column": "Quantity", "operation": "mean", "group_by": "Product" }
  ],
  "chart_plan": { "should_plot": true, "chart_type": "bar", "x": "Product", "y": "Quantity" }
}
```

`validators.py` then rejects the output unless: `status` is one of
`ready` / `needs_clarification` / `cannot_answer`; every `tool` is in the
whitelist; every required parameter is present with the right type; every
referenced column exists in the schema; the dataframe→scalar type flow between
steps is consistent (`validate_plan_types`, lines 252-269); and the chart's
`x`/`y` exist in the *predicted* final result (`get_final_result_columns`, lines
272-292). On failure it retries **once** with the error appended
(`core.py:73`, `max_attempts=2`).

`execute_plan` (`tools.py:95-114`) then runs the plan with exactly five
whitelisted pandas functions — `filter_data`, `aggregate_data`, `sort_data`,
`select_columns`, `limit_results`. **No AI-generated Python is ever executed**,
which is the project's core safety property and worth preserving.

A second LLM call (`agent/explainer.py`) converts the verified result into a
1-3 sentence summary, returned as `{"summary": "..."}`.

`POST /api/analyze` finally returns (`main.py:87-93`):

```json
{
  "status": "success",
  "answer": "Laptop has the highest total quantity sold, at 1,248 units.",
  "analysis_plan": [ { "tool": "aggregate_data", "...": "..." } ],
  "chart_plan": { "should_plot": true, "chart_type": "bar", "x": "Product", "y": "Quantity" },
  "result_data": [ { "Product": "Laptop", "Quantity": 1248 } ]
}
```

**Where the data comes from:** uploaded CSVs only, held as pandas DataFrames in
a module-level dict, `sessions: Dict[str, Any]` (`main.py:102`), keyed by a
UUID. The code's own comment admits the problem: *"In a real app, you'd use a
database and cloud storage (S3)."* Nothing is persisted; a restart or a second
worker process loses every dataset. `backend/data/` is empty — there are no
fixed data files.

**How finished it is**

*Works:* CSV load and structural validation; quality thresholds; type
normalisation; the whitelisted tool registry and `execute_plan`; the planner
prompt and its strict validator with a retry; the explainer; two working HTTP
endpoints; CORS for the Vite dev server.

*Missing:* persistence of any kind; conversation history (collected, never
used); chart validation is written but never called; auth; tests; the dataset
preview and column-report endpoints the UI's tabs need; proper HTTP status
codes; `requirements.txt` entries for `openai` and `python-dotenv`.

*Experimental or broken:*
- **`charting.py` is dead code.** Nothing imports it, so a chart plan that
  passed the *predictive* check in `validators.py` is never checked against the
  *actual* result. An invalid chart can reach the browser. → fixed in feature 4.
- **`/api/analyze` can return `null`.** The `if/elif` chain (`main.py:52-93`)
  has no `else`; a `pending` or `completed` status falls through and the
  function returns `None`, which FastAPI serialises as `null`. → fixed in
  feature 1.
- Imports and the `sessions` dict are declared **halfway down** `main.py`
  (lines 95-102), after the endpoint that uses them.
- `import math` (`main.py:72`) is unused.
- `unavailable_columns` is always passed as `{}` (`main.py:47`) because the
  columns were already dropped at upload. The agent therefore cannot say *"that
  column was excluded for quality reasons"* — it can only say *"unknown
  column"*. The feature exists on both sides but the wire between them is cut.
  → fixed in feature 4.
- `overall_missing_ratio = df.isna().mean().mean()` (`validation.py:74`) is the
  mean of per-column means, not the true fraction of missing cells. With
  columns of differing length-weighting these differ; it is the number shown to
  the user as the rejection reason.
- The per-column missing warnings (`validation.py:94-98`) never name the
  column, so the warning list reads `"78.4% of values are missing"` with no
  subject. `unavailable_columns` does carry the name, so the report should be
  built from that dict.
- A legacy Streamlit UI (`backend/app.py`, `backend/ui.py`, ~1000 lines) was
  deleted in commit `4886fd4`, but `streamlit`, `altair` and `pydeck` are still
  installed in `.venv`, and stale root-level `__pycache__/*.pyc` (including
  `ui.cpython-314.pyc`) are **committed to git**. → fixed in feature 0.5.

**Environment variables (names only)**

Currently needed: `HUGGINGFACE_API_KEY` — the single entry in `.env`, read in
`agent/core.py:23` and `agent/explainer.py:13`. Note the file has a space before
the `=`, which `python-dotenv` tolerates but many tools do not. The full target
list is in §7.

---

## 2. Target architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  BROWSER                                                                 │
│  React 19 + Vite + Tailwind 4   (static build, Vercel)                   │
│  src/api/client.js  ── the only place that knows the backend URL         │
│  src/api/stream.js  ── fetch + ReadableStream SSE parser (no components) │
│  src/api/session.js ── crypto.randomUUID() in localStorage              │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  HTTPS, header: X-Session-Id
                                │  JSON  ·  multipart (upload)
                                │  text/event-stream (chat)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FastAPI  (one Render Web Service, Uvicorn)                              │
│                                                                          │
│   api/routers/        thin HTTP layer — validate, call a service, return │
│        health   datasets   conversations   messages   messages/stream    │
│   services/           business logic, the only layer that orchestrates   │
│        ├── dataset_service       upload → validate → persist             │
│        ├── conversation_service  window, summary, condensation input     │
│        ├── condenser             follow-up  →  standalone question       │
│        ├── summarizer            rolling fact sheet (runs after `done`)  │
│        └── analysis_service      ASYNC GENERATOR of turn events          │
│   agent/              ◀── the EXISTING AI code, imported as a module     │
│        planner (core.py) · explainer.py · validators.py (UNTOUCHED)      │
│        tools.py · charting.py (finally wired in) · llm.py (new)          │
│   db/                 SQLAlchemy 2.0 models + session, Alembic migrations│
└───────┬────────────────────────────────┬─────────────────────────────────┘
        │                                │
        │ asyncpg over TLS               │  HTTPS (LangChain chat model)
        ▼                                ▼
┌───────────────────────┐      ┌──────────────────────────────────────────┐
│  NEON (PostgreSQL)    │      │  LLM provider (free tier — every call    │
│  same region as Render│      │  counts; base URL + model from env)      │
│                       │      │                                          │
│  sessions   users     │      │  call 1  condenser  → standalone question│
│  datasets             │      │  call 2  planner    → analysis JSON      │
│  dataset_columns      │      │  call 3  explainer  → plain text, STREAMED│
│  dataset_files ◀──────┼──┐   │  call 4  summarizer → fact sheet         │
│  preprocessing_reports│  │   │          (after `done`, every 2 exchanges)│
│  conversations        │  │   └──────────────────────────────────────────┘
│  messages             │  │
│  conversation_summaries  │  dataset_files holds only the OBJECT KEY
└───────────────────────┘  │
                           ▼
              ┌──────────────────────────────────────────────┐
              │  NEON OBJECT STORAGE (S3-compatible, Beta)   │
              │  private bucket "dataset", main branch       │
              │  datasets/{dataset_id}.parquet               │
              │  boto3: endpoint_url + path-style + SigV4    │
              │  reached ONLY via dataframe_store.py         │
              │  (≤5 MB CSV in, LRU cache of 3 frames)       │
              └──────────────────────────────────────────────┘
```

### One chat turn

`analysis_service.run_turn()` is an **async generator that yields events**.
Both chat endpoints consume the same generator — the JSON endpoint drains it
and returns only the final message, the SSE endpoint forwards every event. This
is why streaming is not a later rewrite (§9, feature 4).

```
POST /api/conversations/{id}/messages/stream   { "content": "now show it per month" }
  │
  ├─ 0  persist the USER message (before any event is emitted)
  ├─ 1  load dataset + schema + excluded columns   → datasets, dataset_columns
  │                                                  dataset_files (LRU cache)
  ├─ 2  load the window (last 3 exchanges) + fact sheet
  │                                   → messages, conversation_summaries
  ├─ 3  CONDENSE  ───────────────────────────── yield status{condensing}
  │     "now show it per month"
  │       → "Show total quantity per product per month for 2024"
  │     skipped entirely when there is no history
  │                                             yield condensed{question}
  ├─ 4  PLAN      ───────────────────────────── yield status{planning}
  │     the planner receives ONE string, exactly as today
  ├─ 5  VALIDATE  ───────────────────────────── yield status{validating}
  │     agent/validators.py, unchanged; retry once
  ├─ 6  EXECUTE   ───────────────────────────── yield status{executing}
  │     execute_plan() — whitelisted pandas only, in the threadpool
  ├─ 7  validate the chart against the REAL result (charting.py)
  │                                             yield result{resultData, …}
  ├─ 8  EXPLAIN   ───────────────────────────── yield status{explaining}
  │     plain-text answer, token by token       yield token{text} × N
  ├─ 9  persist the AGENT message (once)        yield done{message}
  └─10  AFTER done: refresh the fact sheet if 2 exchanges have left the window
```

Steps 4-7 are blocking (network + pandas) and run via
`starlette.concurrency.run_in_threadpool`. Step 8 is an async LangChain
`astream`. Step 10 runs in a background task, so the user never waits for it.

---

## 3. Proposed backend folder structure

```
backend/
├── app/
│   ├── main.py                 create_app(), CORS, exception handlers, routers
│   ├── config.py               pydantic-settings Settings — the ONLY os.getenv
│   ├── deps.py                 get_db, get_session (X-Session-Id)
│   │
│   ├── api/
│   │   ├── errors.py           the error envelope + exception handlers
│   │   ├── sse.py              event → SSE wire format, heartbeats, headers
│   │   └── routers/
│   │       ├── health.py       GET /health
│   │       ├── datasets.py     endpoints 2-8, 13
│   │       └── conversations.py endpoints 9-12, 14 + the two chat endpoints
│   │
│   ├── schemas/                Pydantic request/response models (camelCase)
│   │   ├── dataset.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   └── events.py           NEW: the 6 SSE event payloads, one model each
│   │
│   ├── services/
│   │   ├── dataset_service.py      upload → validate → persist → report
│   │   ├── dataframe_store.py      Parquet ⇄ Neon Object Storage + LRU(3)
│   │   │                           the ONLY module that touches boto3
│   │   ├── conversation_service.py window, fact sheet, digest building
│   │   ├── condenser.py            NEW: follow-up → standalone question
│   │   ├── summarizer.py           NEW: incremental rolling fact sheet
│   │   ├── analysis_service.py     NEW: the async event generator (§2)
│   │   └── presenters.py           analysis_plan → English; rates → "2.1%"
│   │
│   ├── agent/                  ◀── MOVED, not rewritten
│   │   ├── core.py             planner (LLM call swapped for the LangChain model)
│   │   ├── prompts.py          unchanged — the planner still gets ONE string
│   │   ├── explainer.py        prompt changed to PLAIN TEXT so it can stream
│   │   ├── schemas.py
│   │   ├── state.py
│   │   ├── validators.py       UNTOUCHED
│   │   ├── tools.py            ← from backend/tools.py
│   │   ├── charting.py         ← from backend/charting.py, finally called
│   │   └── llm.py              NEW: builds the LangChain chat model once
│   │
│   ├── prompts/                NEW: the two prompts that are not the planner's
│   │   ├── condenser.txt
│   │   └── summarizer.txt
│   │
│   ├── data/
│   │   ├── validation.py       ← from backend/validation.py, unchanged
│   │   └── data_utils.py       ← from backend/data_utils.py, unchanged
│   │
│   └── db/
│       ├── session.py          async engine + sessionmaker
│       ├── base.py             DeclarativeBase
│       └── models/             one file per table
│
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── tests/
│   ├── conftest.py
│   ├── test_validation.py      pure, no LLM, no DB — write these first
│   ├── test_tools.py           pure
│   ├── test_validators.py      pure
│   ├── test_condenser.py       the 3 conversations of §6, with a stubbed model
│   ├── test_stream.py          the event sequence, with a stubbed model
│   └── test_api_*.py           httpx.AsyncClient against a Neon test branch
├── pyproject.toml              deps + ruff + pytest config
├── requirements.txt            generated/pinned for Render
└── .env.example                names only, never values
```

Frontend additions (feature 6):

```
frontend/src/api/
├── client.js      fetch wrapper: base URL, X-Session-Id, error envelope, timeout
├── session.js     crypto.randomUUID() → localStorage, one key
└── stream.js      POST + ReadableStream → an async iterator of parsed events
```

**Reasoning.** The `app/` package fixes the flat-import problem — today
`main.py` only runs if the working directory is `backend/`, which breaks
Render's default start command. Routers stay thin so endpoints are testable
without HTTP. `services/` exists because the chat turn is ten steps long; put
that in a route handler and it can never be unit-tested. `analysis_service.py`
is a generator so the two endpoints cannot drift apart. `presenters.py` is
separate because the contract requires pre-formatted strings (`"2.1%"`,
`"45 KB"`, English plan steps) — isolating that makes Suggested change S1 a
one-file deletion later. The two new prompts live in `prompts/*.txt`, not in
Python string literals, because they will be tuned often and a prompt diff
should be readable. `src/api/stream.js` keeps SSE parsing out of components, as
you asked.

---

## 4. Database schema

Postgres on Neon. UUID primary keys (`gen_random_uuid()` from the built-in
`pgcrypto`) because ids are exposed in URLs and sequential integers leak volume
and allow enumeration. `timestamptz` everywhere, never naive timestamps.

### Ownership model: anonymous sessions, upgradeable to accounts

Decision Q1(d). The requirement is *"link to a real user account later without
rewriting tables"*, so ownership hangs off **`sessions`**, and the upgrade path
is a single column on that one table.

```sql
-- sessions: created on first request, id supplied by the browser
id            uuid        primary key          -- crypto.randomUUID() from the client
user_id       uuid        null references users(id) on delete set null
created_at    timestamptz not null default now()
last_seen_at  timestamptz not null default now()
dataset_count integer     not null default 0   -- enforces the cap of 20

index (user_id) where user_id is not null
```

```sql
-- users: created EMPTY in migration 1, so the FK above exists from day one
id            uuid        primary key default gen_random_uuid()
email         text        not null unique
name          text        not null
created_at    timestamptz not null default now()
```

**Why this shape.** `datasets` and `conversations` carry `session_id`, never
`user_id`. Signing up later is one statement —
`UPDATE sessions SET user_id = :new_user WHERE id = :session` — and every
dataset and conversation is claimed with it. No backfill, no new column on the
big tables, no rewrite. "All of my data" becomes
`WHERE session_id IN (SELECT id FROM sessions WHERE user_id = :me)`, and a
person who signs up from two browsers gets both sessions' data by linking both.
Putting `user_id` directly on `datasets` instead would mean a nullable column
with two meanings and a backfill over live rows at signup — exactly what you
asked to avoid.

**The honest security note.** The session id is generated by the browser and
sent in `X-Session-Id`. It is a bearer capability: anyone who learns the id
reads that session's data. `crypto.randomUUID()` gives 122 bits of entropy, so
guessing is not the risk — leaking is (a screenshot of devtools, a shared
machine). This is acceptable for anonymous datasets you upload yourself and is
**not** acceptable once real accounts exist; at that point the header is
replaced by a signed token and `sessions.id` becomes server-issued. Two things
follow for the UI (feature 6): clearing browser storage **permanently** orphans
every dataset with no recovery path, so say so next to the upload box; and the
server must reject a malformed id rather than create a row for it.

### `datasets`

```sql
id                uuid        pk
session_id        uuid        not null references sessions(id) on delete cascade
name              text        not null   -- original filename, e.g. "orders.csv"
status            text        not null default 'ready'  -- ready|processing|failed
row_count         integer     not null
column_count      integer     not null
size_bytes        bigint      not null
missing_rate      numeric(6,5) not null  -- 0.02100
duplicate_rate    numeric(6,5) not null
quality_score     numeric(6,5) not null
created_at        timestamptz not null default now()
updated_at        timestamptz not null default now()

index (session_id, created_at desc)
check (status in ('ready','processing','failed'))
check (row_count <= 100000)
```

*Why:* every field is read by the UI — `name`, `row_count`, `column_count`,
`size_bytes`, `missing_rate`, `duplicate_rate` by the sidebar, overview header
and summary card; `quality_score` by the Data Quality card; `status` by the
"Ready for analysis" badge. Rates are stored as **numbers** and formatted by
`presenters.py`; storing `"2.1%"` would make them unsortable and unusable for
thresholds. The index serves the sidebar's one query. The `row_count` check
mirrors `MAX_DATASET_ROWS` so a config mistake cannot put an unservable dataset
in the database. The 20-dataset cap is enforced in `dataset_service` against
`sessions.dataset_count`, maintained in the same transaction as the insert.

### `dataset_columns`

```sql
id                      uuid    pk
dataset_id              uuid    not null references datasets(id) on delete cascade
name                    text    not null
position                integer not null          -- original CSV column order
dtype                   text    not null          -- post-normalisation, e.g. "int64"
original_dtype          text    null              -- e.g. "object"
converted_to            text    null              -- "numeric" | "datetime" | null
conversion_success_rate numeric(6,5) null
missing_ratio           numeric(6,5) not null
is_available            boolean not null default true
exclusion_reason        text    null

unique (dataset_id, name)
index (dataset_id, position)
```

*Why:* this is the agent's `schema` dict, the "Columns & Types" tab, and the
conversion/exclusion sections of the report, all from one table. `position`
exists because JSON object key order must not drive table headers.
`is_available` + `exclusion_reason` **fix a real bug**: today excluded columns
are dropped and `unavailable_columns={}` is passed to the agent
(`main.py:47`), so the agent cannot explain *why* a column is unusable. With
this table both the planner and the condenser get the real dict.

### `dataset_files`

**Revised — decision Q2 changed to Neon Object Storage.** The table stores a
*pointer*, not the bytes.

```sql
dataset_id  uuid        pk references datasets(id) on delete cascade
object_key  text        not null       -- "datasets/{dataset_id}.parquet"
format      text        not null default 'parquet'
byte_size   bigint      not null       -- size of the stored object
created_at  timestamptz not null default now()

unique (object_key)
```

*Why a separate table at all:* the DataFrame has to live somewhere other than a
Python dict, or every restart and every second worker loses it. Keeping the
pointer in its own table rather than as columns on `datasets` keeps the
"does this dataset exist / is it ready" query independent of storage, and means
a future second storage backend is a new row shape, not a migration of
`datasets`.

*Why Parquet, not the raw CSV:* it preserves the dtypes that
`normalize_dataframe()` worked out. Re-reading a CSV would mean redoing type
inference and risking a different answer to the same question.

*Why `object_key` is stored rather than derived:* it is computable today
(`datasets/{dataset_id}.parquet`) but storing it means a key-naming change later
does not orphan every existing object, and a stray object can be matched back to
its row. The `unique` constraint makes a double-write detectable.

Decision **Q2: Neon Object Storage** (S3-compatible, Beta), private bucket
`dataset` on the `main` branch, objects at `datasets/{dataset_id}.parquet`.
With a 5 MB CSV ceiling, Parquet is typically well under the source, so expect
~1-3 MB per object. Every read and write goes through `dataframe_store.py` and
nothing else, so the **bytea fallback stays one file away** if the Beta causes
problems.

#### Deletion — and the failure case

**The cascade does not reach the bucket.** `on delete cascade` removes the
`dataset_files` row; the object is untouched. So `dataset_service.delete()` must
delete the object explicitly, and the ordering matters:

1. Delete the object (`DeleteObject`).
2. Then delete the `datasets` row, which cascades the pointer away.

That order leaves the recoverable failure rather than the unrecoverable one. If
step 1 succeeds and step 2 fails, the row points at a missing object — `load()`
raises a clear "object missing" error and the dataset can be re-uploaded. If the
order were reversed and step 2 succeeded while step 1 failed, the object would be
**orphaned with no row pointing at it**, invisible to the application and
impossible to find without listing the bucket.

Two consequences I could not design away, both from Neon's current docs:

- **`DeleteObject` is a soft delete** — Neon's docs say it "soft-deletes the
  object on the current branch", so deleting a dataset does **not** reclaim
  storage. Treat storage as monotonically growing within a branch.

  *Corrected after testing it (A7).* An earlier draft of this section said the
  object "remains retrievable on the branch". That is **not** what happens
  through the S3 API: after `DeleteObject`, `GetObject` on the same key
  returns `NoSuchKey`, and `dataframe_store.load()` raises `ObjectMissing`.
  Verified against the live bucket. So the privacy caveat is narrower than
  first written — a deleted dataset is not readable by key — while the
  storage-growth caveat stands, because nothing observed here says the bytes
  were reclaimed. What cannot be determined from the S3 API is whether a
  branch-level mechanism can still recover them, so "deleted" should still not
  be sold to a user as *erasure*.
- **Lifecycle rules are stored but not enforced**, so a TTL cannot be used to
  clean up orphans either.

Mitigation, and the honest limit of it: on delete, record the attempt and log a
warning if the object delete fails, so orphans are at least discoverable in the
logs. A reconciliation job (list the bucket, diff against `dataset_files`) is
the real fix and is **not** in this plan's scope — at 20 datasets per session it
is not yet worth building, and it is written down here so the decision is
deliberate rather than forgotten.

### `preprocessing_reports`

```sql
id                    uuid        pk
dataset_id            uuid        not null unique references datasets(id) on delete cascade
overall_missing_ratio numeric(6,5) not null
duplicate_ratio       numeric(6,5) not null
checks_completed      integer     not null
notice_count          integer     not null
warnings              jsonb       not null default '[]'
errors                jsonb       not null default '[]'
checks                jsonb       not null  -- the ordered list from endpoint 5
created_at            timestamptz not null default now()
```

*Why:* the report is computed once, at upload, from data that is then thrown
away — recomputing it later would mean re-running `prepare_dataframe()` on a
CSV we no longer keep. `jsonb` for `checks` because the list is display-only,
never queried or joined; normalising six presentational rows would buy nothing.
The two ratios are promoted to real columns because they *are* queried (the
rejection threshold, the quality score).

### `conversations`

```sql
id              uuid        pk
dataset_id      uuid        not null references datasets(id) on delete cascade
session_id      uuid        not null references sessions(id) on delete cascade
title           text        not null default 'New Conversation'
message_count   integer     not null default 0
exchange_count  integer     not null default 0   -- completed user+agent pairs
last_message_at timestamptz not null default now()
created_at      timestamptz not null default now()

index (dataset_id, last_message_at desc)
index (session_id, last_message_at desc)
```

*Why:* `dataset_id` is `not null` because a question is meaningless without a
dataset — the schema enforces what the UI already assumes. `session_id` is
denormalised from `datasets` so the cross-dataset search (endpoint 14) and any
ownership check need no join. `message_count` and `last_message_at` are
**denormalised on purpose**: the sidebar renders them for every conversation,
and a `COUNT(*)`/`MAX()` subquery per row is the classic N+1 on the app's most
frequent query. `exchange_count` is what the window and the summary trigger are
counted in (§6) — pairs, never half-pairs. All three are updated in the same
transaction that inserts a message.

### `messages`

```sql
id                 uuid        pk
conversation_id    uuid        not null references conversations(id) on delete cascade
role               text        not null              -- 'user' | 'agent'
status             text        null                  -- agent only: ready|needs_clarification|cannot_answer|failed
content            text        not null              -- the answer text, or the user's question
condensed_question text        null                  -- agent only: the standalone question used
analysis_plan      jsonb       null                  -- the raw tool list from the planner
chart_plan         jsonb       null                  -- {should_plot, chart_type, x, y}
result_data        jsonb       null                  -- the verified result rows
result_kind        text        null                  -- 'table' | 'scalar'
plan_display       jsonb       null                  -- {question, steps[], columnsUsed[], filters}
latency_ms         integer     null
created_at         timestamptz not null default now()

index (conversation_id, created_at)
check (role in ('user','agent'))
check (role = 'agent' or condensed_question is null)
```

*Why:* **this is both the UI's history and the condenser's memory** — one
table, one source of truth, which is the central design decision of §6.

`condensed_question` (your addition) earns its column three times over:

1. It is shown to the user as *"Understood as: …"* (the `condensed` SSE event),
   so it must survive a page reload — a value that exists only in a stream is
   gone the moment the tab is refreshed.
2. It is what the next turn's condenser reads from the window. Feeding it the
   raw *"and per month?"* would make every turn re-derive the whole chain and
   compound its own errors; feeding it the resolved question keeps each turn one
   hop from the truth.
3. It is the debugging record. When an answer is wrong, the first question is
   always *"what did it think I asked?"* Without this column you cannot tell a
   condensation failure from a planning failure, and those have completely
   different fixes.

The `check` constraint keeps it off user rows, where it would be meaningless.

`analysis_plan` and `chart_plan` are kept raw as well as rendered, so a prompt
or presenter change can be replayed over old conversations without another LLM
call. `result_data` is stored so reopening a conversation shows its tables and
charts without re-running the analysis — and it is the source of the result
digest the condenser sees. `result_kind` exists because a plan with no
`group_by` returns a **scalar**, not rows (Suggested change S4). `latency_ms`
costs one integer and will tell you whether the slow part is the LLM or pandas.
`status = 'failed'` is written when a stream dies mid-turn, so a conversation
can never hold a user message with no reply (§6B).

### `conversation_summaries`

```sql
conversation_id   uuid        pk references conversations(id) on delete cascade
summary           text        not null              -- the fact sheet, ~150 words
covers_through_id uuid        not null references messages(id)
exchange_count    integer     not null              -- exchanges folded in so far
updated_at        timestamptz not null default now()
```

**In the first migration**, per your decision — feature 5 uses it immediately,
and adding a table to a live database for a feature you already know you want
is pure overhead.

*Why `covers_through_id`:* it is the whole reason the update can be incremental.
It records the exact message where the fact sheet stops, so a refresh folds in
**only the exchanges between that point and the current window** — never the
whole conversation. On a free tier that is the difference between a summary
call whose prompt grows forever and one that stays a fixed small size.
`exchange_count` makes the trigger a comparison instead of a query: refresh when
`conversations.exchange_count - window_size - summaries.exchange_count >= 2`.

### Relations

```
users 1──* sessions 1──* datasets 1──1 dataset_files
                                  1──1 preprocessing_reports
                                  1──* dataset_columns
                                  1──* conversations 1──* messages
                   1──* conversations                1──1 conversation_summaries
```

Every child cascades on delete, so "delete dataset" is one statement and cannot
leave orphans (decision Q7). `users → sessions` is `on delete set null`, not
cascade: deleting an account must not silently destroy the data, it un-links it.

### Migrations: **Alembic**

*Why Alembic:* it is SQLAlchemy's own migration tool, so the models and the
migrations share one metadata object and `alembic revision --autogenerate`
diffs the real database against the real models. It is the default in the
FastAPI ecosystem, which matters for a project where you will be reading other
people's examples. It runs as a plain command (`alembic upgrade head`), so it
drops into Render's release step or a one-off job.

*Why not the alternatives:* `Base.metadata.create_all()` works exactly once and
then silently stops reflecting model changes — the usual way a demo diverges
from its database. A standalone tool (Atlas, Flyway, raw `.sql` files) means
maintaining the schema twice, in Python and in SQL, which drifts.

*Rules:* one migration per feature, committed with the code that needs it;
always read the autogenerated file before applying it (Alembic misses enum and
server-default changes); run migrations against Neon's **direct** URL, not the
pooled one (see §8); never edit a migration that has run on the deployed
database.

---

## 5. AI backend integration: merge vs. separate service

### Option A — merge the AI code into the FastAPI app as a module

**Pros**
- Same language and runtime. The AI code is already a set of pure functions
  (`run_agent(state)`, `execute_plan(df, plan)`, `explain_result(...)`) plus
  dicts. It is a library, not a service — the only HTTP in it is `main.py`,
  which becomes the new app.
- **The DataFrame never crosses a network boundary.** `execute_plan` needs the
  actual pandas object; over HTTP you would serialise a 100,000-row frame to the
  agent service and the result back, for every question, and lose dtypes on the
  way. This is the decisive argument.
- **Streaming would have to cross the boundary too.** With a separate service
  the token stream from the explainer has to be relayed through a second hop,
  which means two sets of buffering-prevention headers, two timeout policies and
  a much harder answer to "who persists the message if the inner hop dies".
- One deploy, one log stream, one set of env vars, one place where a stack trace
  is readable end to end.
- No duplicated model layer, retry logic, timeout policy or auth hop.
- Cheapest: a second service on a free tier means a second cold start in the
  critical path of a request that already makes three LLM calls.

**Cons**
- A slow pandas or LLM call occupies a worker. Mitigated by `run_in_threadpool`
  plus enough workers; a genuine fix (a job queue) is the same amount of work
  either way.
- Scaling is coupled — more analysis capacity means more API instances.
- A pandas `MemoryError` on a large CSV takes down a process that is also
  serving `/health`. Bounded here by the 5 MB / 100k-row caps and an
  LRU of 3.

### Option B — keep it as a separate service called over HTTP

**Pros**
- Independent scaling and independent memory limits; a crash in analysis cannot
  take the API down.
- A hard boundary around the AI code, which could later be reused by something
  that is not this frontend.
- Lets the agent run on different hardware or a different Python version.

**Cons**
- **Where does the DataFrame live?** Either the agent service re-downloads and
  re-parses the dataset per request (slow, and it must now also reach the
  database — so the "boundary" leaks), or it keeps its own in-memory cache,
  which is exactly the unreliable global dict we are trying to remove, now in a
  place the API cannot see.
- Two deploys, two cold starts, two CORS/secret/logging configurations, and the
  need for an internal auth mechanism between them.
- Relaying SSE through two services, as above.
- Distributed debugging for a solo developer: a failure is now in one of two
  services plus the hop between them.
- No part of this project needs it. There is one frontend, one developer, and a
  single analysis path.

### Recommendation: **Option A — merge, as `app/agent/`.**

The AI code is a Python library that happens to ship with a FastAPI file. Move
`agent/`, `tools.py`, `charting.py`, `validation.py` and `data_utils.py` under
`app/`, fix the flat imports, and call them directly from
`services/analysis_service.py`. The two new LLM steps (condenser, summarizer)
live in `services/`, not in `agent/`, because they are conversation concerns
rather than analysis concerns — `agent/` keeps its single job: turn one question
into a validated plan and a verified result.

Keep the seam clean — services import the agent, the agent never imports a
router, a model or a database session — so that *if* analysis later needs its
own box, extracting it is a mechanical change rather than an untangling.

The cons of Option A are addressed concretely: wrap planner → execute in
`run_in_threadpool`, cap uploads at 5 MB / 100k rows and the cache at 3 frames
so pandas memory is bounded, and set an explicit timeout on the LLM client.
Those three things are needed under Option B as well.

---

## 6. Conversation memory: window + rolling summary + condensation

### What the code does today

`create_agent_state(question, schema, unavailable_columns)` takes **one
question** and `build_agent_prompt` interpolates it into a single-shot prompt
with no `messages` list at all. `sessions[sid]["history"]` is appended to and
never read. So *"now show it per month"* currently produces a plan with no idea
what "it" is. This is new behaviour to build, not a wiring job.

### The design, as decided

**Context is used in exactly ONE place: the condensation step.** The planner
and the explainer never see history. Our own `messages` table in Neon is the
single source of truth, because the frontend must display history anyway — so
reading the same rows back as model context means history can never disagree
with what is on screen.

### 6.1 Condensation vs. passing history to the planner

My revision-1 draft fed the window straight into the planner prompt. You chose
condensation instead. Both work; here is the honest comparison, because the
trade-off is real and it is not one-sided.

| | **Condensation** (chosen) | **History into the planner** (rev 1) |
|---|---|---|
| LLM calls per turn | **3** (condense, plan, explain) | 2 (plan, explain) |
| Added latency | **+1 round-trip** before planning starts, ~0.5-2 s on a free model | none |
| `agent/prompts.py` | **unchanged** — still one question | must be rewritten to accept a message list |
| `agent/core.py` signature | **unchanged** — still one string | gains a `history` parameter |
| `agent/validators.py` | **untouched** | untouched either way |
| Testability | **a pure string→string function.** 20 fixtures, no DB, no pandas, and a failure is one diffable line | you can only test it end to end: a wrong plan might be a bad prompt, bad history, or a bad model |
| Debuggability | `condensed_question` is stored, so "what did it think I asked?" is a column lookup | you must reconstruct the prompt from the message rows to see what the model saw |
| Failure mode | **two places to be wrong instead of one.** A good question can be mis-condensed and the planner then plans the wrong thing, correctly | one place to be wrong, but a longer prompt where the model can confuse history with the live schema |
| Prompt size at the planner | **small and constant** — one question + schema | grows with the window; the schema and the history compete for attention |
| Free-tier cost | **+50 % calls per turn** (2 → 3) | baseline |
| Reusable | the condensed question can be cached, replayed, shown, and diffed | nothing reusable |

**Where condensation genuinely wins:** `validators.py` is 376 lines of strict
checks and `prompts.py` is a carefully tuned single-shot prompt. Condensation
means neither is touched, so **nothing that works today can regress.** That is
worth a lot more than one round-trip. It also isolates the hardest-to-test part
of the system (resolving "it") into the one shape that is trivial to test.

**Where it genuinely loses:** it costs a third of your free-tier calls per turn,
it adds latency before the first `status{planning}` event, and it introduces a
second failure point — a mis-condensed question produces a *confidently wrong*
answer rather than an error, which is the worst kind of bug. §6.6 is the test
set that guards against exactly this, and `condensed` being shown in the UI as
*"Understood as: …"* means the user can see the mistake rather than be misled by
it. That visibility is why your decision is defensible, and it is the reason I
would not build condensation without displaying the result.

**Decision: condensation, as specified.** The regression safety and the
testability outweigh one extra call, and the free-tier cost is partly recovered
by the skips in §6.5.

### 6.2 What the condenser receives

In this order, exactly as decided:

1. **Schema + excluded columns** — a system message, rebuilt from
   `dataset_columns` **every turn**, never taken from history. The rule:
   *the schema is always current, so it goes in the system message; only the
   dialogue is immutable, so only it goes in history.* Putting the schema in
   history means a stale copy contradicting the live one, with no way for the
   model to tell which to trust.
2. **The rolling fact sheet** — everything older than the window, if a summary
   row exists.
3. **The window** — the last **3 exchanges (6 messages)**, counted as
   user+agent pairs, never cutting a pair. Each agent turn in the window
   carries:
   - its `condensed_question`,
   - its `analysis_plan` as compact JSON (no indentation),
   - a **result digest**: the first 5 rows plus the total row count.
     **Never the full `result_data`.**
4. **The new question.**

**Skip the condensation call entirely when there is no history** (first message
in the conversation): the question is already standalone by definition, and on a
free tier a guaranteed-identity call is pure waste.

Why the window is **3 exchanges**: a follow-up refers to the previous turn or
the one before it — "now per month", "and only for Laptop?", "sort it the other
way". Three pairs covers that with one pair of margin. It is also small enough
that the condenser prompt stays roughly constant in size, which matters because
a growing prompt is a growing cost on every single turn. Counting in **pairs**
rather than messages is what stops the window from opening on an agent reply
whose question has been cut off — a half-exchange is actively misleading, worse
than no context. `HISTORY_WINDOW_EXCHANGES` makes it tunable without a deploy,
and `trim_messages` sits behind it as a hard token backstop for the pathological
case (one exchange whose digest is still enormous).

Why a **digest, not the rows**: this is the single most expensive mistake
available here. One 500-row answer in the window would be re-sent on every
subsequent turn, forever, growing the cost of every future question. Five rows
plus `"of 128 rows"` answers everything a follow-up needs ("and the second
one?", "what was the top country again?") at a fixed size.

### 6.3 The rolling summary — a fact sheet, not a narrative

Fixed sections, in this order, max ~150 words:

```
Goal:
Definitions & agreements:
Active filters/assumptions:
Key findings:
```

**Why a fact sheet.** A narrative summary ("the user asked about products, then
about months…") compresses the wrong thing: it keeps the *shape* of the
conversation and loses the *facts*. What a later question actually needs is
"revenue = price × quantity", "only 2024", "Laptop = 1,248". Fixed headings also
make the summary diffable and make a regression visible — if the
"Active filters" line disappears after an update, that is a bug you can see,
whereas a paragraph that drifts is a bug you cannot.

#### The summarizer prompt (`app/prompts/summarizer.txt`)

```
You maintain a short fact sheet about a data-analysis conversation.

Current fact sheet (empty if this is the first update):
{existing_summary}

New exchanges to fold in:
{new_exchanges}

Rewrite the fact sheet so that it also covers the new exchanges.
Keep these four headings, in this order, and write nothing else:

Goal:
Definitions & agreements:
Active filters/assumptions:
Key findings:

Rules:
- Maximum 150 words in total.
- Facts only. No narrative. Never write "the user then asked".
- Keep every definition, agreement and active filter from the current fact
  sheet unless a new exchange explicitly changes or cancels it. These lines
  are the most important: later questions depend on them.
- Record each finding with the scope it was measured in, for example
  "all-time" or "2024 only".
- Drop a finding only when a newer exchange has replaced it.
- Use "-" for list items. Write "none" under a heading that has nothing.
- Never invent a number. Copy numbers exactly from the exchanges.
```

#### Example fact sheet

After five exchanges on `orders.csv` (96 words):

```
Goal: Find which products and countries sell the most, from orders.csv.

Definitions & agreements:
- "Sales" means total quantity, not revenue.

Active filters/assumptions:
- Only 2024 orders, set by the user at exchange 2. Applies until the user says otherwise.

Key findings:
- Laptop is the top product by total quantity: 1,248 units (all-time, measured before the 2024 filter).
- Total quantity in 2024: 19,460 units.
- Monthly peak in 2024: November, 2,310 units.
- Germany is the top country by 2024 quantity: 3,102 units.
- Top 5 countries (2024): Germany 3,102, France 2,748, Spain 2,190, Italy 1,905, Poland 1,482.
```

Note the parenthetical on the Laptop line. That is the `Record each finding with
the scope` rule doing real work: without it, a later comparison against a 2024
number would be wrong by exactly the amount the filter removes, and nothing
would flag it. Expect to tune this rule — it is the most likely place for the
fact sheet to quietly mislead.

#### Update policy

- **Incremental.** `old summary + the exchanges that just left the window →
  new summary`. The whole conversation is **never** re-read. This keeps the
  summarizer's prompt a fixed small size no matter how long the conversation
  runs.
- **Triggered by `covers_through_id`.** Refresh only when **2 exchanges have
  left the window** since the last update:
  `conversations.exchange_count - HISTORY_WINDOW_EXCHANGES - summaries.exchange_count >= 2`.
  Amortised cost: **0.5 calls per turn** instead of 1.
- **After the `done` event**, in a background task. The user never waits for it.
- **Failure is non-fatal.** Keep the previous summary, leave
  `covers_through_id` untouched, log a warning. The next trigger folds in the
  larger gap. The chat is never blocked and never fails because a summary
  failed.

The gap this leaves, stated plainly: between the moment an exchange leaves the
window and the moment the summary catches up, **one exchange can be invisible to
the condenser** (window-size 3, trigger 2 → the 4th-oldest exchange is out of
the window but may not yet be in the fact sheet). This is a deliberate trade for
halving the summary cost. It only matters if a fact appears exactly once, in
exactly that exchange, and is needed on exactly the next turn. If you ever see
it happen, set `SUMMARY_REFRESH_EXCHANGES=1` and pay the extra call.

### 6.4 The condensation design

#### Prompt (`app/prompts/condenser.txt`)

```
You rewrite a user's new message into ONE standalone question about a dataset.

Dataset columns and types:
{schema}

Columns excluded from analysis (they cannot be used):
{excluded_columns}

Known from earlier in this conversation:
{fact_sheet}

Recent exchanges (oldest first):
{window}

New user message:
{question}

Rules:
- Return ONE question as a single line of plain text. No JSON, no quotes,
  no preamble, no explanation.
- The question must stand on its own. Resolve every reference such as
  "it", "that", "those", "the same", "the other way".
- Carry forward any filter, definition or agreement from the fact sheet or
  the recent exchanges that still applies, unless the new message changes it.
- If the new message is already standalone, return it unchanged.
- If the last agent turn asked a clarifying question, treat the new message
  as the answer to it, and write the question the user originally meant.
- If the new message starts a new topic, return it as its own question.
  Carry forward only filters the user set for the whole conversation.
- Use the exact column names from the schema above when the user's words
  clearly map to one.
- Never invent a column, a value, a filter or a number.
- Never answer the question.
```

#### Output handling

The output is one line of text, so **plain text with a guard**, not structured
output: on a free model, asking for JSON adds a parse-failure mode for a
single-string payload, and the retry would cost another call. The guard in
`condenser.py`:

- strip whitespace, surrounding quotes and a leading `Question:` label;
- if the result is empty, longer than 300 characters, or spans multiple lines,
  **fall back to the raw user message unchanged** and log it. A pass-through is
  always safe: it is exactly the behaviour of a first message.

That fallback is what keeps the condenser from being a new way for the whole
chat to fail.

#### Clarification answers

When the previous agent message has `status = 'needs_clarification'`, the new
user message is the *answer*, not a new question. The prompt says so, and
`conversation_service` additionally passes the clarification text as the last
agent turn in the window so the pairing is unambiguous. Example:

```
agent (needs_clarification): "Do you mean highest total quantity, or highest total revenue?"
user:                        "quantity"
condensed:                   "Which product has the highest total quantity sold in 2024?"
```

#### An addition I would make — flag it and drop it if you disagree

A message like *"only 2024 from now on"* is an **instruction**, not a question.
As specified, it goes to the condenser, then to the planner (which will likely
return `needs_clarification` or `cannot_answer` — neither is right), then to the
explainer: 3 calls to produce a bad answer to something the user did not ask.

I would let the condenser return a tiny JSON object instead of a bare string:

```json
{ "kind": "question",            "question": "Show total quantity per month for 2024" }
{ "kind": "instruction",         "acknowledgement": "Got it — I'll keep everything to 2024 unless you say otherwise." }
{ "kind": "clarification_answer","question": "Which product has the highest total quantity sold in 2024?" }
```

On `instruction`, `analysis_service` persists an agent message with
`status = 'ready'`, the acknowledgement as `content`, no plan and no result,
and emits `done` — **1 LLM call instead of 3.** On a free-only budget that pays
for itself the first time you say "only 2024".

The cost: the condenser now returns JSON, so it regains the parse-failure mode
the plain-text design avoided. Mitigation: the same guard, defaulting to
`kind: "question"` with the raw text. **The planner still receives exactly one
string**, so your constraint holds either way. If you would rather keep the
condenser as a pure string→string function, drop this and accept that
instructions cost 3 calls — say which and I will write it that way.

#### LangChain classes

```python
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
```

| Class / function | Used for | Where |
|---|---|---|
| `ChatGoogleGenerativeAI(...)` | **two** chat models, built once each and cached by role, with timeout and 429 backoff. Only this module imports a provider SDK, enforced by a test | `app/agent/llm.py` |
| `ChatPromptTemplate` + `MessagesPlaceholder("window")` | the condenser prompt: fixed system rules, window injected per turn | `services/condenser.py` |
| `SystemMessage` / `HumanMessage` / `AIMessage` | mapping `messages.role` → LangChain messages; one function | `services/conversation_service.py` |
| `trim_messages(strategy="last", token_counter=model, include_system=True)` | hard token backstop behind the 3-exchange window | `services/conversation_service.py` |
| `StrOutputParser` | the condenser's single-line output | `services/condenser.py` |
| `model.astream(...)` | the explainer, token by token (§6B) | `app/agent/explainer.py` |
| `ChatPromptTemplate` | the summarizer prompt | `services/summarizer.py` |

**Not used, deliberately:** `create_agent` + a `PostgresSaver` checkpointer —
the official v1 recommendation for agent memory — and the legacy
`ConversationBufferMemory` / `ConversationChain` (now in `langchain-classic`,
deprecated, slated for removal in 2.0) and `RunnableWithMessageHistory` (legacy;
deprecated in the JS reference). Why no checkpointer: the frontend needs
`messages` rows regardless, so a checkpointer means a second LangGraph-shaped
copy that drifts the first time a write half-fails; `create_agent` is built for
a model-driven tool-calling loop, whereas this flow is deterministic on purpose
(plan → *strictly validate* → whitelisted pandas → explain) and
`validators.py` refusing unknown tools and columns is the project's core safety
property; and checkpoints store graph state, not the things that actually need
remembering here — a schema rebuilt every turn, a truncated digest, a relational
dataset reference. Those are a deliberate projection *into* the prompt, simpler
to write than to express as checkpointed state.

### 6.5 LLM calls per turn

Free tier, so this is the budget that matters.

| Turn | Condenser | Planner | Planner retry | Explainer | Summarizer | Total |
|---|---|---|---|---|---|---|
| First message (no history) | **skipped** | 1 | 0-1 | 1 | 0 | **2-3** |
| Normal follow-up | 1 | 1 | 0-1 | 1 | 0 | **3-4** |
| Follow-up, summary refresh due | 1 | 1 | 0-1 | 1 | 1 | **4-5** |
| Instruction only (the §6.4 addition) | 1 | 0 | 0 | 0 | 0 | **1** |
| `needs_clarification` / `cannot_answer` | 1 | 1 | 0-1 | **0** | 0 | **2-3** |

When each runs: condenser **before** the planner, in the request; planner and
retry in the request (threadpool); explainer in the request (streamed); summarizer
**after** `done`, in a background task, amortised to **0.5 per turn** by the
2-exchange trigger.

Steady-state cost: **~3.5 calls per turn**, against 2 for today's code. That is
a **+75 %** increase, and on a free-only budget it is the main thing to watch.
What holds it down:

- condensation skipped on the first message of every conversation;
- the explainer skipped on clarification and cannot-answer turns (there is
  nothing to explain) — this is free and worth doing from the start;
- the summarizer amortised to 0.5 and run off the request path;
- the window fixed at 3 exchanges and results digested to 5 rows, so prompts
  stop growing — a free tier usually limits *tokens*, not just calls;
- `CONDENSER_ENABLED=false` as a kill switch: the app degrades to
  "no follow-up understanding" instead of failing, which is the right behaviour
  if you hit a quota wall mid-demo.

**One optional optimisation, not scheduled.** A plan cache keyed on
`(dataset_id, condensed_question)`: on an exact hit, reuse the stored
`analysis_plan` and skip the planner entirely (−1 call). Datasets are immutable
here, so the plan stays valid. I have not put it in the roadmap because it is
only worth it if you see repeated questions, and a cache that is subtly wrong is
worse than one more call. Mentioning it so it is on the record.

### 6.6 Worked example: what the condenser sees at question 9

Dataset `orders.csv` — `order_date` (datetime64), `product` (object),
`category` (object), `quantity` (int64), `price` (float64), `country` (object).

The conversation so far:

| # | User | Condensed to | Answer |
|---|---|---|---|
| 1 | Which product has the highest total quantity sold? | *(skipped — first message)* | Laptop, 1,248 units |
| 2 | Only 2024 from now on. | instruction | "Got it — I'll keep everything to 2024." |
| 3 | And the total? | Show the total quantity for 2024 | 19,460 units |
| 4 | Per month? | Show total quantity per month for 2024 | Nov peak, 2,310 |
| 5 | Which country buys the most? | Which country has the highest total quantity in 2024? | Germany, 3,102 |
| 6 | Show the top 5. | Show the top 5 countries by total quantity in 2024 | Germany … Poland |
| 7 | What about keyboards? | Show total quantity for Keyboard per country in 2024 | Germany 412 … |
| 8 | Sort it the other way. | Show total quantity for Keyboard per country in 2024, sorted ascending | Poland 96 … |

**Question 9: "Compare that to the laptop number."**

Window = the last 3 exchanges = **6, 7, 8**. Exchanges 1-5 have left it, so the
Laptop figure from exchange 1 exists **only in the fact sheet**. This is the
case the design has to survive.

The condenser receives:

```
[SystemMessage]
Dataset columns and types:
order_date: datetime64[ns]   product: object      category: object
quantity: int64              price: float64       country: object

Columns excluded from analysis (they cannot be used):
customer_phone: 78.4% of values are missing.

Known from earlier in this conversation:
Goal: Find which products and countries sell the most, from orders.csv.
Definitions & agreements:
- "Sales" means total quantity, not revenue.
Active filters/assumptions:
- Only 2024 orders, set by the user at exchange 2. Applies until the user says otherwise.
Key findings:
- Laptop is the top product by total quantity: 1,248 units (all-time, measured before the 2024 filter).
- Total quantity in 2024: 19,460 units.
- Monthly peak in 2024: November, 2,310 units.
- Germany is the top country by 2024 quantity: 3,102 units.

[HumanMessage]  Show the top 5 countries by total quantity in 2024
[AIMessage]
condensed_question: Show the top 5 countries by total quantity in 2024
analysis_plan: [{"tool":"filter_data","column":"order_date","operator":"greater_than_or_equal","value":"2024-01-01"},{"tool":"aggregate_data","column":"quantity","operation":"sum","group_by":"country"},{"tool":"sort_data","column":"quantity","ascending":false},{"tool":"limit_results","limit":5}]
result: 5 of 5 rows — Germany 3102, France 2748, Spain 2190, Italy 1905, Poland 1482

[HumanMessage]  Show total quantity for Keyboard per country in 2024
[AIMessage]
condensed_question: Show total quantity for Keyboard per country in 2024
analysis_plan: [{"tool":"filter_data","column":"order_date","operator":"greater_than_or_equal","value":"2024-01-01"},{"tool":"filter_data","column":"product","operator":"equals","value":"Keyboard"},{"tool":"aggregate_data","column":"quantity","operation":"sum","group_by":"country"}]
result: 5 of 14 rows — Germany 412, France 338, Spain 291, Italy 254, Poland 96

[HumanMessage]  Show total quantity for Keyboard per country in 2024, sorted ascending
[AIMessage]
condensed_question: Show total quantity for Keyboard per country in 2024, sorted ascending
analysis_plan: [{"tool":"filter_data","column":"order_date","operator":"greater_than_or_equal","value":"2024-01-01"},{"tool":"filter_data","column":"product","operator":"equals","value":"Keyboard"},{"tool":"aggregate_data","column":"quantity","operation":"sum","group_by":"country"},{"tool":"sort_data","column":"quantity","ascending":true}]
result: 5 of 14 rows — Poland 96, Italy 254, Spain 291, France 338, Germany 412

[HumanMessage]  Compare that to the laptop number.
```

Expected output:

```
Show total quantity for Laptop per country in 2024, sorted ascending
```

Three things to notice, each one a design requirement earning its place:

- **"the laptop number" resolves from the fact sheet, not the window.** Without
  §6.3 the condenser would have no idea what "the laptop number" refers to —
  exchange 1 is long gone. This is the whole reason for the rolling summary.
- **"that" resolves from the window** (the ascending Keyboard-per-country
  breakdown), so the comparison keeps both the `sorted ascending` shape and the
  per-country grouping.
- **"2024" is carried forward from `Active filters/assumptions`**, an agreement
  made at exchange 2 — seven exchanges and one window-eviction ago. §6.7's T-M1
  is the test for exactly this.

And one honest wrinkle the example exposes: the fact sheet records Laptop as
1,248 **all-time**, while the new question is scoped to 2024. The right answer
is to re-measure Laptop under the current filter, which is what the expected
output does — the number from exchange 1 is not reusable. The scope annotation
in the fact sheet is what makes that visible instead of silently comparing two
different populations.

### 6.7 Tests

Four conversations. All four run against a **stubbed chat model** so they are
free, fast and deterministic (`tests/test_condenser.py`); run them once against
the real model before deploying.

**T-C1 — pronoun follow-up (the basic case)**

```
1 user  Which product has the highest total quantity sold?
        → condensation SKIPPED (no history)
2 user  Now show it per month.
        → EXPECT: "Show total quantity per product per month"
        FAIL IF: "it" survives, or the question becomes about something
                 other than quantity
```

**T-C2 — clarification answer**

```
1 user  Show me the best product.
  agent (needs_clarification) "Do you mean by total quantity sold, or by total revenue?"
2 user  quantity
        → EXPECT: "Which product has the highest total quantity sold?"
        FAIL IF: the condenser emits "quantity" as the question, or asks the
                 clarification again
```

This is the one most likely to break, because the user's message is a single
word that is also a column name. If it fails, the fix is in the prompt rule
about clarifications, not in the planner.

**T-C3 — complete topic change (the dangerous case)**

```
1 user  Which product has the highest total quantity sold?
2 user  Only 2024 from now on.                    → instruction
3 user  Which country buys the most?
4 user  Forget all that — how many rows have no country at all?
        → EXPECT: "How many rows have a missing country?"
                  (the 2024 filter MAY be carried; products and countries
                   MUST NOT be)
        FAIL IF: "per product", "top country", or any grouping from
                 exchanges 1-3 appears
```

This is the failure mode condensation introduces and history-into-the-planner
does not: an over-eager condenser **contaminates an independent question with
stale context**, and the planner then plans the contaminated question perfectly.
The user sees a confident, wrong answer. The prompt's
`If the new message starts a new topic` rule exists for this test, and
*"Understood as: …"* in the UI is the user's last line of defence. If you only
ever run one condenser test, run this one.

**T-M1 — an agreement survives leaving the window** *(your test)*

```
1 user  Which product has the highest total quantity sold?
2 user  Only 2024 from now on.                    → the agreement
3..8    five more questions, so exchange 2 is out of the 3-exchange window
        and has been folded into the fact sheet
9 user  And the total quantity?
        → EXPECT: a condensed question that still says 2024, and an
                  analysis_plan that still contains the order_date filter
        FAIL IF: the 2024 filter is gone
```

Assert on two things, not one: the `condensed_question` **text** and the stored
`analysis_plan` **JSON**. The text passing while the plan drops the filter is a
real and otherwise invisible failure. Also assert that
`conversation_summaries.summary` contains a non-empty
`Active filters/assumptions` section after exchange 5 — if the fact sheet lost
the agreement, T-M1 is failing for a summarizer reason, not a condenser reason,
and the two have different fixes.

---

## 6B. Streaming design (SSE)

Decision Q8(b). The answer must appear while it is being produced.

### Why SSE over a `POST`, rather than `EventSource`

`EventSource` can only issue a `GET` and cannot set headers — it could carry
neither the question body nor `X-Session-Id`. So the frontend uses
`fetch()` with a `POST` and reads `response.body` as a `ReadableStream`,
parsing the SSE framing itself in `src/api/stream.js`. WebSockets would also
work but add a connection lifecycle, a reconnect policy and a second protocol
for a one-shot, one-direction stream — SSE is the right size for this.

### The two endpoints, one generator

```python
# services/analysis_service.py
async def run_turn(...) -> AsyncIterator[TurnEvent]:
    ...                      # the 10 steps of §2, yielding events

# routers/conversations.py
@router.post(".../messages")          # JSON: drain, return the final message
@router.post(".../messages/stream")   # SSE:  forward every event
```

Writing the generator **in feature 4**, before the SSE endpoint exists, is what
makes feature 5.5 additive rather than a rewrite. The JSON endpoint stays
forever: it is how `/docs` stays usable and how integration tests assert on a
turn without parsing a stream.

### Events

Wire format is standard SSE — `event: <type>`, then `data: <json>`, then a
blank line. The full catalogue and a complete example sequence are in
[`API_CONTRACT.md`](./API_CONTRACT.md).

| Event | Payload | When |
|---|---|---|
| `status` | `{stage, label}` | entering each real stage: `condensing`, `planning`, `validating`, `executing`, `explaining` |
| `condensed` | `{question}` | after condensation; **omitted** when it was skipped |
| `result` | `{resultData, resultKind, chartPlan, plan}` | after `execute_plan` **and** chart validation |
| `token` | `{text}` | each explainer chunk |
| `done` | `{message}` | after persistence; same shape as the JSON endpoint |
| `error` | `{code, message}` | terminal failure |

The five `stage` values are the real pipeline stages, replacing the three
decorative steps in `ChatInterface.jsx:184-204`. `label` is the display string,
so wording changes do not need a frontend deploy.

`result` arrives **before** the first `token` on purpose: the table and chart
are the answer, the sentence is the commentary. The user reads the data while
the prose types in, which makes a 15 s turn feel like a 3 s one.

### The explainer must return plain text

Today `explain_result` asks for `{"summary": "..."}` and
`validate_explainer_output` (`agent/validators.py:356-377`) parses it. **JSON
cannot be streamed usefully** — you cannot show a half-written JSON object, so
you would have to buffer the whole thing, which defeats the point.

So: `agent/explainer.py`'s prompt drops the JSON wrapper and returns prose,
consumed with `model.astream(...)`. Consequences, stated plainly:

- `validate_explainer_output` **becomes dead code.** It stays in
  `validators.py` (untouched, as agreed) but nothing calls it. Note it in the
  file rather than leaving a reader to wonder.
- The guarantee it provided — a non-empty summary — moves to the generator:
  accumulate tokens, and if the buffer is empty when the stream ends, fall back
  to a deterministic sentence built from the result by `presenters.py` (e.g.
  *"Laptop has the highest total quantity sold, at 1,248 units."*). That is
  strictly better than today's behaviour, which raises and loses the turn.
- Every explainer rule in the current prompt ("do not recalculate", "do not
  reproduce the dataset", "1-3 sentences") is kept verbatim. Only the output
  envelope changes.

### Persistence and failure

- The **user message is persisted before the first event is emitted.** A
  question is never lost, whatever happens next.
- The **agent message is persisted exactly once**, immediately before `done`.
- On any failure after the user message: persist an agent message with
  `status = 'failed'` and the error text as `content`, emit `error`, then stop.
  **A conversation can never contain a user message with no reply** — that is
  the invariant, and it is what the `failed` status exists for.
- `needs_clarification` / `cannot_answer`: emit `status`, then the message text
  (as `token` events, so the UI path is identical), then `done`. No `result`.
  **No explainer call** — there is nothing to explain.

### Client disconnect — the decision

Starlette cancels the response generator when the client goes away, which would
abandon the turn **after** the planner and explainer calls have already been
paid for, leaving an orphan user message. On a free tier, throwing away calls
you have already spent is the wrong answer.

**Decision: the pipeline runs as its own `asyncio.Task` that writes events into
an `asyncio.Queue`; the SSE response only drains the queue.** If the client
disconnects, the queue is dropped but **the task runs to completion and persists
the agent message.** Consequences:

- the user reloads the conversation and the answer is there;
- the LLM calls are not wasted;
- the invariant holds — no user message without a reply;
- a disconnect is logged at info, not error.

The cost is that an abandoned turn still consumes a worker and a few LLM calls
to completion. Bounded by `LLM_TIMEOUT_SECONDS` and by the fact that a turn is
seconds, not minutes. The alternative (cancel on disconnect) saves those calls
but leaves orphan user messages and wastes the calls already made — worse on
both counts.

### Proxy buffering

A reverse proxy that buffers the response makes streaming silently
indistinguishable from not streaming: everything arrives at once, at the end.
Required on every SSE response:

```
Content-Type:      text/event-stream; charset=utf-8
Cache-Control:     no-cache, no-transform
Connection:        keep-alive
X-Accel-Buffering: no
```

`no-transform` and `X-Accel-Buffering: no` are the two that actually stop
nginx-family proxies from buffering. Also send a heartbeat comment line
(`: ping\n\n`) every `SSE_HEARTBEAT_SECONDS` (15) so an idle proxy does not
close a connection while the planner is thinking. And do **not** gzip this
response — compression implies buffering.

**Test it on the deployed Render URL, not only locally.** Local uvicorn has no
proxy in front of it, so streaming always looks perfect on your machine; Render
puts a proxy in the path, and this is exactly where streaming breaks. The check:

```bash
curl -N -X POST https://<app>.onrender.com/api/conversations/<id>/messages/stream \
  -H 'Content-Type: application/json' -H 'X-Session-Id: <uuid>' \
  -d '{"content":"Which product has the highest total quantity sold?"}'
```

`-N` disables curl's own buffering. **Events must appear one at a time over
several seconds.** If they all land together at the end, buffering is the
problem — not the code. Confirm in a browser too, because CORS applies to the
stream like any other response.

### Frontend

- `src/api/stream.js` — `POST` via `fetch`, read `response.body`, decode with
  `TextDecoder`, split on `\n\n`, parse `event:` / `data:`, expose an **async
  iterator of typed events**. All SSE parsing lives here; **components never
  touch the stream**, as you specified. Handle a `data:` field split across
  chunk boundaries — a buffer that is not carried over between reads is the
  classic bug, and it shows up only under slow networks.
- `ChatInterface.jsx` — the fake three steps are replaced by the real `status`
  events; *"Understood as: …"* renders from `condensed`; the table and chart
  render on `result`; the answer text appends on each `token`.
- Errors: on `error`, or on the stream ending without `done`, show a visible
  message in the message list with a retry affordance. **Never an infinite
  spinner** — which is what the current code would do, since it has no error
  branch at all.
- Also set an idle timeout: if no event arrives for ~45 s, treat it as a drop.
  A stalled stream is otherwise indistinguishable from a slow one.

---

## 7. Environment variables (names only)

### Backend

| Name | Purpose | Decided value |
|---|---|---|
| `DATABASE_URL` | Neon **pooled** string — **the running app only** | |
| `DATABASE_URL_DIRECT` | Neon **direct** string — **Alembic only, nothing else** | |
| `AWS_ENDPOINT_URL_S3` | Neon Object Storage endpoint, `br-….storage.<region>.aws.neon.tech`. Injected by `neon env pull` | |
| `AWS_ACCESS_KEY_ID` | Neon storage credential | |
| `AWS_SECRET_ACCESS_KEY` | Neon storage credential | |
| `AWS_REGION` | storage region | |
| `NEON_STORAGE_BUCKET` | **not injected by Neon** — the bucket name must be set by hand | `datasets` |
| `GEMINI_API_KEY` | Google AI Studio key. **Passed explicitly** by `app/agent/llm.py`: the SDK checks `GOOGLE_API_KEY` then `GEMINI_API_KEY`, and there is a known auth failure when only the latter is set alongside Application Default Credentials | |
| `LLM_PLANNER_MODEL` | the planner (`core.py`) — must emit a plan that survives `validators.py` | `gemini-3.8-flash` |
| `LLM_FAST_MODEL` | explainer, and later the condenser and summariser — cheap, frequent rewriting | `gemini-3.5-flash-lite` |
| `LLM_PLANNER_THINKING_BUDGET` | `gemini-3.8-flash` is a **reasoning** model; left alone it spends its whole output budget on hidden thinking. `0` disables it, blank uses the model default. See risk 1 | `0` |
| `LLM_STREAMING` | verified `true` for the fast model in A8 | `true` |
| `LLM_TIMEOUT_SECONDS` | there was no timeout before A3; a hung provider hung the request forever | `60` |
| `LLM_MAX_RETRIES` | retries for a **429 only**, with exponential backoff and jitter. Nothing else is retried: a malformed request fails identically the second time | `2` |
| `CONDENSER_ENABLED` | kill switch (§6.5). Off = no follow-up understanding, but the app still works | `true` |
| `HISTORY_WINDOW_EXCHANGES` | the window, in user+agent pairs | `3` |
| `HISTORY_TOKEN_BUDGET` | `trim_messages` backstop behind the window | |
| `SUMMARY_REFRESH_EXCHANGES` | exchanges that must leave the window before a refresh | `2` |
| `SUMMARY_MAX_WORDS` | fact-sheet ceiling | `150` |
| `SSE_HEARTBEAT_SECONDS` | keep-alive comment interval | `15` |
| `MAX_UPLOAD_BYTES` | no limit today — an unbounded `await file.read()` into memory (`main.py:107`) | `5242880` (5 MB) |
| `MAX_DATASET_ROWS` | bounds pandas memory per worker | `100000` |
| `MAX_DATASETS_PER_SESSION` | the cap, enforced against `sessions.dataset_count` | `20` |
| `DATAFRAME_CACHE_SIZE` | LRU of loaded DataFrames | `3` |
| `CORS_ALLOWED_ORIGINS` | comma-separated. Hardcoded to `localhost:5173` today (`main.py:15`), which **will break the moment you deploy** | |
| `ENVIRONMENT` | `development` / `production` — gates `/docs` and tracebacks | |
| `LOG_LEVEL` | | |
| `SENTRY_DSN` | optional | |

No `SECRET_KEY`: anonymous sessions need no signing. It appears the day real
accounts do.

### Frontend

| Name | Purpose |
|---|---|
| `VITE_API_BASE_URL` | the backend origin. **Must** be `VITE_`-prefixed or Vite will not expose it |

Only this one. The session id is generated in the browser
(`crypto.randomUUID()`) and kept in `localStorage`, so it is **not** an env
var. Note that **every `VITE_` variable is compiled into the public bundle** —
never put a key or secret behind that prefix.

Also: commit a `.env.example` listing these names with empty values.
`.gitignore` already covers `.env` and `.env.*` with a `!.env.example`
exception, so the slot is ready.

---

## 8. Deployment plan

### Where — decision Q3(a)

| Part | Host | Why |
|---|---|---|
| Frontend | **Vercel** | A static Vite build. Git-push deploys, per-branch previews, and a free tier that genuinely covers this. |
| Backend | **Render Web Service** | Needs a long-lived process: multi-second requests, an open SSE connection per turn, pandas in memory, an LRU DataFrame cache. **Not a serverless function** — a cold start with a pandas + pyarrow import, a platform response timeout, and a per-invocation sandbox that destroys the cache are each individually fatal to this workload, and SSE is the final nail. |
| Database | **Neon** | Serverless Postgres, branchable, generous free tier. |
| Dataset files | **Neon Object Storage**, private bucket `dataset`, behind `dataframe_store.py` | Same project as the database, so no extra vendor and no egress between them. **Beta**, and only in `aws-us-east-2` / `aws-eu-central-1` — which constrains the region choice below. |

**Region is now constrained, not free.** Neon Object Storage is available only
in **`aws-us-east-2` (Ohio)** and **`aws-eu-central-1` (Frankfurt)**. Since the
bucket already exists on `main`, its region is fixed — match the Render region
to *that*, not to the database region in the abstract. Check `AWS_REGION` in
`backend/.env` before choosing in feature 7. If the Neon project turns out to be
in a region where Object Storage is unavailable, the bytea fallback is the
answer, which is the other reason `dataframe_store.py` is the only door to
storage.

**Same region for Render and Neon** (your decision, and the right one). A chat
turn makes several round-trips to the database — load the dataset, the window,
the summary, then two writes. A cross-continent hop adds 100 ms+ to *each*, and
it is latency you pay on every turn forever. Pick the Neon region first, then
match the Render region to it.

### CORS

`backend/main.py:13-19` currently hardcodes
`allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"]`. In
production that blocks every real request, and it is the single most likely
cause of a "the deploy is broken" afternoon.

- Read origins from `CORS_ALLOWED_ORIGINS` and split on commas.
- Dev: `http://localhost:5173,http://127.0.0.1:5173`.
- Prod: the exact Vercel origin(s), scheme included, **no trailing slash**. Add
  preview origins explicitly if you use them — wildcards are not worth it.
- **Never `allow_origins=["*"]` with `allow_credentials=True`.** The browser
  rejects that combination, and the current code already sets
  `allow_credentials=True`. With a header-based session id you do not need
  credentials at all, so consider setting it to `False`.
- `allow_methods` / `allow_headers` are `["*"]` today; narrow them to the
  contract's methods and to `Content-Type` + `X-Session-Id`. **`X-Session-Id` is
  a custom header, so it must be in `allow_headers` explicitly** — a missing
  entry there fails the preflight on every request, including the stream.
- Check that Render does not strip `Access-Control-Allow-Origin` on 4xx. A 422
  that loses its CORS header shows up in the browser as an opaque network error,
  which is a genuinely confusing hour to debug.

### Env vars at deploy time

- Set them in each host's dashboard; never in the repo.
- `VITE_API_BASE_URL` is a **build-time** substitution — change it and you must
  rebuild, not just restart.
- First-release order: Neon → `alembic upgrade head` (direct URL) → Render →
  read the Render URL → set `VITE_API_BASE_URL` → Vercel → go back and put the
  Vercel origin into `CORS_ALLOWED_ORIGINS`. The circular dependency between the
  last two steps is normal; expect one extra redeploy of each.
- Render release command: `alembic upgrade head`. Start command:
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

### Neon: pooled vs. direct

Neon gives two connection strings. The pooled one has **`-pooler`** in the host
name and goes through PgBouncer in transaction mode.

| Use | Which | Why |
|---|---|---|
| The running FastAPI app | **Pooled** | Neon limits direct connections, and every Uvicorn worker holds its own SQLAlchemy pool. Workers × pool size exhausts the direct limit quickly, and the failure mode is intermittent "too many connections" under load. |
| **Alembic migrations** | **Direct** | DDL, advisory locks and session-scoped state do not survive transaction-mode pooling. Migrations through the pooler fail in confusing, partially-applied ways. This is the one that bites people. |
| `psql`, one-off scripts, `pg_dump` | **Direct** | Session-level features, and the connection count is 1. |
| `LISTEN`/`NOTIFY`, persistent `SET`, server-side cursors | **Direct** | Transaction pooling breaks all of them. |

Three practical notes:

- With asyncpg behind PgBouncer, **disable statement caching** —
  `connect_args={"statement_cache_size": 0}` and
  `prepared_statement_cache_size=0`. Transaction pooling can hand a later query
  a different backend than the one that prepared the statement, and the error
  (`prepared statement "__asyncpg_stmt_1__" does not exist`) looks like nothing
  to do with pooling.
- Neon **autosuspends** an idle compute, so the first request after idle pays a
  cold start. Do not defeat this with a frequent `/health` ping — that keeps the
  compute awake and burns the free tier's compute hours. Accept it. It does mean
  the first `status{condensing}` event of the day can be a few seconds late,
  which is itself an argument for streaming: the user sees *something*
  immediately.
- Use a Neon **branch** for the test database so integration tests never touch
  development data.

---

## 9. Feature roadmap

Your order, with the two sequencing changes from revision 1 (both code-driven)
and the new feature 5.5.

**Why feature 1 is a restructure, not a greenfield skeleton:**
`backend/main.py` already has a working FastAPI app with CORS, an upload
endpoint and an analyse endpoint. The job is to move it into `app/` and fix the
flat imports — today it only runs from inside `backend/`, which is not how
Render starts a process.

**Why feature 0.5 exists:** the declared `requirements.txt` is missing `openai`
and `python-dotenv`, which the agent imports. A clean clone cannot start.
Twenty minutes now saves a confusing afternoon later.

**Why 4 and 5 stay separate but coupled:** `create_agent_state(question, …)`
takes one string, and with condensation **it still will** — that is the point of
§6.1. Feature 4 builds the turn with condensation stubbed to a pass-through
(`condensed = raw question`), so feature 5 only has to fill in one function
instead of changing a signature that three modules call.

**Bug assignments**, as decided: `requirements.txt` → 0.5; the missing `else`
branch → 1; `charting.py` wiring and the `unavailable_columns={}` gap → 4; the
hardcoded `product`/`quantity` renderer and scalar results → 6.

---

### 0.5 — Repair the dev environment

**Build:** a pinned `requirements.txt` covering everything imported — `openai`,
`python-dotenv`, `pandas`, `pyarrow`, **`boto3`**, `sqlalchemy`, `asyncpg`,
`greenlet`, `alembic`, `pydantic-settings`, plus `pytest`/`pytest-asyncio`/
`httpx` for tests; `backend/.env.example` with the §7 names **and empty
values**; `git rm -r --cached` the committed `__pycache__` and add it to
`.gitignore`; pin the deployment Python version; drop
`streamlit`/`altair`/`pydeck` from the venv (keeping `pyarrow`, which Streamlit
had pulled in and we now need for Parquet).

**Env file location:** `backend/.env`, loaded by `app/config.py`. The app runs
from `backend/`, so a root-level `.env` would be found in development and
missed in any other working directory. `.gitignore` already covers `.env` and
`.env.*` with a `!.env.example` exception.

**Done when:** a fresh clone + `pip install -r backend/requirements.txt` +
`uvicorn` starts and answers `GET /` without an `ImportError`.

**Test it yourself:** delete `.venv`, recreate it, install, start the server,
open `http://127.0.0.1:8000/docs`.

---

### 1 — FastAPI skeleton + Neon connection + `/health`

**Build:** the `app/` package of §3; `config.py` with pydantic-settings;
`db/session.py` with an async engine on the pooled URL
(`statement_cache_size=0`); move the existing modules in and fix imports;
`GET /health`; CORS from `CORS_ALLOWED_ORIGINS` including `X-Session-Id`; a
global exception handler producing the contract's error envelope; **add the
missing `else` branch** so no status can return `null`. Keep the old
`/api/upload` and `/api/analyze` working off the in-memory dict so nothing
regresses.

**First check of the whole project — the model.** Before anything else, a
throwaway script (`backend/scratch/check_model.py`) that, for **both** model
roles, confirms (a) the id is in the live `models.list` output, (b) a
completion returns, with its latency and token usage, and (c) **streaming
works** — iterating the chunks and timing them. All three matter: an id that
does not resolve blocks everything, a model that cannot stream makes feature
5.5 impossible, and — as A8 found — an id can resolve and answer correctly
while still being too slow or too rate-limited to use. **Done:** both models
pass all three. Add latency and quota to whatever you check next time; neither
is visible from a model list.

**Done when:** `uvicorn app.main:app` starts **from `backend/`**, `/health`
reports `database: ok` **and `storage: ok`** against real Neon, `/docs` lists
the routes, and the model check prints tokens one at a time.

**Test it yourself:** `curl http://127.0.0.1:8000/health` → `database: "ok"`,
`storage: "ok"`. Break `DATABASE_URL` on purpose and confirm a 503 naming
*which* dependency failed, with no stack trace. Run the model script and watch
the tokens arrive separately.

**Storage health check:** `HeadBucket`, with the result cached ~30 s. An
uncached check bills an S3 request per ping and keeps the Neon compute awake,
which §8 warns against.

---

### 2 — DB schema + migrations

**Build:** SQLAlchemy models for the nine tables in §4 — including `users`
(empty), `sessions`, `conversation_summaries`, `messages.condensed_question` and
`dataset_files.object_key`, all in the **first** migration; Alembic reading
`DATABASE_URL_DIRECT` **only, with no fallback to `DATABASE_URL`** (which is the
pooled string — risk 24); `dataframe_store.py` (Parquet ⇄ Neon Object Storage,
`LRU(3)`, boto3 with `endpoint_url` + path-style + SigV4, the only module that
imports boto3); `deps.get_session()` reading and validating `X-Session-Id`.

**Done when:** `alembic upgrade head` creates every table on Neon;
`alembic downgrade base` removes them cleanly; `alembic revision
--autogenerate` on an unchanged model tree produces an **empty** migration
(proof the models and the database agree).

**Test it yourself:** run `upgrade head`, then in the Neon SQL editor:
`select table_name from information_schema.tables where table_schema='public';`
— expect `sessions`, `users`, `datasets`, `dataset_columns`, `dataset_files`,
`preprocessing_reports`, `conversations`, `messages`,
`conversation_summaries`. Insert a session, a dataset and a conversation by
hand, delete the **session**, and confirm all three are gone — that verifies the
cascade chain. Then `UPDATE sessions SET user_id = …` and confirm the datasets
are now reachable through the user without touching the datasets table — that
verifies the upgrade path.

---

### 3 — Core endpoints matching the mock data

**Build:** endpoints 2-10 of the contract, minus the chat endpoints: upload →
validate → persist → report (with the 5 MB / 100k-row / 20-dataset limits);
dataset list/detail; report; columns; preview; conversation list/create; message
list. `presenters.py` for the formatted strings.

**Done when:** every endpoint returns **exactly** the JSON in
`API_CONTRACT.md`, uploads survive a server restart, a rejected CSV returns 422
with the `DatasetRejected` fields populated, a 21st dataset returns 409, and a
request with no `X-Session-Id` returns 400.

**Test it yourself:** in `/docs`, upload a real CSV with a session id; confirm
`GET /api/datasets` shows it with correct counts; **restart the server and
confirm it is still there** (the current in-memory version fails this); upload a
CSV where one column is >70 % empty and check it comes back `available: false`
with a reason; upload a CSV that is >40 % empty and check for the 422; try a 6 MB
file and check for the 413; send a **different** session id and confirm you see
an empty dataset list.

---

### 4 — Connect the AI backend + the chat endpoint (as an event generator)

**Build:** `analysis_service.run_turn()` as the **async generator** of §2 and
§6B, and the JSON endpoint that drains it. Inside: load the DataFrame from
`dataframe_store`, build the real schema **and the real `unavailable_columns`**
from `dataset_columns` (fixing the `{}` at `main.py:47`), call the planner,
validate, execute, **validate the chart against the actual result using
`charting.py`** (dead code today), explain, persist. Condensation stubbed to a
pass-through. The explainer switched to plain text with the empty-buffer
fallback. Blocking section in `run_in_threadpool`. The `failed`-status path so
no user message is ever left unanswered.

**Done when:** a question posted to a real conversation returns a `ready`
message with `content`, `resultData` and `plan`; both messages are persisted and
come back from endpoint 10; an ambiguous question returns `needs_clarification`;
an out-of-scope question returns `cannot_answer`; a provider failure returns 502
**and** leaves a `failed` agent message; and an invalid chart is suppressed
rather than returned.

**Test it yourself:** upload the `orders.csv`-shaped file, create a
conversation, and post four cases through `/docs` —
"Which product has the highest total quantity sold?" (ready),
"What is the average price?" (ready, **scalar** — look at what comes back; this
is Suggested change S4), "Show me the best" (clarification),
"Predict next year's sales" (cannot_answer). Then `GET` the messages and
confirm the full exchange is stored, with `analysis_plan` and `result_data`
populated. Then set `GEMINI_API_KEY` to a wrong value and confirm you get a 502
**and** a `failed` agent message rather than a user message on its own.

---

### 5 — LangChain conversation memory (window + fact sheet + condensation)

**Build:** `app/agent/llm.py` with `init_chat_model`; `core.py` and
`explainer.py` moved onto the LangChain model; `conversation_service.load_window()`
(3 exchanges, pairs only, result digests of 5 rows + count);
`condenser.py` with the §6.4 prompt, the plain-text guard and the
pass-through fallback; `summarizer.py` with the §6.3 fact-sheet prompt,
incremental updates via `covers_through_id`, the 2-exchange trigger, the
after-`done` background task and the non-fatal failure path;
`condensed_question` persisted and emitted.

**Done when:** T-C1, T-C2, T-C3 and T-M1 from §6.7 all pass; the condensation
call is **skipped** on a first message; and a 30+ message conversation still
works without a context error.

**Test it yourself:** the decisive sequence, in one conversation:

1. "Which product has the highest total quantity sold?" → Laptop
2. **"Now show it per month."** → a monthly breakdown of *quantity*, not a
   clarification and not an error. This one exchange is the whole feature.
3. "And only for Laptop?" → the same monthly analysis, filtered.
4. "Forget that — how many rows have no country?" → **must not** mention
   products or months (T-C3).

Then the memory test: say "only 2024 from now on", ask five unrelated
questions, then ask "and the total quantity?" — the 2024 filter must still be in
the stored `analysis_plan` (T-M1). Check `select condensed_question from
messages` to see what it understood at each step, and `select summary from
conversation_summaries` to read the fact sheet. Finally, stop the server,
restart it, reopen the same conversation and ask a follow-up — it must still
work, which is what proves the memory is in Neon and not in a process.

---

### 5.5 — SSE streaming endpoint + explainer token streaming

**Build:** `POST /api/conversations/{id}/messages/stream`; `api/sse.py`
(event → wire format, the four anti-buffering headers, the 15 s heartbeat);
`schemas/events.py`; the `asyncio.Task` + `asyncio.Queue` disconnect design of
§6B; explainer tokens through `model.astream`. The JSON endpoint keeps working
from the same generator.

**Done when:** `curl -N` shows events **arriving one by one over several
seconds, not all at the end**; `result` arrives before the first `token`;
`condensed` is absent on a first message; a mid-stream failure emits `error`
**and** persists a `failed` message; and a client that disconnects mid-stream
still finds the completed answer in the database.

**Test it yourself:**

```bash
curl -N -X POST http://127.0.0.1:8000/api/conversations/<id>/messages/stream \
  -H 'Content-Type: application/json' -H 'X-Session-Id: <uuid>' \
  -d '{"content":"Which product has the highest total quantity sold?"}'
```

Watch for `status` → `condensed` → `status` → `result` → many `token` → `done`,
with visible gaps. Then run it again and **press Ctrl-C in the middle**; wait
five seconds; `GET` the messages and confirm the complete agent answer is there.
Then repeat the whole check against the **deployed Render URL** in feature 7 —
local uvicorn has no proxy, so local success proves nothing about production.

---

### 6 — Replace the mock data in the frontend (and consume the stream)

**Build:** `src/api/session.js` (`crypto.randomUUID()` → `localStorage`),
`src/api/client.js` (base URL, `X-Session-Id`, error-envelope parsing, timeout),
`src/api/stream.js` (the SSE async iterator, with cross-chunk buffering);
delete `MOCK_DATASETS`; replace the four fake handlers in `App.jsx`; add loading
and **error** states (there are none today); pass the real props to
`DatasetRejected`; render `PreprocessingReport` from endpoint 5; fill the
"Columns & Types", "Preview" and "Conversations" tabs; replace the fake
three-step progress with real `status` events; show *"Understood as: …"* from
`condensed`; render the table and chart on `result` and type the answer on
`token`; apply **S4** (scalar results — a crash otherwise) and **S3**
(column-agnostic table and chart — without it only `orders.csv` renders); warn
next to the upload box that clearing browser data permanently orphans datasets.

**Done when:** `grep -ri mock frontend/src` is empty, a hard refresh restores
the real state, the answer visibly types in, and the full flow — upload →
overview → report → conversation → follow-up → chart — works in the browser.

**Test it yourself:** `npm run dev` with the backend running. Upload a CSV that
is **not** about products (e.g. `customers.csv` with `city` and `age`) and ask
"What is the average age per city?" — the table headers and chart axes must show
`city`/`age`. That is the test S3 exists for. Ask a follow-up and check that
*"Understood as: …"* appears and is correct. Then **stop the backend
mid-answer** and confirm a visible error, not an infinite spinner. Then open
devtools, clear `localStorage`, reload, and confirm you get an empty sidebar —
that is the anonymous-session model working as designed, and it is why the
warning text matters.

---

### 7 — Deploy

**Build:** `Dockerfile` or a Render start command
(`uvicorn app.main:app --host 0.0.0.0 --port $PORT`); `alembic upgrade head` as
the release command; backend on Render; frontend on Vercel; **the same region as
Neon**; env vars per §7; CORS set to the real Vercel origin with `X-Session-Id`
in `allow_headers`; the pooled/direct split per §8.

**Done when:** the public Vercel URL completes the whole flow against the public
Render backend, `/health` is green, **streaming works through Render's proxy**,
and a redeploy does not lose datasets.

**Test it yourself:** open the deployed URL on your **phone** (so it is
definitely not your machine or your cache), upload a CSV, ask a question, ask a
follow-up. Confirm the answer **types in** rather than appearing all at once —
that is the one thing that only breaks in production. Run the `curl -N` check
against the Render URL. Then look at the Neon dashboard and see the rows.
Finally redeploy the backend and confirm the dataset and its conversation are
still there.

---

## 10. Risks

Ordered by how likely each one is to cost you a day.

1. **The model choice itself — resolved, after two dead ends.**
   Streaming is **no longer an unknown**: both configured models stream
   incrementally, verified in A8 (2 chunks, time-to-first ~1.3-1.5s). The
   assumption all of §6B rests on is confirmed, so feature 5.5 is safe to
   build on that count.

   Getting there cost two wrong model choices, both worth recording because
   neither was visible from a model list:

   - *Hugging Face / Qwen (A4).* The hardcoded id
     `Qwen/Qwen3.8-Flash-Next:featherless-ai` was not a real model, and the
     account had no inference credits (HTTP 402). Nothing could be verified
     at all. This is why the provider was replaced in A8.
   - *`gemini-3.8-flash` (A8).* The id is real and answers correctly, but on
     the free tier it is throttled to the point of uselessness: **548s for a
     single output token**, and 504 `DEADLINE_EXCEEDED` at any sane timeout.
     `thinking_budget=0` is honoured (usage reports `reasoning=0`), so this is
     *not* reasoning overhead — the newest generation is simply queued behind
     paid traffic. `gemini-3.7-flash` measured 154s. Measurements:

     | model | time for a 1-token reply |
     |---|---|
     | `gemini-3.8-flash` (budget 0) | 548.6s |
     | `gemini-3.8-flash` (effort low) | 143.8s |
     | `gemini-3.7-flash` (budget 0) | 153.6s |
     | **`gemini-3.6-flash`** (budget 0) | **1.4s** |
     | `gemini-3.5-flash` (budget 0) | 1.5s |

   Settled on **`gemini-3.6-flash`** for the planner and
   **`gemini-3.5-flash-lite`** for everything else. The lesson for next time
   is that a model id existing in `models.list` says nothing about whether it
   is *usable* on a free tier — latency and daily quota both have to be
   measured, which is what `backend/scratch/check_model.py` now does.

2. **The Gemini free tier: quota, privacy, and what you may demo with.**
   Three separate constraints, all of them consequences of "free only".

   *Call budget — measured, and much tighter than expected.* Gemini's free
   tier limits `generateContent` to **20 requests per DAY, per model, per
   project**. Not per minute. The quota error is explicit:

   > Quota exceeded for metric: `generate_content_free_tier_requests`,
   > limit: **20**, model: `gemini-3.6-flash` … Please retry in 9h38m

   Measured in A8, a single question costs **2 planner calls + 1 explainer
   call** (see the markdown-fence finding below). The planner and the
   explainer draw on *separate* per-model quotas, so the binding constraint is
   the planner's 20/day:

   | | per question | daily ceiling |
   |---|---|---|
   | planner (`gemini-3.6-flash`) | 2 | **~10 questions/day** |
   | explainer (`gemini-3.5-flash-lite`) | 1 | much higher; `-lite` models get a far larger allowance |

   **~10 questions per day** is the real budget for the whole project, and
   that is before §6 adds condensation and summarisation, which would take a
   turn to ~3.5 calls and roughly halve it again. This is not a theoretical
   risk: the A8 verification run exhausted the planner's daily quota and two
   of six questions came back 429 on the first attempt at the run.

   **What A9 did about it.** Three mitigations, in order of how much they
   buy:

   1. **One planner call per question instead of two** (risk 3b). This is the
      biggest single win and it doubles the usable question count outright.
   2. **Fallback chains.** `LLM_PLANNER_MODELS` and `LLM_FAST_MODELS` are
      ordered lists, and the quota is *per model*, so a chain of *n* models is
      *n* times the daily capacity. On a 429 the next model is tried
      **immediately** — a daily quota does not recover from a backoff of any
      length, so sleeping first would only add latency to the same outcome.
      Only once every model has refused does it back off and retry the chain,
      which is what recovers a per-*minute* limit. Gemini's own
      `retryDelay` for a daily limit is ~9 hours, so it is **capped at 120s**
      and otherwise ignored; past that the honest answer is the 429.

      | role | chain | daily planner capacity |
      |---|---|---|
      | planner | `gemini-3.6-flash`, `gemini-2.5-flash` | 40 calls ≈ **40 questions** |
      | fast | `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-2.5-flash-lite` | 60 calls |

      So ~10 questions/day became **~40**: 2× from the fence fix, 2× from the
      second planner model.
   3. **A development cache.** `LLM_DEV_CACHE=true` stores responses on disk
      keyed by `(model, full prompt)`, so re-running a verification costs
      nothing. Verified in A9: the cold run made 5 real calls, the warm run
      made **0** and served 5 from cache. It is **refused in production** by
      `app/config.py` regardless of the env file, because a cached answer
      shown to a real user looks perfectly fine and was computed for someone
      else's dataset.

   Consequences still to plan around:
   - **Development burns the same quota as demos** whenever the cache is off.
     Turn it on while iterating; the live latency numbers in this document
     were all taken with it off.
   - `CONDENSER_ENABLED=false` (§6.5) remains the right default for any day
     you intend to demo, since §6 would take a turn to ~3.5 calls.
   - A `-lite` model is the only free model with really large volume. If the
     planner ever has to run many times it belongs on `-lite` too — but note
     that **`gemini-3.5-flash-lite` rejects a thinking budget of 0** while
     accepting 512 or −1. `list-models` reports `thinking=True` for it, so the
     capability is not discoverable; `llm.py` learns it at runtime by retrying
     without the budget and remembering. Thinking is therefore configured
     **per model, never per role** — the earlier role-based version failed
     every call with a bare `INVALID_ARGUMENT` the moment the planner was
     pointed at a `-lite` model.
   - Rate-limit handling works and was observed working: a 429 retries twice
     with exponential backoff **and jitter** and then surfaces as a real
     **HTTP 429 with `Retry-After`**, never a 500. The jitter matters because
     the condenser, planner and explainer of one turn are rate-limited within
     milliseconds of each other and would otherwise retry in lockstep. What
     retrying cannot do is conjure quota: against a *daily* limit the backoff
     is futile by construction, and the honest response is the 429.

   *Privacy — the one that constrains what you can show.* On the free tier
   **Google may use prompts and responses to improve their products.** Every
   uploaded CSV becomes part of a prompt, so every upload is a disclosure to
   Google. Two consequences, and they are product decisions, not technical
   ones:

   - **Demo with sample data only.** `samples/orders.csv` and
     `samples/customers.csv` exist for this. Do not upload personal,
     confidential or client data while the app runs on a free tier.
   - The UI must **say so next to the upload box** before anyone uploads
     anything, in the same place it already has to admit that clearing browser
     storage orphans their data (§4). A privacy note that appears only in a
     README is not consent.

   Moving to a paid tier changes the data-use terms and is the only real fix;
   until then this limitation belongs on screen.
3. **A mis-condensed question produces a confidently wrong answer.** This is the
   failure mode condensation *introduces*: the planner plans the wrong question
   perfectly, nothing errors, and the user is misled. T-C3 is the guard, and
   *"Understood as: …"* in the UI is the user's only visibility. Do not ship
   condensation without displaying it.
3b. **The planner's markdown fence — FIXED in A9, and it halved LLM usage.**

   *The problem (measured in A8).* `gemini-3.6-flash` returned
   ```` ```json … ``` ```` on **attempt 1 of every single question**.
   `json.loads` failed, `validate_agent_output` reported "invalid JSON", the
   retry prompt fired, and attempt 2 passed. The pipeline was correct — the
   retry exists for exactly this — but it was paying **2 planner calls per
   question**, which against a 20/day quota is the difference between ~20 and
   ~10 questions a day.

   *The fix, two independent layers.* Asking nicely is not enough on its own,
   so both are in place:

   1. **Gemini JSON mode.** `response_mime_type="application/json"` on the
      planner client (`LLM_PLANNER_JSON_MODE`). This is a request, not a
      guarantee, which is why there is a second layer.
   2. **A deterministic fence strip.** `app/agent/text_utils.py` removes a
      fence that wraps the *whole* reply, before anything parses it. It lives
      at the provider boundary rather than in `validators.py`, because a
      markdown fence is a provider quirk and `validators.py` should keep
      describing what a valid plan *is*. It is deliberately conservative: a
      fence in the middle of prose is left alone, because guessing which part
      of a mixed reply was "the answer" is how a parser starts silently
      picking the wrong one — that case is a planner failure and should be
      reported as one.

   *Result, measured over Q1-Q3 in A9:* **every question passed on attempt 1**
   and the planner cost dropped from 2 calls to 1. Total real provider calls
   for three questions: **5** (3 planner + 2 fast; the clarification needs no
   explainer call), against 9 planner calls for six questions in A8.

4. **JSON reliability at the planner.** It asks for JSON in prose and parses it
   by hand, with one retry. Small free models emit prose preambles, markdown
   fences and trailing commas. Every failure is a user-visible 502 after two
   paid calls. Mitigation: strip fences before parsing, raise the retry count,
   and use the provider's JSON mode if it has one. Note that
   `with_structured_output` would cost a capability the free model may not have.
5. **Proxy buffering kills streaming invisibly.** Everything works locally and
   arrives in one lump on Render. The four headers and the heartbeat in §6B
   prevent it; the `curl -N` check against the **deployed** URL is the only way
   to know. Budget an hour for this on first deploy.
6. **Latency.** Three sequential LLM calls plus a possible retry plus a Neon
   cold start. 30 s+ is realistic. Streaming makes it *feel* fine — the first
   `status` event lands in under a second — which is the main reason Q8(b) is
   the right call. But there is still no timeout anywhere today: set
   `LLM_TIMEOUT_SECONDS`, the frontend's 45 s idle timeout, and a Render request
   timeout above both.
7. **Client disconnect and orphan messages.** Handled by the task+queue design
   in §6B, but it is subtle code: an `asyncio.Task` that outlives its response,
   with a DB session that must not be the request's. Getting this wrong gives
   you either orphan user messages or a session closed under a running task.
   Test it explicitly (feature 5.5).
8. **In-memory DataFrames vs. real hosting.** The current `sessions` dict breaks
   with more than one worker *silently and intermittently* — upload hits worker
   A, the question hits worker B, "Session not found". Until feature 2's
   `dataframe_store` lands, run exactly one worker.
9. **CORS on the first deploy**, now with a custom header. `X-Session-Id` must
   be in `allow_headers` or **every** request fails preflight, including the
   stream. Near-certain to bite once, and the browser error names nothing
   useful. Check it in a browser — curl ignores CORS entirely.
10. **Memory.** `await file.read()` loads the whole upload, pandas holds the
    frame, the LRU holds 3, and a free Render instance gives 512 MB. Bounded now
    by 5 MB / 100k rows / `LRU(3)`, but verify with a real 5 MB CSV of 100k wide
    rows rather than assuming — a 100k × 50 float frame is ~40 MB in pandas, and
    three of those is most of your container.
11. **The fact sheet quietly loses an agreement.** If the summarizer drops
    `Active filters/assumptions`, every later turn silently stops honouring
    "only 2024" and the numbers are all wrong with no error. T-M1 asserts on
    both the summary section and the stored plan for this reason. This is the
    highest-consequence, lowest-visibility failure in the memory design.
12. **The summary-lag gap.** With window 3 and trigger 2, one exchange can be
    outside the window and not yet in the fact sheet. Documented and accepted in
    §6.3; `SUMMARY_REFRESH_EXCHANGES=1` is the fix if it bites.
13. **The explainer is no longer validated.** Switching to plain text for
    streaming makes `validate_explainer_output` dead code. The empty-buffer
    fallback replaces its one guarantee, but nothing now stops the explainer from
    recalculating a number in prose — only the prompt does. If you see invented
    numbers, that is where to look.
14. **Dead chart validation.** `charting.py` is never called today, so a chart
    that passed the *predicted*-column check can fail against the *actual*
    result and reach the browser as a broken graph. Wired in during feature 4 —
    it is written, just unconnected.
15. **The hardcoded `product`/`quantity` renderer.** Until S3 is done, any CSV
    that is not about products shows an empty table. The most likely thing to
    make the app *look* broken to someone you demo it to.
16. **Scalar results.** No UI path at all; `.map()` over a number. "What is the
    average price?" is a first-class use case. S4.
17. **The session id lives only in `localStorage`.** Clearing browser data
    permanently orphans every dataset, with no recovery path and no email to
    recover to. Say so in the UI (feature 6). Also: anyone who learns the id
    reads that session's data — acceptable for anonymous uploads, not once
    accounts exist.
18. **No tests.** `backend/tests/` is empty and you are about to add a database,
    a migration tool, an LLM framework, a condenser, a summarizer, SSE and a
    frontend rewrite. `validation.py`, `tools.py`, `validators.py` and the
    condenser are all pure functions — free to test, and exactly where a silent
    regression would hide.
19. **Neon Object Storage is Beta.** No stability guarantee on the API or the
    service, and several S3 behaviours are *accepted but not enforced* —
    versioning returns `x-amz-version-id: null`, lifecycle rules are stored and
    ignored, object-lock enforcement is limited. Do not build anything on those
    three. Mitigation is the one you specified: every byte goes through
    `dataframe_store.py`, so the bytea-in-Postgres fallback is a one-file change.
20. **`DeleteObject` is a soft delete** — but less visibly than first
    written. Tested in A7: after a delete, `GetObject` returns `NoSuchKey`, so
    the object is **not** readable by key and `load()` raises `ObjectMissing`.
    What the soft delete costs is **storage**: it is not reclaimed, so usage
    grows monotonically within a branch, and lifecycle rules cannot clean up
    after it because they are stored but not enforced. Say "removed", not
    "erased", to the user.
21. **Orphaned objects.** The Postgres cascade does not reach the bucket, so a
    failed object-delete leaves a file no row points at — invisible to the app.
    The delete ordering in §4 makes the *other* failure (row points at a missing
    object) the one that happens, because that one is recoverable and visible.
    A bucket-vs-table reconciliation job is the real fix and is deliberately out
    of scope at this size.
22. **Storage credentials have no enforced expiry.** Neon accepts an
    `expires_at` but does not currently enforce it, so a leaked key stays valid
    until explicitly revoked (`neon credentials revoke`). `backend/.env` is
    gitignored and must stay that way; rotation changes only the secret, not the
    access key id.
23. **Neon free-tier limits** — autosuspend latency, compute-hour and storage
    caps. At 5 MB CSVs and 20 datasets per session the volume is fine; the soft
    delete above is what makes the storage figure drift upward over time.
24. **Alembic through the pooler.** Migrations on the pooled URL fail in
    partially-applied ways. §8. `DATABASE_URL` in `backend/.env` **is** the
    pooled string, so this is a live trap, not a theoretical one: `alembic/env.py`
    must read `DATABASE_URL_DIRECT` and must never fall back to `DATABASE_URL`.
25. **Type-flow strictness vs. real questions.** `validate_plan_types` requires
    dataframe-in/dataframe-out, so a plan ending in a scalar followed by any
    other step is rejected — correctly, but the model has to discover this via
    the retry, which costs a call. Expect `cannot_answer` on questions that are
    actually answerable. Once you have real transcripts, add the failing
    patterns to the prompt as examples.
26. **Committed `.pyc` files and a stale Streamlit install.** Cosmetic now;
    confusing later when `ui.cpython-314.pyc` turns up in a grep for code that
    no longer exists. Fixed in 0.5.

---

## 11. Decisions (resolved)

The open questions from revision 1, with the answers now locked in. Nothing in
this document guesses at any of them.

| | Question | Decision |
|---|---|---|
| **Q1** | Authentication | **(d) Anonymous sessions.** The frontend generates a `crypto.randomUUID()`, keeps it in `localStorage`, and sends it as `X-Session-Id`. Ownership hangs off `sessions`; `sessions.user_id` (nullable, FK to an empty `users` table created in migration 1) is the upgrade path, so linking to a real account later is one `UPDATE` and no table is rewritten. §4. |
| **Q2** | Dataset storage | **CHANGED after revision 2: Neon Object Storage** (S3-compatible, Beta). Private bucket `dataset` on the `main` branch, objects at `datasets/{dataset_id}.parquet`, boto3 with `endpoint_url` + path-style. `dataset_files` stores the key, not bytes. All access through `dataframe_store.py`, so the **bytea-in-Postgres fallback is one file away**. Max CSV **5 MB**. §4. |
| **Q3** | Hosting | **(a) Vercel + Render Web Service + Neon, same region.** §8. |
| **Q4** | Limits | **5 MB**, **100,000 rows**, **LRU of 3** DataFrames, **20 datasets** per session. §4, §7. |
| **Q5** | LLM provider | **(a) Model, base URL and key from env vars** — done in `app/config.py`, and `app/agent/llm.py` is the only place a client is built. Budget **free only**, which is why §6.5 exists. Checked in A4: the previously hardcoded model id **does not exist** (corrected to `Qwen/Qwen3.8-Flash-Next-FP8`), and the account returns **402, no inference credits**, so streaming is still unverified. Risk 1. |
| **Q6** | Dataset sharing | **Private.** Nothing in the UI hints at sharing; not built. |
| **Q7** | Retention | **Keep everything, cascade deletes, cap 20 datasets per session.** §4. |
| **Q8** | Progress indicator | **Changed to (b): real streaming.** Full design in §6B, contract in `API_CONTRACT.md`, built in feature 5.5. |

### Two things I need from you before writing code

Neither blocks the documents; both change the implementation.

1. **The condenser's return type** (§6.4). As specified it is a bare string, so
   an instruction like *"only 2024 from now on"* costs 3 LLM calls to answer
   badly. I recommend a small `{kind, question|acknowledgement}` object, which
   makes it 1 call — a real saving on a free-only budget — at the price of a
   JSON parse step in the condenser. The planner still receives one string
   either way. **Say which you want.**
2. **A sample CSV in `backend/data/`** (it is empty today). Every test in §6.7
   and features 3-6 assumes an `orders.csv` with `order_date`, `product`,
   `category`, `quantity`, `price`, `country`. If you have the real file, add
   it; otherwise I will generate one as the first step of feature 0.5 so the
   tests have something to run against.
