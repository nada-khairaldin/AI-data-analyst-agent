# Deploy

Backend on Render, frontend on Vercel. Do the backend first: the frontend
needs its URL, and the backend needs the frontend's origin for CORS.

---

## 1. Render — backend

### Create the service

1. <https://dashboard.render.com> → **New** → **Web Service**.
2. Connect the GitHub repo `nada-khairaldin/AI-data-analyst-agent`, branch
   **`main`**.
3. Settings:

   | Field | Value |
   |---|---|
   | Name | `data-analysis-agent-api` |
   | Language | **Python 3** |
   | Region | **Ohio (US East)** |
   | Branch | `main` |
   | **Root Directory** | **`backend`** |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Instance Type | Free |

   `--host 0.0.0.0` matters: bound to `127.0.0.1` the service is unreachable
   from outside the container. `$PORT` is assigned by Render — do not hardcode
   8000.

4. **Advanced** → **Health Check Path**: `/health`.

### Environment variables

Add these under **Environment**. Values come from `backend/.env` on your
machine — copy them across; none of them are in the repo.

| Name | Where it comes from |
|---|---|
| `PYTHON_VERSION` | **leave unset** — see the note below |
| `DATABASE_URL` | Neon **pooled** string (host contains `-pooler`) |
| `DATABASE_URL_DIRECT` | Neon **direct** string (no `-pooler`) |
| `AWS_ENDPOINT_URL_S3` | Neon Object Storage endpoint |
| `AWS_ACCESS_KEY_ID` | Neon storage credential |
| `AWS_SECRET_ACCESS_KEY` | Neon storage credential |
| `AWS_REGION` | `us-east-2` |
| `NEON_STORAGE_BUCKET` | `dataset` — singular |
| `GEMINI_API_KEY` | Google AI Studio key |
| `CORS_ALLOWED_ORIGINS` | the Vercel URL — set in step 3 below |
| `ENVIRONMENT` | `production` |
| `LOG_LEVEL` | `INFO` |
| `LLM_DEV_CACHE` | `false` |

Everything else has a working default in `app/config.py`.

Two of these are easy to get wrong and both fail in confusing ways:

- **`NEON_STORAGE_BUCKET` is `dataset`, singular.** Plural gives a bare 404
  from `HeadBucket` with nothing to say the name is the problem.
- **`LLM_DEV_CACHE` must be `false`.** `app/config.py` refuses it in
  production anyway (`dev_cache_enabled` ANDs the flag with
  `not is_production`), so this is belt and braces — a cached answer served to
  a real user looks perfectly fine and was computed for someone else's
  dataset.

### The Python version — do not pin it unless a build log tells you to

**Leave `PYTHON_VERSION` unset and do not add a `runtime.txt`.**

A `runtime.txt` pinning 3.13.4 was committed and then removed. The removal
still stands, but the reason first given for it was wrong: the "outage" that
prompted it was a **wrong hostname** being tested, not the pin. The real
service deployed every push fine. The pin is still not worth having — the
project is verified on 3.14.5, not 3.13 — but nothing here ever broke
because of it.

The project is developed and tested on **3.14.5** (`.python-version`, all 390
tests). If you ever do need to pin, use that, and read the Render build log
first — the failure mode to look for is a C extension (pandas, pyarrow,
asyncpg) with no wheel for the chosen version, which falls back to a source
build that will not finish on a free instance.

### Then

Deploy and open `https://<your-service>.onrender.com/health`. Expected:

```json
{"status":"ok","database":"ok","storage":"ok","version":"0.1.0"}
```

`503` with `"database":"unreachable"` means `DATABASE_URL` is wrong or the
Neon compute is cold — the probe allows 15s, and a first request after
autosuspend can take longer. Reload once.

`"storage":"unreachable"` comes back with a `storageDetail` naming the
botocore code; `HeadBucket failed: 404` is the bucket name.

**Note:** `/docs` is disabled when `ENVIRONMENT=production`. Set it to
`development` temporarily if you want the browsable API on the deployed
instance.

**Free instance:** spins down after ~15 minutes idle, and the next request
takes 30-60s to wake. Open `/health` once before demoing.

### Migrations

The schema is already applied to Neon `main` from your machine, so there is
nothing to run. If you ever need to:

```bash
cd backend && alembic upgrade head     # uses DATABASE_URL_DIRECT, never the pooler
```

Do not add this to the Render build command: it would run on every deploy
against the pooled URL's sibling and is not idempotent in a useful way here.

---

## 2. Vercel — frontend

1. <https://vercel.com/new> → import the same repo.
2. Settings:

   | Field | Value |
   |---|---|
   | Framework Preset | **Vite** |
   | **Root Directory** | **`frontend`** |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |

3. **Environment Variables** → add:

   | Name | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://<your-render-service>.onrender.com` |

   No trailing slash. It must be `VITE_`-prefixed or Vite will not expose it
   to the bundle — and remember every `VITE_` variable is compiled into the
   **public** bundle, so never put a secret behind that prefix.

4. Deploy.

---

## 3. Back to Render — CORS

Once Vercel gives you the URL, set on Render:

```
CORS_ALLOWED_ORIGINS = https://<your-project>.vercel.app
```

Scheme included, no trailing slash, comma-separated for more than one. To keep
local development working alongside it:

```
CORS_ALLOWED_ORIGINS = https://<your-project>.vercel.app,http://localhost:5173
```

**Both origins are needed if you ever point a local `npm run dev` at the
deployed backend.** Verified against the live service: the Vercel origin is
allowed and `http://localhost:5173` is **not**, so a local frontend talking to
Render is blocked by CORS until localhost is added to the list. Use
`http://localhost:5173` exactly — `127.0.0.1:5173` is a different origin to a
browser and needs its own entry.

Redeploy the Render service (an env var change triggers one).

`"*"` will **not** work here, and the browser will not tell you why in a
useful way. `X-Session-Id` is a custom header, so every request is preceded by
a preflight; it is already in `allow_headers`, but the origin has to match
exactly or the preflight fails while `curl` keeps working.

---

## Quick verification

```bash
# backend alone
curl https://<service>.onrender.com/health

# a real upload, end to end
curl -H "X-Session-Id: $(uuidgen)" \
     -F "file=@samples/orders.csv;type=text/csv" \
     https://<service>.onrender.com/api/datasets
```

Then the frontend: upload `samples/orders.csv`, open the dataset, read the
preprocessing report, start a conversation, ask
*"Which product has the highest total quantity sold?"*

`samples/bad.csv` should be rejected with the missing-values screen.


---

## If Render is down and you need to demo now

The frontend talks to whatever `VITE_API_BASE_URL` points at, so running
everything locally is a two-terminal fallback and needs no code change.

```bash
# terminal 1 — backend
cd backend
LLM_DEV_CACHE=true ../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8100
# wait for: Application startup complete.  (Neon cold start can take ~45s)
curl http://127.0.0.1:8100/health

# terminal 2 — frontend
cd frontend
# point it at the local backend instead of Render
echo "VITE_API_BASE_URL=http://127.0.0.1:8100" > .env
npm run dev          # http://localhost:5173
```

`http://localhost:5173` is already in `CORS_ALLOWED_ORIGINS` on Render, and the
local backend's own default allows it too, so nothing else changes.

`LLM_DEV_CACHE=true` is what makes the demo cheap: the four questions from the
phase C run are already cached, so re-asking them costs **0** Gemini calls
against the 20-per-day limit. Ask something new and it costs ~3.

Put `.env` back to the Render URL afterwards:

```bash
echo "VITE_API_BASE_URL=https://ai-data-analyst-agent-br1d.onrender.com" > frontend/.env
```

### Diagnosing the Render service itself

What "down" looked like from outside, for comparison:

```
* ALPN: server accepted http/1.1
> GET /health HTTP/1.1
* Operation timed out after 40010 ms with 0 bytes received
```

TLS completes and the request is sent, then nothing. Render's edge is up and
the application behind it is not answering — a failed build, or a start
command that crash-loops. The edge holds the connection open, which is why
there is no 502 to read.

Check, in this order:

1. **Events** tab — did a deploy run at all? If auto-deploy is off, a push
   changes nothing and the service is still on the old commit.
2. **Logs** tab — the build log for a failed wheel, and the runtime log for a
   traceback on startup. A missing env var surfaces here, not at build time.
3. **Manual Deploy → Clear build cache & deploy**, which is the quickest way
   to rule out a half-written cache.

Also worth knowing: DNS puts this service in **gcp-us-west1**, not Ohio. It
works, but every database query crosses the country to Neon in `us-east-2`.
Recreating it in Ohio would cut a noticeable amount of latency off every
request.
