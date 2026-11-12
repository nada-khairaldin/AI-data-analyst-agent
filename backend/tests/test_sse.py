"""Tests for the SSE framing and the task+queue (phase C4).

The disconnect behaviour is the one worth testing hardest: the whole design
exists so that a browser going away does not throw away LLM calls that have
already been paid for, nor leave a user message with no reply.
"""

import asyncio
import json

import pytest

from app.api import sse


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


def test_an_event_has_a_name_a_data_line_and_a_blank_line():
    text = sse.frame("status", {"stage": "planning", "label": "Planning"})

    assert text.startswith("event: status\n")
    assert "\ndata: " in text
    assert text.endswith("\n\n")


def test_data_is_a_single_line_of_json():
    """Multi-line data would need the client to join continuation lines."""
    text = sse.frame("token", {"text": "line one\nline two"})

    body = [line for line in text.splitlines() if line.startswith("data: ")]
    assert len(body) == 1
    assert json.loads(body[0][len("data: ") :])["text"] == "line one\nline two"


def test_non_serialisable_values_do_not_break_the_frame():
    """default=str, so a stray Timestamp degrades to a string rather than
    killing the stream mid-turn."""
    import datetime

    text = sse.frame("result", {"at": datetime.datetime(2024, 1, 5)})

    assert "2024-01-05" in text


def test_a_comment_is_a_valid_keep_alive():
    assert sse.comment().startswith(": ")
    assert sse.comment().endswith("\n\n")


def test_the_anti_buffering_headers_are_present():
    """A buffering proxy makes streaming silently indistinguishable from not
    streaming: everything arrives at once, at the end."""
    assert sse.SSE_HEADERS["Content-Type"].startswith("text/event-stream")
    assert "no-transform" in sse.SSE_HEADERS["Cache-Control"]
    assert sse.SSE_HEADERS["X-Accel-Buffering"] == "no"


# ---------------------------------------------------------------------------
# Draining
# ---------------------------------------------------------------------------


async def events(*items):
    for item in items:
        yield item


async def collect(generator):
    return [chunk async for chunk in generator]


async def test_every_event_is_forwarded_in_order():
    chunks = await collect(
        sse.stream_events(
            events(
                {"event": "status", "data": {"stage": "planning"}},
                {"event": "result", "data": {"resultData": []}},
                {"event": "token", "data": {"text": "hi"}},
                {"event": "done", "data": {"message": {}}},
            )
        )
    )

    names = [c.split("\n")[0] for c in chunks if c.startswith("event:")]
    assert names == [
        "event: status",
        "event: result",
        "event: token",
        "event: done",
    ]


async def test_result_precedes_the_first_token():
    """Deliberate: the table and chart ARE the answer, the sentence is
    commentary, so a 15s turn feels like a 3s one."""
    chunks = await collect(
        sse.stream_events(
            events(
                {"event": "result", "data": {}},
                {"event": "token", "data": {"text": "a"}},
                {"event": "token", "data": {"text": "b"}},
                {"event": "done", "data": {}},
            )
        )
    )
    text = "".join(chunks)

    assert text.index("event: result") < text.index("event: token")


async def test_exactly_one_terminator():
    chunks = await collect(
        sse.stream_events(events({"event": "done", "data": {}}))
    )
    text = "".join(chunks)

    assert text.count("event: done") == 1
    assert "event: error" not in text


async def test_a_pipeline_exception_becomes_an_error_event():
    """Nothing awaits the pump task, so a silent death would hang the client
    until its timeout."""

    async def exploding():
        yield {"event": "status", "data": {}}
        raise RuntimeError("boom")

    chunks = await collect(sse.stream_events(exploding()))
    text = "".join(chunks)

    assert "event: error" in text
    assert "INTERNAL_ERROR" in text
    # And the provider's message is not leaked to the client.
    assert "boom" not in text


async def test_a_heartbeat_is_sent_while_the_pipeline_is_slow():
    async def slow():
        await asyncio.sleep(0.25)
        yield {"event": "done", "data": {}}

    chunks = await collect(sse.stream_events(slow(), heartbeat=0.05))
    text = "".join(chunks)

    assert ": keep-alive" in text
    assert "event: done" in text


# ---------------------------------------------------------------------------
# Disconnect — the point of the task+queue
# ---------------------------------------------------------------------------


async def test_the_pipeline_finishes_after_the_client_disconnects():
    """Starlette closes the response generator on disconnect. The turn must
    still complete: the calls are already paid for, and a user message
    without a reply would break the §6B invariant.
    """
    finished = asyncio.Event()

    async def pipeline():
        yield {"event": "status", "data": {"stage": "planning"}}
        await asyncio.sleep(0.05)
        yield {"event": "done", "data": {}}
        finished.set()

    generator = sse.stream_events(pipeline())

    # Read one event, then abandon the stream exactly as a disconnect does.
    first = await generator.__anext__()
    assert "event: status" in first
    await generator.aclose()

    # The task keeps going on its own.
    await asyncio.wait_for(finished.wait(), timeout=2)
    assert finished.is_set()


async def test_closing_early_does_not_raise():
    async def pipeline():
        for index in range(50):
            yield {"event": "token", "data": {"text": str(index)}}
            await asyncio.sleep(0)

    generator = sse.stream_events(pipeline())
    await generator.__anext__()

    await generator.aclose()  # must not raise


async def test_the_pump_always_terminates_the_queue():
    """Without the sentinel in a finally, a failing pipeline would leave the
    response waiting on an empty queue forever."""
    queue: asyncio.Queue = asyncio.Queue()

    async def exploding():
        raise RuntimeError("boom")
        yield  # pragma: no cover

    await sse.pump(exploding(), queue)

    items = []
    while not queue.empty():
        items.append(queue.get_nowait())

    assert items[-1] is sse.SENTINEL
    assert items[0]["event"] == "error"
