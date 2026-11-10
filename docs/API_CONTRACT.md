# API Contract

Status: proposal (Task 0, discovery). Nothing here is implemented yet.

Revision 2 — reflects the locked decisions in
[`PLAN.md` §11](./PLAN.md#11-decisions-resolved): anonymous sessions via an
`X-Session-Id` header, a 5 MB / 100,000-row upload ceiling, 20 datasets per
session, and **real SSE streaming** of the chat answer (endpoint 11b).

Revision 3 — datasets are stored in **Neon Object Storage**, not as `bytea` in
Postgres. The only endpoint this changes is 13 (`DELETE`), where the cascade no
longer reaches the file and "deleted" does not mean "erased".

This contract is derived from the mock data in `frontend/src/App.jsx` and from
what each component actually reads. Where the mock shape is awkward for a real
backend, **the contract still matches the mock** and the improvement is listed
at the bottom under [Suggested changes](#suggested-changes).

- Base URL: `${VITE_API_BASE_URL}` (e.g. `http://127.0.0.1:8000` in dev)
- All request and response bodies are JSON, except dataset upload (multipart).
- Key casing: **camelCase** in the API, because the existing frontend mock is
  camelCase (`rowCount`, `colCount`, `messageCount`, `resultData`, `showChart`,
  `chartTitle`, `columnsUsed`). The Python layer stays snake_case internally;
  Pydantic response models convert at the edge (`alias_generator=to_camel`).
  This choice is made purely to keep frontend changes minimal.
### Session identity (decision Q1d)

There is no login. **Every endpoint except `GET /health` requires a
`X-Session-Id` header.**

```
X-Session-Id: 3f9a1c22-8d4e-4b17-9c03-6e2a7b514d88
```

- The **frontend** generates it once with `crypto.randomUUID()` and keeps it in
  `localStorage` (`src/api/session.js`). `src/api/client.js` attaches it to
  every request.
- The **backend** upserts a `sessions` row on first use and scopes every query
  to it. A missing or non-UUID header is `400 SESSION_REQUIRED` — the server
  does **not** mint an id for the client, so a malformed value can never create
  an orphan row.
- A session sees only its own datasets and conversations. Sending a different
  id returns an empty list, not an error.
- `X-Session-Id` is a custom header, so it must appear in the CORS
  `allow_headers` list or every preflight fails. See `PLAN.md` §8.
- **Upgrade path:** when real accounts arrive, the header is replaced by a
  signed token and `sessions.user_id` is filled in. No response shape in this
  document changes, and no table is rewritten (`PLAN.md` §4).
- Honest limitation: this is a bearer capability, not authentication. Anyone who
  learns the id can read that session's data, and clearing browser storage
  orphans every dataset permanently. Both are documented in `PLAN.md` §4 and
  surfaced in the UI.

## Error format

The current `backend/main.py` returns `{"status": "error", ...}` with HTTP 200.
That is a flaw: the frontend cannot distinguish success from failure without
parsing the body. The contract uses real HTTP status codes plus a single
envelope:

```json
{
  "error": {
    "code": "DATASET_REJECTED",
    "message": "The dataset contains 47.3% missing values, which exceeds the allowed limit of 40%.",
    "details": { "missingRate": "47.3%", "maxAllowed": "40%" }
  }
}
```

| Code | HTTP | Meaning |
|---|---|---|
| `SESSION_REQUIRED` | 400 | `X-Session-Id` missing or not a UUID |
| `VALIDATION_ERROR` | 400 | Bad request body / empty question |
| `UNSUPPORTED_FILE` | 400 | Not a parseable CSV, bad encoding, duplicate headers |
| `DATASET_REJECTED` | 422 | CSV parsed but failed quality thresholds |
| `NOT_FOUND` | 404 | Unknown dataset / conversation id, or one owned by another session |
| `FILE_TOO_LARGE` | 413 | Over `MAX_UPLOAD_BYTES` (5 MB) |
| `TOO_MANY_ROWS` | 413 | Over `MAX_DATASET_ROWS` (100,000) |
| `DATASET_LIMIT_REACHED` | 409 | This session already holds 20 datasets |
| `LLM_UNAVAILABLE` | 502 | Provider call failed or returned unusable output after retries |
| `INTERNAL_ERROR` | 500 | Anything else |

A dataset or conversation belonging to a different session returns **404, not
403** — confirming that an id exists would leak the existence of other people's
data, and the client has no legitimate use for the distinction.

Note: an ambiguous question (`needs_clarification`) and an unanswerable question
(`cannot_answer`) are **not** errors. They come back as HTTP 201 agent messages
with a different `status` field — see `POST /api/conversations/{id}/messages`.

**On the streaming endpoint**, an error that happens *before* the response
starts is an ordinary HTTP error with this envelope. Once the stream has
started, the status line is already `200` and cannot be changed, so a failure
arrives as an `error` **event** instead (endpoint 11b). The client must handle
both.

---

## 1. `GET /health`

Liveness + DB reachability. Not used by the UI; used by the host's health check
and by you to confirm the Neon connection.

Response `200`:

```json
{ "status": "ok", "database": "ok", "version": "0.1.0" }
```

If the DB is unreachable: `503` with `"database": "unreachable"`.

**Called by:** nothing in the frontend (deployment/platform only).

**Notes:** the **only** endpoint that does not require `X-Session-Id`. Keep it
cheap (`SELECT 1`), because Neon autosuspends and a heavy health check keeps the
compute awake and burns quota.

---

## 2. `POST /api/datasets`

Upload a CSV. Replaces `handleFileUpload` in `App.jsx:98-127`, which currently
fakes a 1.5s delay and invents `rowCount`/`colCount` with `Math.random()`.

Request: `multipart/form-data`, single field `file` (the UI's input is
`accept=".csv"`, single file, `WelcomeScreen.jsx:29-35`).

Response `201` — the object is exactly one element of `MOCK_DATASETS`:

```json
{
  "id": "9f1c2a44-5e3b-4a7e-9f41-0d6e2b7a1c33",
  "name": "orders.csv",
  "rowCount": 2384,
  "colCount": 8,
  "size": "45 KB",
  "missingRate": "2.1%",
  "duplicateRate": "0.4%",
  "status": "ready",
  "conversations": []
}
```

Rejected dataset `422` — the fields map 1:1 onto `DatasetRejected.jsx` props,
which `App.jsx` currently never passes:

```json
{
  "error": {
    "code": "DATASET_REJECTED",
    "message": "The dataset contains too many missing values to provide reliable analysis.",
    "details": {
      "filename": "problematic.csv",
      "fileSize": "28 KB",
      "missingRate": "47.3%",
      "maxAllowed": "40%",
      "reasons": [
        "The dataset contains 47.3% missing values, which exceeds the allowed limit of 40%."
      ]
    }
  }
}
```

**Called by:** `src/App.jsx` (`handleFileUpload`), rendered through
`src/components/WelcomeScreen.jsx` and, on 422,
`src/components/DatasetRejected.jsx`.

**Notes:**
- `status` is `"ready"` whenever the upload succeeds. The field exists in the
  mock and `DatasetOverview.jsx:45-48` renders a hardcoded "Ready for analysis"
  badge, so keep the field for a future `"processing"` case.
- The rejection rules already exist in `backend/validation.py`: dataset missing
  > 40%, duplicate rows > 50%, empty file, duplicate column names. The current
  code returns these as HTTP 200 `{"status":"error"}`; this contract moves them
  to 422 / 400.
- `size` and the two rates are **pre-formatted strings** because the mock is
  (`'45 KB'`, `'2.1%'`, `'0.4%'`). See Suggested changes S1.

**Limits (decision Q4), checked in this order:**

| Check | Limit | Response |
|---|---|---|
| Request body size | **5 MB** (`MAX_UPLOAD_BYTES`) | `413 FILE_TOO_LARGE` |
| Datasets already held by this session | **20** (`MAX_DATASETS_PER_SESSION`) | `409 DATASET_LIMIT_REACHED` |
| Rows after parsing | **100,000** (`MAX_DATASET_ROWS`) | `413 TOO_MANY_ROWS` |
| Quality thresholds | `validation.py` | `422 DATASET_REJECTED` |

Size and dataset-count are checked **before** the file is parsed, so an
oversized upload never reaches pandas. Row count can only be known after
parsing. Example:

```json
{
  "error": {
    "code": "DATASET_LIMIT_REACHED",
    "message": "You already have 20 datasets. Delete one before uploading another.",
    "details": { "current": 20, "maximum": 20 }
  }
}
```

The frontend has no UI for either case today — `WelcomeScreen` only knows
"uploading" and `DatasetRejected` only renders the missing-values story. Feature
6 adds a plain error message for the other codes; reusing `DatasetRejected` for
"too large" would show a misleading 47.3 %-missing bar.

---

## 3. `GET /api/datasets`

The sidebar's dataset list with nested conversations. Replaces the
`MOCK_DATASETS` constant that initialises state at `App.jsx:76`.

Response `200`:

```json
{
  "datasets": [
    {
      "id": "1",
      "name": "orders.csv",
      "rowCount": 2384,
      "colCount": 8,
      "size": "45 KB",
      "missingRate": "2.1%",
      "duplicateRate": "0.4%",
      "status": "ready",
      "conversations": [
        { "id": "c1", "title": "Product Performance", "date": "2 hours ago", "messageCount": 12 },
        { "id": "c2", "title": "Sales Overview",      "date": "1 day ago",   "messageCount": 8  },
        { "id": "c3", "title": "Revenue Analysis",    "date": "2 days ago",  "messageCount": 15 }
      ]
    }
  ]
}
```

**Called by:** `src/App.jsx` (initial load), consumed by
`src/components/Sidebar.jsx:84-142` and
`src/components/DatasetOverview.jsx:113-131`.

**Notes:**
- Conversations are returned **without** their `messages` array. The mock nests
  `messages` inside `conversations` (`App.jsx:23-49`), but sending every message
  of every conversation on first paint does not scale. `Sidebar` only reads
  `conv.title`; `DatasetOverview` only reads `title`, `date`, `messageCount`.
  Messages load lazily via endpoint 10. This is the one place the contract
  deliberately returns *less* than the mock; `ChatInterface` already guards with
  `conversation?.messages || []` (`ChatInterface.jsx:16`), so an absent array is
  safe.
- `date` is a server-rendered relative string to match the mock exactly. See
  Suggested changes S2.
- Ordering: datasets by `created_at DESC` (the mock prepends new uploads,
  `App.jsx:121`); conversations by `last_message_at DESC` (the mock prepends new
  conversations, `App.jsx:149`).
- No pagination for v1. Add `?limit=&cursor=` when a user passes ~50 datasets.

---

## 4. `GET /api/datasets/{datasetId}`

A single dataset, same shape as one element of endpoint 3 (with
`conversations`). Needed because after a page refresh the frontend has no
dataset in memory.

Response `200`: identical shape to one `datasets[]` element above.
Response `404`: `NOT_FOUND`.

**Called by:** `src/App.jsx` (`handleSelectDataset`) /
`src/components/DatasetOverview.jsx`.

---

## 5. `GET /api/datasets/{datasetId}/report`

The data-preparation report. `PreprocessingReport.jsx` is today **100 %
hardcoded** — `customer_phone`, `78.4% missing`, `order_date`, `quantity`,
`2.1%`, `0.4%`, `6 checks completed`, `2 notices` are all literals in the JSX
(lines 32-143). Only `dataset.name`, `rowCount`, `colCount` come from props.

Response `200`:

```json
{
  "datasetId": "1",
  "checksCompleted": 6,
  "noticeCount": 2,
  "qualityScore": "97.9%",
  "qualityLabel": "Good",
  "excludedColumnCount": 1,
  "convertedColumnCount": 2,
  "checks": [
    { "order": 1, "level": "success", "title": "File validation", "summary": "CSV file loaded successfully." },
    { "order": 2, "level": "success", "title": "Dataset size",    "summary": "2,384 rows • 8 columns" },
    { "order": 3, "level": "success", "title": "Missing values",  "summary": "Overall missing rate: 2.1% (within threshold)." },
    {
      "order": 4,
      "level": "warning",
      "title": "Column excluded from analysis",
      "summary": "This column remains in the original dataset but will not be used for analysis.",
      "excludedColumns": [ { "name": "customer_phone", "reason": "78.4% missing" } ]
    },
    {
      "order": 5,
      "level": "info",
      "title": "Data type conversion",
      "summary": null,
      "conversions": [
        { "name": "order_date", "from": "object", "to": "datetime", "successRate": "99.7% converted" },
        { "name": "quantity",   "from": "object", "to": "int64",    "successRate": "100% converted" }
      ]
    },
    { "order": 6, "level": "success", "title": "Duplicate rows", "summary": "0.4% detected (below threshold)." }
  ]
}
```

**Called by:** `src/components/PreprocessingReport.jsx` (via `src/App.jsx`
`currentView === 'report'`). The "Data Quality" card in
`src/components/DatasetOverview.jsx:143-168` uses `qualityScore`,
`qualityLabel`, `excludedColumnCount` and `convertedColumnCount` from the same
response (all hardcoded there today).

**Notes:**
- `level` drives the existing icon/border styling: `success` → green
  `CheckCircle2`, `warning` → amber `AlertCircle` + left bar, `info` → blue
  `Info` + left bar, `error` → red. These are exactly the variants already in
  the JSX.
- The data behind this already exists in `backend/validation.py`
  `prepare_dataframe()`, which returns `errors`, `warnings`,
  `unavailable_columns` (a `{column: "78.4% of values are missing."}` dict) and
  `conversions` (a `{column: {original_type, converted_to, success_rate}}`
  dict). This endpoint is a formatter over that output, persisted at upload
  time.
- `qualityScore` has no source in the backend yet. Proposed definition:
  `1 - overall_missing_ratio`, to one decimal. `qualityLabel` from thresholds
  (≥95 % Good, ≥85 % Fair, else Poor). Stated here so the number is not invented
  a second time in the UI.
- `successRate` is a pre-formatted string ("99.7% converted") because the JSX
  prints it verbatim. See Suggested changes S1.

---

## 6. `GET /api/datasets/{datasetId}/columns`

Feeds the **"Columns & Types"** tab, which is declared in
`DatasetOverview.jsx:12` but renders the placeholder
`"{activeTab} content will be displayed here."` (lines 194-198).

Response `200`:

```json
{
  "datasetId": "1",
  "columns": [
    { "name": "order_id",       "dtype": "int64",          "available": true,  "missingRate": "0.0%",  "exclusionReason": null },
    { "name": "order_date",     "dtype": "datetime64[ns]", "available": true,  "missingRate": "0.3%",  "exclusionReason": null },
    { "name": "product",        "dtype": "object",         "available": true,  "missingRate": "0.0%",  "exclusionReason": null },
    { "name": "quantity",       "dtype": "int64",          "available": true,  "missingRate": "0.0%",  "exclusionReason": null },
    { "name": "customer_phone", "dtype": "object",         "available": false, "missingRate": "78.4%", "exclusionReason": "78.4% of values are missing." }
  ]
}
```

**Called by:** `src/components/DatasetOverview.jsx` (new "Columns & Types" tab
body).

**Notes:** `dtype` comes straight from `backend/data_utils.py` `get_schema()`.
Excluded columns are listed with `available: false` rather than omitted, because
the Preprocessing Report promises "This column remains in the original dataset".

---

## 7. `GET /api/datasets/{datasetId}/preview?limit=5`

Feeds the **"Preview"** tab (also a placeholder today). `PROJECT_PLAN.md` §3.2
promises "the first five rows".

Response `200`:

```json
{
  "datasetId": "1",
  "columns": ["order_id", "order_date", "product", "quantity"],
  "rows": [
    { "order_id": 1001, "order_date": "2024-01-03", "product": "Laptop", "quantity": 2 },
    { "order_id": 1002, "order_date": "2024-01-03", "product": "Mouse",  "quantity": 5 }
  ],
  "totalRows": 2384
}
```

**Called by:** `src/components/DatasetOverview.jsx` (new "Preview" tab body).

**Notes:** `columns` is sent separately and ordered, because JSON object key
order must not be relied on for rendering table headers. `limit` is capped at
100 server-side. `NaN`/`NaT` serialise as `null`.

---

## 8. `GET /api/datasets/{datasetId}/conversations`

The "Conversations" tab and the "View all →" button in
`DatasetOverview.jsx:109`.

Response `200`:

```json
{
  "conversations": [
    { "id": "c1", "title": "Product Performance", "date": "2 hours ago", "messageCount": 12 }
  ]
}
```

**Called by:** `src/components/DatasetOverview.jsx` ("Conversations" tab,
"View all").

**Notes:** same objects as nested in endpoint 3. Supports `?limit=&offset=`.

---

## 9. `POST /api/datasets/{datasetId}/conversations`

Create a conversation. Replaces `handleNewConversation` (`App.jsx:143-158`),
which builds
`{ id: 'conv_' + Date.now(), title: 'New Conversation', date: 'Just now', messageCount: 0, messages: [] }`.

Request:

```json
{ "title": "New Conversation" }
```

`title` is optional; the server defaults to `"New Conversation"` to match the
mock, and renames it from the first question (see endpoint 11).

Response `201`:

```json
{ "id": "conv_8f2a", "title": "New Conversation", "date": "Just now", "messageCount": 0, "messages": [] }
```

**Called by:** `src/App.jsx` (`handleNewConversation`), triggered from
`src/components/Sidebar.jsx:124-130` and
`src/components/DatasetOverview.jsx:174-179`.

**Notes:** returns `messages: []` and `date: "Just now"` so the object can be
dropped into state unchanged, exactly as the mock does.

---

## 10. `GET /api/conversations/{conversationId}/messages`

Load a conversation's history. This is the only endpoint that returns the full
message objects from `App.jsx:23-49`.

Response `200`:

```json
{
  "conversationId": "c1",
  "title": "Product Performance",
  "datasetId": "1",
  "messages": [
    {
      "role": "user",
      "content": "Which product has the highest total quantity sold?"
    },
    {
      "role": "agent",
      "status": "ready",
      "content": "The product with the highest total quantity sold is Laptop.\nTotal quantity sold: 1,248 units.",
      "condensedQuestion": null,
      "showChart": true,
      "chartTitle": "Top 5 products by total quantity",
      "resultData": [
        { "product": "Laptop",     "quantity": 1248 },
        { "product": "Mouse",      "quantity": 986  },
        { "product": "Keyboard",   "quantity": 712  },
        { "product": "Monitor",    "quantity": 456  },
        { "product": "Headphones", "quantity": 324  }
      ],
      "plan": {
        "question": "Which product has the highest total quantity sold?",
        "steps": [
          "Group by Product",
          "Calculate SUM of Quantity",
          "Sort by total quantity (descending)",
          "Take top 1 result"
        ],
        "columnsUsed": ["Product", "Quantity"],
        "filters": "None"
      }
    }
  ]
}
```

**Called by:** `src/App.jsx` (`handleSelectConversation`), rendered by
`src/components/ChatInterface.jsx:65-182`.

**Notes:**
- Field by field this is byte-compatible with the mock message objects, plus two
  additive fields the mock has no slot for: `status` and `condensedQuestion`.
- **`condensedQuestion`** (agent messages only) is the standalone question the
  condenser produced, stored in `messages.condensed_question`. The UI renders it
  above the answer as *"Understood as: …"*. It is `null` for the first message of
  a conversation (condensation is skipped — there is no history to resolve) and
  `null` when the user's question was already standalone and passed through
  unchanged. **Render the line only when the value is non-null and differs from
  the preceding user message**, otherwise every turn gets a redundant echo. It
  must come back from this endpoint, not only from the stream, or the line
  vanishes on a page reload.
- `resultData` is an array of row objects with **arbitrary column names**.
  `ChatInterface.jsx` hardcodes `row.product` / `row.quantity` and the Recharts
  `dataKey="product"` / `dataKey="quantity"` (lines 101-127). The *data shape*
  is already generic; the *component* is not. See Suggested changes S3 — this is
  the single biggest frontend change required.
- `plan.filters` is a human string (`"None"`, or `"Country = Palestine"`),
  matching the mock and `PROJECT_PLAN.md` §5.
- `plan.steps` are English sentences, not raw tool JSON. The backend's
  `analysis_plan` is a list of
  `{"tool": "aggregate_data", "column": "Quantity", "operation": "sum", "group_by": "Product"}`
  dicts; the server renders them into these strings so the UI stays dumb.
- Messages with `status` `needs_clarification` / `cannot_answer` carry only
  `role` + `content` (no `resultData`, no `plan`), which the UI already handles
  because every result block is guarded (`msg.resultData &&`, `msg.plan &&`).
- Supports `?limit=&before=` for long conversations; by default returns the
  whole conversation.

---

## 11. `POST /api/conversations/{conversationId}/messages`

The **non-streaming** chat endpoint: ask a question, get the finished answer in
one JSON response. It and endpoint 11b drain the **same** async generator
(`analysis_service.run_turn()`, `PLAN.md` §6B) — this one discards every
intermediate event and returns only the final message, so the two can never
drift apart.

**Who uses it:** `/docs`, `curl`, and the integration tests. **The frontend uses
11b**, not this. It exists because asserting on a turn is far easier against one
JSON body than against a parsed event stream, and because a browsable `/docs`
that can actually run a question is worth keeping.

Request:

```json
{ "content": "Which product has the highest total quantity sold?" }
```

Response `201` — the agent message in the same shape as an `agent` message
above, plus `status` and the conversation metadata the sidebar needs:

```json
{
  "conversation": {
    "id": "c1",
    "title": "Which product has the h...",
    "date": "Just now",
    "messageCount": 2
  },
  "message": {
    "role": "agent",
    "status": "ready",
    "content": "The product with the highest total quantity sold is Laptop.\nTotal quantity sold: 1,248 units.",
    "condensedQuestion": null,
    "showChart": true,
    "chartTitle": "Top 5 products by total quantity",
    "resultData": [
      { "product": "Laptop", "quantity": 1248 }
    ],
    "plan": {
      "question": "Which product has the highest total quantity sold?",
      "steps": ["Group by Product", "Calculate SUM of Quantity", "Sort by total quantity (descending)", "Take top 1 result"],
      "columnsUsed": ["Product", "Quantity"],
      "filters": "None"
    }
  }
}
```

Clarification `201` (the agent needs more information):

```json
{
  "conversation": { "id": "c1", "title": "Show me the best", "date": "Just now", "messageCount": 2 },
  "message": {
    "role": "agent",
    "status": "needs_clarification",
    "content": "Do you mean the highest total quantity sold, or the highest total revenue?",
    "showChart": false,
    "resultData": null,
    "plan": null
  }
}
```

Out of scope `201`:

```json
{
  "conversation": { "id": "c1", "title": "Predict next year", "date": "Just now", "messageCount": 2 },
  "message": {
    "role": "agent",
    "status": "cannot_answer",
    "content": "Forecasting is not supported. The dataset has no future-dated rows to project from.",
    "showChart": false,
    "resultData": null,
    "plan": null
  }
}
```

**Called by:** `src/App.jsx` (`handleSendMessage`), UI state driven by
`src/components/ChatInterface.jsx:22-34` (`handleSend`, `isAnalyzing`).

**Notes:**
- **The server persists both messages.** The request contains only the user's
  text; the backend writes the `user` row, runs the agent, writes the `agent`
  row, and returns the agent row. The frontend must therefore not treat its
  optimistic local append as authoritative.
- `conversation.title` is auto-renamed from the first question. The mock does
  `text.substring(0, 25) + '...'` (`App.jsx:169`); the server does the same so
  the sidebar label matches.
- `condensedQuestion` is the standalone question the condenser produced, or
  `null` on a first message / a pass-through. Same semantics as endpoint 10.
- This call is slow: up to **three** sequential LLM round-trips (condenser,
  planner, explainer) plus a possible planner retry, plus a Neon cold start.
  Budget 5-30 s. Set Render's request timeout above 60 s. This latency is the
  reason endpoint 11b exists.
- `502 LLM_UNAVAILABLE` when the provider fails or returns unparseable JSON
  after retries. The user message is still persisted **and an agent message with
  `status: "failed"` is written**, so a conversation never holds a user message
  with no reply.

---

## 11b. `POST /api/conversations/{conversationId}/messages/stream`

**The endpoint the frontend actually uses.** Same input, same work, same final
message as endpoint 11 — delivered as Server-Sent Events while it happens, so
the user sees the pipeline progress, then the table and chart, then the answer
typing in.

### Request

```
POST /api/conversations/c1/messages/stream
Content-Type: application/json
X-Session-Id: 3f9a1c22-8d4e-4b17-9c03-6e2a7b514d88
Accept: text/event-stream

{ "content": "now show it per month" }
```

**Why POST and not `EventSource`:** `EventSource` can only issue a `GET` and
cannot set request headers, so it could carry neither the question body nor
`X-Session-Id`. The client uses `fetch()` and reads `response.body` as a
`ReadableStream`, parsing the SSE framing itself in `src/api/stream.js`.

### Response headers

```
200 OK
Content-Type:      text/event-stream; charset=utf-8
Cache-Control:     no-cache, no-transform
Connection:        keep-alive
X-Accel-Buffering: no
```

`no-transform` and `X-Accel-Buffering: no` are the two that actually stop
nginx-family proxies from buffering the response. Without them everything
arrives at once at the end, and the code looks broken when it is not. Do **not**
gzip this response — compression implies buffering. A heartbeat comment line
(`: ping\n\n`) is sent every 15 s so an idle proxy does not close the connection
while the planner is thinking; clients must ignore lines beginning with `:`.

### Wire format

Standard SSE: an `event:` line, a `data:` line holding compact JSON, then a
blank line.

```
event: status
data: {"stage":"planning","label":"Building analysis plan"}

```

### Events

| Event | Payload | When | Count |
|---|---|---|---|
| `status` | `{stage, label}` | entering each pipeline stage | 1 per stage |
| `condensed` | `{question}` | after condensation | 0 or 1 |
| `result` | `{resultData, resultKind, chartPlan, plan}` | after the analysis runs **and** the chart is validated | 0 or 1 |
| `token` | `{text}` | each chunk of the answer text | many |
| `done` | `{conversation, message}` | after the agent message is persisted | 0 or 1 |
| `error` | `{code, message}` | terminal failure | 0 or 1 |

`stage` is one of `condensing`, `planning`, `validating`, `executing`,
`explaining` — the **real** pipeline stages, replacing the three decorative
steps hardcoded in `ChatInterface.jsx:184-204`. `label` is the display string,
so wording changes need no frontend deploy.

Guarantees the client can rely on:

- Exactly one of `done` or `error` ends the stream. If the connection closes
  without either, treat it as a drop.
- `result` always precedes the first `token`. This is deliberate: the table and
  chart **are** the answer, the sentence is commentary. The user reads the data
  while the prose types in, which makes a 15 s turn feel like a 3 s one.
- `condensed` is **absent** on the first message of a conversation (condensation
  is skipped — nothing to resolve) and absent when `CONDENSER_ENABLED=false`.
- `done.message` is byte-identical to the `message` object from endpoint 11, and
  `done.message.content` equals every `token.text` concatenated. The client
  should **replace** its accumulated text with `done.message.content` rather
  than trust its own concatenation.
- `result` is absent for `needs_clarification` and `cannot_answer` turns.

### Full example sequence — a successful follow-up

User sends `"now show it per month"` in a conversation that already has history.

```
event: status
data: {"stage":"condensing","label":"Understanding your question"}

event: condensed
data: {"question":"Show total quantity per product per month for 2024"}

event: status
data: {"stage":"planning","label":"Building analysis plan"}

event: status
data: {"stage":"validating","label":"Checking the plan"}

event: status
data: {"stage":"executing","label":"Running analysis"}

event: result
data: {"resultKind":"table","resultData":[{"month":"2024-01","quantity":1420},{"month":"2024-02","quantity":1610},{"month":"2024-03","quantity":1735}],"chartPlan":{"shouldPlot":true,"chartType":"line","x":"month","y":"quantity"},"plan":{"question":"Show total quantity per product per month for 2024","steps":["Keep only rows where order_date is on or after 2024-01-01","Group by month","Calculate SUM of quantity","Sort by month (ascending)"],"columnsUsed":["order_date","quantity"],"filters":"order_date >= 2024-01-01"}}

event: status
data: {"stage":"explaining","label":"Writing the answer"}

event: token
data: {"text":"Quantity"}

event: token
data: {"text":" rose steadily"}

event: token
data: {"text":" through Q1 2024,"}

event: token
data: {"text":" peaking in March at 1,735 units."}

event: done
data: {"conversation":{"id":"c1","title":"Product Performance","date":"Just now","messageCount":8},"message":{"role":"agent","status":"ready","content":"Quantity rose steadily through Q1 2024, peaking in March at 1,735 units.","condensedQuestion":"Show total quantity per product per month for 2024","showChart":true,"chartTitle":"Total quantity per month","resultKind":"table","resultData":[{"month":"2024-01","quantity":1420},{"month":"2024-02","quantity":1610},{"month":"2024-03","quantity":1735}],"plan":{"question":"Show total quantity per product per month for 2024","steps":["Keep only rows where order_date is on or after 2024-01-01","Group by month","Calculate SUM of quantity","Sort by month (ascending)"],"columnsUsed":["order_date","quantity"],"filters":"order_date >= 2024-01-01"}}}

```

### First message of a conversation

No `condensing` stage and no `condensed` event:

```
event: status
data: {"stage":"planning","label":"Building analysis plan"}
...
```

### Clarification

The clarification text is sent as `token` events, so the client's rendering path
is identical to a normal answer. No `result`, and **no explainer call** — there
is nothing to explain.

```
event: status
data: {"stage":"condensing","label":"Understanding your question"}

event: condensed
data: {"question":"Show me the best product"}

event: status
data: {"stage":"planning","label":"Building analysis plan"}

event: token
data: {"text":"Do you mean the highest total quantity sold, or the highest total revenue?"}

event: done
data: {"conversation":{"id":"c1","title":"Show me the best produ...","date":"Just now","messageCount":4},"message":{"role":"agent","status":"needs_clarification","content":"Do you mean the highest total quantity sold, or the highest total revenue?","condensedQuestion":"Show me the best product","showChart":false,"resultData":null,"plan":null}}

```

`cannot_answer` is identical with that status and the reason as the text.

### Failure mid-stream

```
event: status
data: {"stage":"planning","label":"Building analysis plan"}

event: error
data: {"code":"LLM_UNAVAILABLE","message":"The analysis service did not respond. Your question was saved — please try again."}

```

The HTTP status is already `200` at this point and cannot be changed, which is
why the error arrives as an event. Before the stream opens, failures are
ordinary HTTP errors with the normal envelope — `400 SESSION_REQUIRED`,
`404 NOT_FOUND`, `400 VALIDATION_ERROR` for an empty question.

### Persistence and the invariant

- The **user message is persisted before the first event is emitted.** A
  question is never lost, whatever happens next.
- The **agent message is persisted exactly once**, immediately before `done`.
- On any failure after the user message, an agent message with
  `status: "failed"` is written and `error` is emitted. **A conversation can
  never contain a user message with no reply** — that is the invariant.

### Client disconnect

If the client goes away mid-stream, **the turn still completes and the agent
message is still persisted.** The pipeline runs as its own task writing into a
queue that the response drains, so cancelling the response does not cancel the
work (`PLAN.md` §6B). Consequences for the client: reopening the conversation
shows the finished answer, and a user who closes the tab and comes back has lost
nothing. Rationale: on a free LLM tier, abandoning a turn whose calls are
already paid for is the worst of both outcomes.

### Testing it

```bash
curl -N -X POST http://127.0.0.1:8000/api/conversations/<id>/messages/stream \
  -H 'Content-Type: application/json' -H 'X-Session-Id: <uuid>' \
  -d '{"content":"Which product has the highest total quantity sold?"}'
```

`-N` disables curl's own buffering. **Events must appear one at a time over
several seconds.** If they all arrive together at the end, the problem is
buffering, not the code.

**Run this against the deployed Render URL too, not only locally.** Local
uvicorn has no proxy in front of it, so streaming always looks perfect on your
machine; Render puts a proxy in the path, and that is exactly where streaming
breaks. Check it in a browser as well, because CORS applies to this response
like any other — and `X-Session-Id` must be in `allow_headers` or the preflight
fails before the stream ever opens.

**Called by:** `src/api/stream.js` (the SSE parser and async iterator), driven
from `src/App.jsx` (`handleSendMessage`), rendered by
`src/components/ChatInterface.jsx`. **No component touches the stream directly.**

**Client notes:**
- Buffer across chunk boundaries. A `data:` line can be split between two
  `ReadableStream` reads; a parser that does not carry its buffer over works on
  a fast local connection and fails on a slow network. This is the classic SSE
  client bug.
- Ignore lines starting with `:` (heartbeats) and unknown `event:` types, so
  adding an event later cannot break an older client.
- Apply an **idle timeout** of ~45 s with no event, and surface it as an error.
  A stalled stream is otherwise indistinguishable from a slow one, and the
  current UI would spin forever.

---

## 12. `PATCH /api/conversations/{conversationId}`

Rename a conversation. Supports the `MoreHorizontal` menu
(`DatasetOverview.jsx:49-51`), currently a dead button.

Request: `{ "title": "Q4 product performance" }` → Response `200`: the
conversation object. Low priority; include only if you want the dead buttons to
work.

---

## 13. `DELETE /api/datasets/{datasetId}`

Delete a dataset and cascade to its conversations and messages. Also behind the
dead `MoreHorizontal` button. Response `204`.

**Notes:**
- Destructive; the UI must confirm first. Not required for a working v1.
- **The Postgres cascade does not reach the object store.** The service deletes
  the Parquet object first, then the row, so the failure that can happen is the
  recoverable one (a row pointing at a missing object) rather than the invisible
  one (an object no row points at). `PLAN.md` §4 has the ordering argument.
- **"Deleted" is not "erased."** Neon Object Storage's `DeleteObject` is a *soft*
  delete on the branch, so the object remains retrievable and the storage is not
  reclaimed. The UI must not promise erasure — "removed from your workspace" is
  accurate, "permanently deleted" is not.
- Still returns `204` when the object delete failed but the row was removed; the
  failure is logged, not surfaced, because there is nothing the user can do
  about it and the dataset is genuinely gone from their view.

---

## 14. `GET /api/conversations?q=<text>`

Backs the sidebar's **non-functional** search input (`Sidebar.jsx:69-76` — no
`value`, no `onChange`, no handler).

Response `200`:

```json
{
  "conversations": [
    { "id": "c1", "datasetId": "1", "datasetName": "orders.csv", "title": "Product Performance", "date": "2 hours ago", "messageCount": 12 }
  ]
}
```

**Called by:** `src/components/Sidebar.jsx`.

**Notes:** v1 can be `ILIKE '%q%'` on `conversations.title` plus
`messages.content`. Postgres full-text search (`tsvector`) only if that proves
too slow. Lowest priority of all endpoints — the input is cosmetic today.

---

## 15. `GET /api/me` — **not built**

Would have backed the sidebar footer, which hardcodes the avatar `U`,
`"User Name"` and `"user@example.com"` (`Sidebar.jsx:150-156`).

**Resolved by decision Q1(d): there are no user accounts, so there is no
`/api/me`.** An anonymous session has no name and no email, and an endpoint that
returned a placeholder would be a fake dressed as an API.

What to do in feature 6 instead: replace the hardcoded name and email with
something true — a generic label, or the session's dataset count — and keep the
Settings button inert. When accounts arrive, this endpoint returns and the
footer becomes real.

---

## Endpoint ↔ frontend map

| Frontend file | Mock it replaces | Endpoints |
|---|---|---|
| `src/App.jsx` | `MOCK_DATASETS` (l. 11-73) | 3 |
| `src/App.jsx` | `handleFileUpload` (l. 98-127) | 2 |
| `src/App.jsx` | `handleNewConversation` (l. 143-158) | 9 |
| `src/App.jsx` | `handleSendMessage` (l. 160-201) | **11b** (11 is for tests and `/docs` only) |
| `src/App.jsx` | `handleSelectConversation` (l. 136-141) | 10 |
| `src/api/session.js` *(new)* | — generates and stores `X-Session-Id` | all |
| `src/api/stream.js` *(new)* | the fake `isAnalyzing` progress (l. 28-33) | 11b |
| `src/components/Sidebar.jsx` | `datasets` prop, dead search, fake user | 3, 14; **15 not built** |
| `src/components/WelcomeScreen.jsx` | `onFileUpload` prop | 2 |
| `src/components/DatasetOverview.jsx` | quality card + 4 placeholder tabs | 4, 5, 6, 7, 8 |
| `src/components/ChatInterface.jsx` | `conversation.messages`, hardcoded 3-step progress (l. 184-204) | 10, **11b** |
| `src/components/PreprocessingReport.jsx` | entire hardcoded body (l. 32-143) | 5 |
| `src/components/DatasetRejected.jsx` | unpassed props + hardcoded fallbacks | 2 (422) |

---

## Suggested changes

Each of these would make the backend cleaner. The contract above still matches
the mock so the frontend changes stay small; these are deliberate, separate
frontend edits.

**Status after revision 2:**

| | Change | Status |
|---|---|---|
| S1 | numbers instead of formatted strings | **not adopted** — contract keeps `"45 KB"`, `"2.1%"` |
| S2 | ISO timestamps instead of `"2 hours ago"` | **not adopted** — contract keeps `date` |
| S3 | column-agnostic table and chart | **accepted**, scheduled in feature 6 |
| S4 | explicit scalar results | **accepted**, scheduled in feature 6 (`resultKind` is already in the 11b events) |
| S5 | real streaming progress | **adopted as a requirement** — now endpoint 11b, built in feature 5.5. No longer a suggestion |
| S6 | split dataset and conversation lists | **not adopted** — revisit at scale |

**S1 — Send numbers, not pre-formatted strings.**
The mock uses `size: '45 KB'`, `missingRate: '2.1%'`,
`duplicateRate: '0.4%'`, `successRate: '99.7% converted'`. A backend should
send `sizeBytes: 46080`, `missingRate: 0.021`, `successRate: 0.997` and let the
UI format.
*Reason:* formatting in the API hardcodes locale and precision in Python, makes
the values unusable for sorting or thresholds, and means a display tweak needs a
backend deploy. *Cost:* one `formatBytes`/`formatPercent` helper in the
frontend, used in about five places.

**S2 — Send ISO timestamps, not relative strings.**
Replace `date: "2 hours ago"` with `updatedAt: "2026-11-10T08:14:22Z"`.
*Reason:* "2 hours ago" is wrong the moment it is cached or the tab is left
open, and it depends on the server's clock and locale rather than the viewer's.
*Cost:* `Intl.RelativeTimeFormat` in `Sidebar` and `DatasetOverview`.

**S3 — Make the result table and chart column-agnostic. (accepted, feature 6)**
Add to each agent message:

```json
{
  "resultColumns": [
    { "key": "product",  "label": "Product",             "type": "category" },
    { "key": "quantity", "label": "Total Quantity Sold", "type": "number"   }
  ],
  "chart": { "type": "bar", "x": "product", "y": "quantity", "title": "Total Quantity Sold by Product" }
}
```

*Reason:* `ChatInterface.jsx` hardcodes `row.product`, `row.quantity`, the
`<th>` labels `Product` / `Total Quantity Sold`, the chart title, and
`dataKey="product"` / `dataKey="quantity"`. **The real agent answers questions
about any CSV**, so a question about `customers.csv` renders an empty table
today. The backend already has everything needed: `chart_plan` is
`{should_plot, chart_type, x, y}` (`backend/agent/schemas.py:93-98`) and
`get_schema()` gives dtypes. *Cost:* rewrite the `<table>` and `<BarChart>`
blocks to map over `resultColumns`, and switch on `chart.type` for the four
supported types (`bar`, `line`, `pie`, `scatter`) — only `bar` exists in the
component now. Without this the app is a demo, not a product.

**S4 — Return scalar answers explicitly. (accepted, feature 6)**
`aggregate_data` without `group_by` returns a **scalar**, not a table
(`backend/tools.py:63-80`, `backend/agent/validators.py:240-249`). The mock has
no shape for that; the UI would try to `.map()` over a number. Add
`resultKind: "scalar" | "table"` and `resultValue: 1248`.
*Reason:* "What is the average price?" is a primary use case —
`backend/agent/prompts.py:72-90` has exactly that as its first example — and it
would render blank or throw. *Cost:* one conditional branch in `ChatInterface`.
**This one is close to mandatory:** it is a crash, not a polish item.

**S5 — Real progress. ADOPTED — see endpoint 11b.**
No longer a suggestion. The decorative three-step indicator is replaced by real
`status` events from the pipeline, plus `condensed`, `result` and token-by-token
`token` events. Two differences from what this entry originally proposed: it is
a `POST` on `.../messages/stream` rather than a `GET` on a sub-resource (an
`EventSource` `GET` cannot carry the question body or `X-Session-Id`), and the
answer text itself streams, not just the stage labels. Built in feature 5.5;
full design in `PLAN.md` §6B.

**S6 — Separate dataset list from conversation list.**
Endpoint 3 nests `conversations` inside each dataset because `Sidebar` expects
it. Two endpoints (`/datasets`, `/datasets/{id}/conversations`) would let the
sidebar lazy-load on expand.
*Reason:* with 20 datasets × 30 conversations the first paint carries 600
objects nobody has clicked. *Cost:* small — `Sidebar` already has an
`expandedId` state (`Sidebar.jsx:15`) to hang the fetch off. Not urgent at your
scale.
