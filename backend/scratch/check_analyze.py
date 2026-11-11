"""Run the real /api/analyze pipeline over a fixed set of questions.

Run from backend/:  python scratch/check_analyze.py

This is the end-to-end check that the model swap actually works: upload a
sample CSV through the real endpoint, ask real questions, and report for each
one what the model emitted, whether it passed validation first time or needed
the retry, and what the user would see.

It records every LLM call by wrapping the two call sites, so the total is a
real count rather than an estimate — which matters on a free tier where the
per-minute limit is the thing most likely to break a demo.

Deliberately reports failures instead of working around them. If the planner
emits an invalid plan, that is the result; the prompt is not this script's
business.
"""

import json
import os
import sys
import time
import warnings

sys.path.insert(0, ".")

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from app.agent import core, explainer  # noqa: E402
from app.agent.llm import FAST, PLANNER  # noqa: E402
from app.main import app  # noqa: E402

SAMPLES = "../samples"

# Seconds to wait between questions; see the note in main().
PAUSE = float(os.environ.get("PAUSE", "30"))

# "1,2,3" runs only the first three. Default: all of them.
ONLY = [int(x) for x in os.environ.get("ONLY", "").split(",") if x.strip()]

QUESTIONS = [
    ("orders.csv", "Which product has the highest total quantity sold?", "ready"),
    ("orders.csv", "What is the average price?", "ready (scalar)"),
    ("orders.csv", "Show me the best", "needs_clarification"),
    ("orders.csv", "Predict next year's sales", "cannot_answer"),
    ("customers.csv", "Which country has the most customers?", "ready"),
    (
        "customers.csv",
        "What is the total amount spent by Enterprise customers?",
        "ready",
    ),
]

# Every LLM call made, as (role, chars_in, chars_out).
calls = []
# Raw planner outputs for the question currently running.
planner_outputs = []
# Real provider attempts (one per model tried) and dev-cache hits.
counters = {"provider_attempts": 0, "cache_hits": 0, "models_used": []}


def instrument():
    """Wrap the two call sites, the provider attempt, and the cache.

    core.py and explainer.py each imported `complete` into their own
    namespace, so patching app.agent.llm.complete would not be seen by
    either. The names have to be replaced where they are used.

    `_attempt` is wrapped separately because it is the only place a request
    actually leaves the process — counting `complete` calls would count cache
    hits as provider traffic, which is exactly the number under test.
    """
    from app.agent import dev_cache, llm

    real_core = core.complete
    real_explainer = explainer.complete
    real_attempt = llm._attempt
    real_cache_get = dev_cache.get

    def core_complete(prompt, *, role=PLANNER):
        out = real_core(prompt, role=role)
        calls.append((role, len(prompt), len(out or "")))
        planner_outputs.append(out)
        return out

    def explainer_complete(prompt, *, role=FAST):
        out = real_explainer(prompt, role=role)
        calls.append((role, len(prompt), len(out or "")))
        return out

    def counting_attempt(model, role, operation, what):
        counters["provider_attempts"] += 1
        counters["models_used"].append(model)
        return real_attempt(model, role, operation, what)

    def counting_cache_get(model, prompt):
        out = real_cache_get(model, prompt)
        if out is not None:
            counters["cache_hits"] += 1
        return out

    core.complete = core_complete
    explainer.complete = explainer_complete
    llm._attempt = counting_attempt
    dev_cache.get = counting_cache_get
    llm.dev_cache.get = counting_cache_get


def dev_cache_stats():
    from app.agent import dev_cache

    s = dev_cache.stats()
    return f"enabled={s['enabled']} entries={s['entries']}"


def upload(client, filename):
    with open(f"{SAMPLES}/{filename}", "rb") as handle:
        response = client.post(
            "/api/upload", files={"file": (filename, handle.read(), "text/csv")}
        )
    body = response.json()
    if body.get("status") != "success":
        raise SystemExit(f"upload of {filename} failed: {body}")
    return body["session_id"]


def shorten(text, limit=300):
    if text is None:
        return "None"
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + " …"


def main():
    instrument()
    client = TestClient(app)

    sessions = {}
    results = []

    selected = [
        q for n, q in enumerate(QUESTIONS, 1) if not ONLY or n in ONLY
    ]

    for filename, question, expected in selected:
        if filename not in sessions:
            sessions[filename] = upload(client, filename)

        planner_outputs.clear()
        before = len(calls)
        started = time.monotonic()

        response = client.post(
            "/api/analyze",
            json={"session_id": sessions[filename], "query": question},
        )
        elapsed = time.monotonic() - started
        body = response.json()

        planner_calls = sum(1 for role, _, _ in calls[before:] if role == PLANNER)

        print("=" * 72)
        print(f"FILE      {filename}")
        print(f"QUESTION  {question}")
        print(f"EXPECTED  {expected}")
        print(f"HTTP      {response.status_code}   {elapsed:.1f}s")
        print(f"ATTEMPTS  {planner_calls} planner call(s) -> "
              f"{'passed on attempt 1' if planner_calls == 1 else f'passed/failed on attempt {planner_calls}'}")
        print()
        for index, raw in enumerate(planner_outputs, 1):
            print(f"RAW PLANNER OUTPUT (attempt {index}):")
            print(f"  {shorten(raw, 600)}")
        print()
        print(f"STATUS    {body.get('status')}")
        print(f"MESSAGE   {shorten(body.get('message'))}")
        print(f"ANSWER    {shorten(body.get('answer'))}")
        if body.get("analysis_plan"):
            print(f"PLAN      {json.dumps(body['analysis_plan'])}")
        if body.get("result_data") is not None:
            print(f"RESULT    {shorten(json.dumps(body['result_data']), 200)}")
        if body.get("details"):
            print(f"DETAILS   {shorten(body['details'])}")
        print()

        results.append(
            {
                "file": filename,
                "question": question,
                "expected": expected,
                "http": response.status_code,
                "attempts": planner_calls,
                "status": body.get("status"),
                "answer": body.get("answer") or body.get("message"),
                "seconds": round(elapsed, 1),
            }
        )

        # Be gentle with the free tier's per-minute limit between questions.
        # 2s was not enough: a run with that spacing got HTTP 429 on two of
        # six questions after the retries were exhausted. Each question costs
        # 2-3 calls, so six questions in a minute exceeds the free quota.
        # Override with PAUSE=<seconds> when re-running.
        time.sleep(PAUSE)

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for r in results:
        print(
            f"  {r['file']:15} {r['question'][:44]:46} "
            f"{str(r['status']):16} attempt {r['attempts']}  {r['seconds']:5.1f}s"
        )
    print()
    planner_total = sum(1 for role, _, _ in calls if role == PLANNER)
    fast_total = sum(1 for role, _, _ in calls if role == FAST)
    n = len(selected)
    from collections import Counter

    print(f"  questions            : {n}")
    print(f"  logical LLM calls    : {len(calls)}  "
          f"(planner {planner_total}, fast {fast_total})")
    print(f"  REAL provider calls  : {counters['provider_attempts']}")
    print(f"  dev-cache hits       : {counters['cache_hits']}")
    print(f"  real calls/question  : {counters['provider_attempts'] / n:.2f}")
    if counters["models_used"]:
        print("  models that answered :")
        for model, count in Counter(counters["models_used"]).most_common():
            print(f"      {model:28} {count}")
    print(f"  dev cache            : {dev_cache_stats()}")


if __name__ == "__main__":
    main()
