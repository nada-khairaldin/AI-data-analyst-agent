"""Does the configured model exist, and can it stream?

Run from backend/:  python scratch/check_model.py

The whole streaming design in docs/PLAN.md §6B rests on two assumptions that
have never been tested: that LLM_MODEL resolves on LLM_BASE_URL, and that the
provider streams. Both are cheap to check and expensive to discover late --
finding out in feature 5.5 that the free tier does not stream would mean
redesigning the chat endpoint after building it.

This is a deliberate throwaway. It is committed so the next person can re-run
it after changing LLM_MODEL, not because the app depends on it.
"""

import sys
import time

sys.path.insert(0, ".")

from app.agent.llm import complete, get_client, stream  # noqa: E402
from app.config import settings  # noqa: E402

PROMPT = "Reply with exactly: OK"


def show_config():
    print("config")
    print(f"  base_url : {settings.llm_base_url}")
    print(f"  model    : {settings.llm_model}")
    print(f"  key      : {'present' if settings.resolved_llm_api_key else 'MISSING'}")
    print(f"  timeout  : {settings.llm_timeout_seconds}s")
    print(f"  retries  : {settings.llm_max_retries}")
    print()


def check_model_exists():
    """Is LLM_MODEL actually on the router?

    This runs first because the router checks billing BEFORE it resolves the
    model, so a 402 masks a wrong model id completely. Listing the models is
    free and separates the two faults -- which matters, because this project
    shipped with a hardcoded id that was never on the list.
    """
    print("0. model id resolves")
    try:
        ids = [m.id for m in get_client().models.list().data]
    except Exception as error:
        print(f"   SKIPPED  could not list models: {type(error).__name__}")
        return None

    target = settings.llm_model
    if target in ids:
        print(f"   OK       {target} is one of {len(ids)} available models")
        print()
        return True

    print(f"   FAILED   {target!r} is NOT on the router ({len(ids)} models)")
    stem = target.split(":")[0].split("/")[-1][:8].lower()
    near = [i for i in ids if stem in i.lower()]
    if near:
        print("   did you mean:")
        for i in near[:5]:
            print(f"              {i}")
    print()
    return False


def check_completion():
    print("1. non-streaming completion")
    started = time.monotonic()
    try:
        reply = complete(PROMPT)
    except Exception as error:
        print(f"   FAILED  {type(error).__name__}: {error}")
        if "402" in str(error):
            print()
            print("   This is a BILLING failure, not a code failure: the")
            print("   Hugging Face account has no Inference Provider credits.")
            print("   Features 5 and 5.5 cannot be built or tested until")
            print("   credits are added, a PRO subscription is active, or")
            print("   LLM_BASE_URL points at a provider with a free tier.")
        return False
    elapsed = time.monotonic() - started
    print(f"   OK      {elapsed:.2f}s")
    print(f"   reply   {reply!r}")
    print()
    return True


def check_streaming():
    """The important one: chunks must arrive separately, not all at once.

    A provider that buffers the whole reply and sends it as a single chunk is
    technically "streaming" and useless for §6B, so this measures the gap
    between the first and last chunk rather than just counting them.
    """
    print("2. streaming completion")
    started = time.monotonic()
    first_at = None
    last_at = None
    chunks = []

    try:
        for piece in stream("Count from 1 to 10, separated by spaces."):
            now = time.monotonic()
            if first_at is None:
                first_at = now
            last_at = now
            chunks.append(piece)
            print(f"   +{now - started:5.2f}s  {piece!r}")
    except Exception as error:
        print(f"   FAILED  {type(error).__name__}: {error}")
        return False

    if not chunks:
        print("   FAILED  the stream yielded no content at all")
        return False

    print()
    print(f"   chunks            : {len(chunks)}")
    print(f"   time to first     : {first_at - started:.2f}s")
    print(f"   first -> last     : {last_at - first_at:.2f}s")
    print(f"   full reply        : {''.join(chunks)!r}")

    if len(chunks) == 1:
        print()
        print("   WARNING: one chunk only. The provider buffered the whole")
        print("   reply, so token-by-token streaming is NOT available and")
        print("   docs/PLAN.md §6B needs rethinking before feature 5.5.")
        return False

    print()
    print("   OK: real incremental streaming. §6B is viable.")
    return True


if __name__ == "__main__":
    show_config()
    ok_model = check_model_exists()
    ok_complete = check_completion()
    ok_stream = check_streaming() if ok_complete else False

    def label(value):
        return {True: "PASS", False: "FAIL", None: "SKIP"}[value]

    print()
    print("=" * 60)
    print(f"  model id   : {label(ok_model)}")
    print(f"  completion : {label(ok_complete)}")
    print(f"  streaming  : {label(ok_stream)}")
    print("=" * 60)
    sys.exit(0 if (ok_complete and ok_stream) else 1)
