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


def instrument():
    """Wrap the two call sites.

    core.py and explainer.py each imported `complete` into their own
    namespace, so patching app.agent.llm.complete would not be seen by
    either. The names have to be replaced where they are used.
    """
    real_core = core.complete
    real_explainer = explainer.complete

    def core_complete(prompt, *, role=PLANNER):
        out = real_core(prompt, role=role)
        calls.append((role, len(prompt), len(out or "")))
        planner_outputs.append(out)
        return out

    def explainer_complete(prompt, *, role=FAST):
        out = real_explainer(prompt, role=role)
        calls.append((role, len(prompt), len(out or "")))
        return out

    core.complete = core_complete
    explainer.complete = explainer_complete


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

    for filename, question, expected in QUESTIONS:
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
    print(f"  TOTAL LLM CALLS : {len(calls)}  "
          f"(planner {planner_total}, fast {fast_total})")
    print(f"  questions       : {len(QUESTIONS)}")
    print(f"  calls/question  : {len(calls) / len(QUESTIONS):.2f}")


if __name__ == "__main__":
    main()
