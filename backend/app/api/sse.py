"""SSE framing and the task+queue that outlives a disconnect (PLAN §6B).

Starlette cancels a response generator when the client goes away, which would
abandon a turn *after* the planner and explainer calls had already been paid
for — and leave a user message with no reply. So the pipeline runs as its own
task writing into a queue, and the response only drains the queue. If the
client disconnects the queue is dropped but the task runs to completion and
persists the agent message.
"""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

# Flushed every 15s by default so an idle proxy does not close the connection
# while the planner is still thinking.
SENTINEL = object()

# A reverse proxy that buffers the response makes streaming silently
# indistinguishable from not streaming: everything arrives at once, at the
# end. These are required on every SSE response (PLAN §6B).
SSE_HEADERS = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def frame(name: str, payload) -> str:
    """One SSE event. `data` is a single line, so no multi-line parsing."""
    return f"event: {name}\ndata: {json.dumps(payload, default=str)}\n\n"


def comment(text: str = "keep-alive") -> str:
    """An SSE comment: ignored by clients, keeps the socket warm."""
    return f": {text}\n\n"


async def pump(generator, queue):
    """Drain `generator` into `queue`, always terminating with SENTINEL.

    Runs as its own task. Exceptions are turned into an `error` event rather
    than raised, because nothing is awaiting this task — the response is
    reading the queue, and a silent death would hang the client until timeout.
    """
    try:
        async for item in generator:
            await queue.put(item)
    except Exception as error:
        logger.exception("SSE pipeline failed")
        await queue.put(
            {
                "event": "error",
                "data": {
                    "code": "INTERNAL_ERROR",
                    "message": "Something went wrong while analysing your question.",
                },
            }
        )
    finally:
        await queue.put(SENTINEL)


async def stream_events(generator, *, heartbeat=15.0):
    """Yield SSE text for every event, with keep-alives while idle.

    The pipeline task is deliberately NOT cancelled when this generator is
    closed: that is the whole point of the design. The task finishes, the
    agent message is persisted, and the user finds the answer when they
    reopen the conversation.
    """
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(pump(generator, queue))

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            except TimeoutError:
                yield comment()
                continue

            if item is SENTINEL:
                return

            yield frame(item["event"], item["data"])
    except asyncio.CancelledError:
        # The client went away. Logged at info, not error: it is a normal
        # thing for a browser to do, and the turn is still being completed.
        logger.info("SSE client disconnected; the turn continues in the background")
        raise
    finally:
        if not task.done():
            logger.info("Leaving the turn running so the reply is persisted")
