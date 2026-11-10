"""Do both configured Gemini models exist, answer, and stream?

Run from backend/:  python scratch/check_model.py

Checks, per model, in the order that isolates faults:

0. The id appears in the live models.list output and supports
   generateContent. This runs FIRST because a wrong id and an exhausted quota
   produce different errors, and guessing between them wastes time. The
   previous provider shipped with a hardcoded model id that was never on its
   list, and nothing caught it for months.
1. A normal completion, with latency and token usage. The usage breakdown
   matters: a reasoning model can spend almost its entire output budget on
   hidden thinking tokens, which is invisible in the reply but obvious here.
2. Streaming, measuring the gap between the first and last chunk rather than
   just counting them. A provider that buffers the whole reply and sends it as
   one chunk is technically streaming and useless for docs/PLAN.md §6B.

A deliberate throwaway, committed so it can be re-run after changing a model
id or a thinking budget.
"""

import sys
import time
import warnings

sys.path.insert(0, ".")

warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

import google.genai as genai  # noqa: E402

from app.agent.llm import (  # noqa: E402
    FAST,
    PLANNER,
    LLMError,
    complete,
    get_model,
    model_name,
    stream,
)
from app.config import settings  # noqa: E402

ROLES = ((PLANNER, "planner"), (FAST, "fast"))


def show_config():
    print("config")
    print(f"  key              : {'present' if settings.gemini_api_key else 'MISSING'}")
    print(f"  planner model    : {settings.llm_planner_model}")
    print(f"  fast model       : {settings.llm_fast_model}")
    print(f"  thinking budget  : {settings.llm_planner_thinking_budget} (planner)")
    print(f"  timeout          : {settings.llm_timeout_seconds}s")
    print(f"  retries (429)    : {settings.llm_max_retries}")
    print()


def list_available():
    """Every id that supports generateContent, straight from the API."""
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        names = set()
        for model in client.models.list():
            actions = getattr(model, "supported_actions", None) or []
            if not actions or "generateContent" in actions:
                names.add((model.name or "").replace("models/", ""))
        return names
    except Exception as error:
        print(f"  could not list models: {type(error).__name__}: {error}")
        return None


def check_id(role, label, available):
    print(f"0. [{label}] model id resolves")
    name = model_name(role)

    if available is None:
        print("   SKIPPED  no model list to compare against")
        print()
        return None

    if name in available:
        print(f"   OK       {name} is one of {len(available)} usable models")
        print()
        return True

    print(f"   FAILED   {name!r} is NOT available ({len(available)} usable models)")
    stem = name.split("-")[0]
    near = sorted(n for n in available if n.startswith(stem))
    if near:
        print("   did you mean:")
        for n in near[:8]:
            print(f"              {n}")
    print()
    return False


def check_completion(role, label):
    print(f"1. [{label}] completion")
    started = time.monotonic()
    try:
        reply = complete("Reply with exactly: OK", role=role)
    except LLMError as error:
        print(f"   FAILED   {type(error).__name__}: {error}")
        print()
        return False
    except Exception as error:
        print(f"   FAILED   {type(error).__name__}: {error}")
        print()
        return False

    elapsed = time.monotonic() - started
    print(f"   OK       {elapsed:.2f}s")
    print(f"   reply    {reply!r}")

    # Usage is read off a second, direct call because complete() returns only
    # the text. Worth it: the reasoning split is the thing most likely to
    # explain a surprising latency.
    try:
        response = get_model(role).invoke("Reply with exactly: OK")
        usage = response.usage_metadata or {}
        reasoning = (usage.get("output_token_details") or {}).get("reasoning", 0)
        print(
            f"   tokens   in={usage.get('input_tokens')} "
            f"out={usage.get('output_tokens')} (reasoning={reasoning})"
        )
        if reasoning and usage.get("output_tokens"):
            share = reasoning / usage["output_tokens"]
            if share > 0.5:
                print(
                    f"   NOTE     {share:.0%} of the output budget went to hidden"
                    " thinking tokens."
                )
    except Exception:
        pass

    print()
    return True


def check_streaming(role, label):
    print(f"2. [{label}] streaming")
    started = time.monotonic()
    first_at = last_at = None
    chunks = []

    try:
        for piece in stream("Count from 1 to 10, separated by spaces.", role=role):
            now = time.monotonic()
            if first_at is None:
                first_at = now
            last_at = now
            chunks.append(piece)
    except Exception as error:
        print(f"   FAILED   {type(error).__name__}: {error}")
        print()
        return False

    if not chunks:
        print("   FAILED   the stream yielded no content at all")
        print()
        return False

    print(f"   chunks           : {len(chunks)}")
    print(f"   time to first    : {first_at - started:.2f}s")
    print(f"   first -> last    : {last_at - first_at:.2f}s")
    print(f"   reply            : {''.join(chunks).strip()[:70]!r}")

    if len(chunks) == 1:
        print()
        print("   WARNING: one chunk only. The provider buffered the whole reply,")
        print("   so token-by-token streaming is NOT available and §6B needs")
        print("   rethinking before feature 5.5.")
        print()
        return False

    print("   OK: real incremental streaming.")
    print()
    return True


if __name__ == "__main__":
    show_config()
    available = list_available()
    results = {}

    for role, label in ROLES:
        print("=" * 62)
        print(f"  {label.upper()}: {model_name(role)}")
        print("=" * 62)
        ok_id = check_id(role, label, available)
        ok_complete = check_completion(role, label)
        ok_stream = check_streaming(role, label) if ok_complete else False
        results[label] = (ok_id, ok_complete, ok_stream)

    def mark(value):
        return {True: "PASS", False: "FAIL", None: "SKIP"}[value]

    print("=" * 62)
    print(f"  {'role':10} {'model id':10} {'completion':12} streaming")
    for label, (a, b, c) in results.items():
        print(f"  {label:10} {mark(a):10} {mark(b):12} {mark(c)}")
    print("=" * 62)

    everything = all(b and c for _, b, c in results.values())
    sys.exit(0 if everything else 1)
