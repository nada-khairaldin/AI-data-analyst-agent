"""One turn of the chat, as an async event generator (PLAN §6B).

``run_turn`` yields the events in the contract's catalogue. Endpoint 11 drains
it and returns only the final message; the SSE endpoint in phase C forwards
every event. Writing the generator first is what makes streaming additive
rather than a rewrite.

Invariant: **a conversation can never hold a user message with no reply.** The
user row is written before the first event; on any failure an agent row with
status ``failed`` is written before ``error`` is emitted.
"""

import logging
import time

import pandas as pd

from app.agent import STATUSES, create_agent_state, run_agent
from app.agent.charting import (
    validate_chart_against_result,
    validate_chart_data_types,
    validate_chart_semantics,
)
from app.agent.explainer import astream_explanation
from app.agent.llm import LLMError
from app.agent.tools import execute_plan
from app.api.serializers import conversation_summary, message_detail
from app.config import settings
from app.data.data_utils import get_schema
from app.presenters import render_plan, to_jsonable
from app.services import condenser, conversation_service, summarizer

logger = logging.getLogger(__name__)

STAGE_LABELS = {
    "condensing": "Understanding your question",
    "planning": "Planning the analysis",
    "validating": "Checking the plan",
    "executing": "Running the analysis",
    "explaining": "Writing the answer",
}


def event(name, **payload):
    return {"event": name, "data": payload}


def _status(stage):
    return event("status", stage=stage, label=STAGE_LABELS[stage])


def result_kind(result):
    return "table" if isinstance(result, pd.DataFrame) else "scalar"


def serialise_result(result):
    """Result rows or scalar as JSON-safe values.

    Every value goes through ``to_jsonable``, which is what makes NaN become
    null and a Timestamp become an ISO string. Both matter: NaN is not valid
    JSON (a strict parser and the browser's JSON.parse both reject it), and a
    Timestamp is neither JSON-serialisable nor a valid jsonb value — which is
    reachable now that min/max are allowed on date columns.
    """
    if isinstance(result, pd.DataFrame):
        return [
            {str(key): to_jsonable(value) for key, value in record.items()}
            for record in result.to_dict(orient="records")
        ]
    return to_jsonable(result)


async def run_turn(db, conversation, dataset, frame, columns, question, *, history=None):
    """Yield the events of one turn, persisting both messages.

    ``history`` is accepted and ignored: the planner is given ``[]`` until
    phase C adds condensation. It is a parameter now so that adding memory
    does not change this signature.
    """
    started = time.monotonic()
    history = history or []

    # The user message is persisted FIRST, before any event. A question is
    # never lost, whatever happens next.
    first = await conversation_service.is_first_question(db, conversation.id)
    await conversation_service.add_message(
        db, conversation, role="user", content=question
    )
    if first:
        await conversation_service.autotitle(db, conversation, question)
    await db.commit()

    try:
        async for item in _pipeline(
            db,
            conversation,
            dataset,
            frame,
            columns,
            question,
            history,
            started,
            first_question=first,
        ):
            yield item
    except LLMError as error:
        yield await _fail(db, conversation, error.code, error.message, started)
    except Exception as error:
        logger.exception("Turn failed for conversation %s", conversation.id)
        yield await _fail(
            db,
            conversation,
            "INTERNAL_ERROR",
            "Something went wrong while analysing your question.",
            started,
        )


async def _pipeline(
    db,
    conversation,
    dataset,
    frame,
    columns,
    question,
    history,
    started,
    *,
    first_question,
):
    # Real unavailable_columns, from dataset_columns. The old endpoint passed
    # {} because it had dropped the columns, so the agent could only say
    # "unknown column" and never "excluded for quality reasons".
    unavailable = {
        column.name: column.exclusion_reason
        for column in columns
        if not column.is_available
    }
    available = {column.name for column in columns if column.is_available}

    # The planner is only shown columns it may use. An excluded column in the
    # schema would invite a plan that the executor then cannot run.
    schema = {
        name: dtype
        for name, dtype in get_schema(frame).items()
        if name in available
    }

    # ---- condensing -----------------------------------------------------
    yield _status("condensing")

    condensed_question = None
    asked = question

    if not first_question:
        outcome = condenser.condense(
            question=question,
            schema=schema,
            excluded_columns=unavailable,
            fact_sheet=await summarizer.fact_sheet(db, conversation.id),
            window=conversation_service.render_window(
                await conversation_service.window_exchanges(
                    db,
                    conversation.id,
                    exchanges=settings.history_window_exchanges,
                )
            ),
        )

        if outcome["kind"] == condenser.INSTRUCTION:
            # An instruction asks nothing, so there is nothing to plan or
            # explain: 1 LLM call instead of 3 (PLAN §6.4). It is persisted as
            # a normal ready agent message so the next turn's window and the
            # fact sheet both carry the agreement forward.
            text = outcome["acknowledgement"]
            for chunk in _as_chunks(text):
                yield event("token", text=chunk)
            yield await _finish(
                db,
                conversation,
                status=STATUSES["READY"],
                content=text,
                started=started,
                condensed_question=None,
            )
            return

        asked = outcome["question"]
        if not outcome["fell_back"] and asked.strip() != question.strip():
            condensed_question = asked
            yield event("condensed", question=asked)

    # ---- planning -------------------------------------------------------
    yield _status("planning")

    state = create_agent_state(
        question=asked, schema=schema, unavailable_columns=unavailable
    )
    state = run_agent(state)

    # ---- validating -----------------------------------------------------
    yield _status("validating")

    status = state["status"]

    if status == STATUSES["FAILED"]:
        yield await _fail(
            db,
            conversation,
            "LLM_UNAVAILABLE",
            state.get("error") or "The analysis plan could not be produced.",
            started,
        )
        return

    if status in (STATUSES["NEEDS_CLARIFICATION"], STATUSES["CANNOT_ANSWER"]):
        # No result and NO explainer call — there is nothing to explain. The
        # text is still emitted as tokens so the client path is identical.
        text = state.get("message") or ""
        for chunk in _as_chunks(text):
            yield event("token", text=chunk)
        yield await _finish(
            db,
            conversation,
            status=status,
            content=text,
            started=started,
            condensed_question=condensed_question,
        )
        return

    # ---- executing ------------------------------------------------------
    yield _status("executing")

    plan = state["analysis_plan"]
    try:
        result = execute_plan(frame, plan)
    except Exception as error:
        yield await _fail(
            db,
            conversation,
            "ANALYSIS_FAILED",
            f"The analysis could not be completed: {error}",
            started,
            analysis_plan=plan,
        )
        return

    # The chart is validated against the ACTUAL result, not the predicted
    # columns: validators.py checked the plan's shape, this checks the data.
    chart_plan = _validated_chart(result, state.get("chart_plan"))

    rows = serialise_result(result)
    kind = result_kind(result)
    plan_display = render_plan(question, plan)

    yield event(
        "result",
        resultData=rows,
        resultKind=kind,
        chartPlan=chart_plan,
        plan=plan_display,
    )

    # ---- explaining -----------------------------------------------------
    yield _status("explaining")

    collected = []
    try:
        async for piece in astream_explanation(asked, plan, result):
            collected.append(piece)
            yield event("token", text=piece)
    except LLMError:
        raise
    except Exception as error:
        logger.warning("Explainer failed, falling back: %s", error)

    answer = "".join(collected).strip()
    if not answer:
        # Deterministic sentence from the result rather than raising, which is
        # what the old code did after the analysis had already succeeded and
        # already been paid for (PLAN §6B).
        answer = _fallback_answer(result, plan)
        for chunk in _as_chunks(answer):
            yield event("token", text=chunk)

    yield await _finish(
        db,
        conversation,
        status=STATUSES["READY"],
        content=answer,
        started=started,
        condensed_question=condensed_question,
        analysis_plan=plan,
        chart_plan=chart_plan,
        result_data=rows,
        result_kind=kind,
        plan_display=plan_display,
    )

    # After `done`, never before: a summariser failure must not touch a turn
    # that is already answered.
    await _maybe_refresh_summary(db, conversation)


def _validated_chart(result, chart_plan):
    """Drop the chart rather than the answer when it does not hold up.

    A bad chart is cosmetic; failing the turn over one would throw away a
    correct analysis the user already paid for.
    """
    if not chart_plan or not chart_plan.get("should_plot"):
        return {"should_plot": False, "chart_type": None, "x": None, "y": None}

    for check in (
        validate_chart_against_result,
        validate_chart_data_types,
        validate_chart_semantics,
    ):
        ok, error = check(result, chart_plan)
        if not ok:
            logger.info("Chart rejected: %s", error)
            return {"should_plot": False, "chart_type": None, "x": None, "y": None}

    return chart_plan


def _as_chunks(text, size=48):
    """Split text on word boundaries so the token path is exercised even
    without a streaming explainer."""
    text = text or ""
    if not text:
        return
    words = text.split(" ")
    buffer = ""
    for word in words:
        candidate = f"{buffer} {word}" if buffer else word
        if len(candidate) >= size:
            yield candidate + " "
            buffer = ""
        else:
            buffer = candidate
    if buffer:
        yield buffer


def _fallback_answer(result, plan):
    """A deterministic sentence when the explainer produces nothing.

    Strictly better than the old behaviour, which raised and lost the turn
    after the analysis had already succeeded (PLAN §6B).
    """
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return "The analysis returned no rows."
        if len(result) == 1:
            pairs = ", ".join(
                f"{key}: {value}" for key, value in result.iloc[0].items()
            )
            return f"Result: {pairs}."
        return f"The analysis returned {len(result)} rows."
    return f"Result: {result}."


async def _finish(
    db,
    conversation,
    *,
    status,
    content,
    started,
    condensed_question=None,
    analysis_plan=None,
    chart_plan=None,
    result_data=None,
    result_kind=None,
    plan_display=None,
):
    """Persist the agent message exactly once, then emit `done`."""
    message = await conversation_service.add_message(
        db,
        conversation,
        role="agent",
        content=content,
        status=status,
        condensed_question=condensed_question,
        analysis_plan=analysis_plan,
        chart_plan=chart_plan,
        result_data=result_data,
        result_kind=result_kind,
        plan_display=plan_display,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    await db.commit()
    await db.refresh(conversation)
    return event(
        "done",
        conversation=conversation_summary(conversation),
        message=message_detail(message),
    )


async def _fail(db, conversation, code, message, started, **extra):
    """Write a `failed` agent message, then emit `error`.

    This is the invariant: no user message without a reply.
    """
    await conversation_service.add_message(
        db,
        conversation,
        role="agent",
        content=message,
        status="failed",
        latency_ms=int((time.monotonic() - started) * 1000),
        **extra,
    )
    await db.commit()
    return event("error", code=code, message=message)


async def _maybe_refresh_summary(db, conversation):
    """Refresh the fact sheet when 2 exchanges have left the window.

    Wrapped whole: the turn is already persisted and `done` already emitted,
    so nothing here may raise into the caller. A failure keeps the previous
    sheet, which is always safe.
    """
    try:
        summary = await summarizer.load_summary(db, conversation.id)
        if not summarizer.is_due(conversation, summary):
            return

        covered = summary.exchange_count if summary else 0
        pairs = await summarizer.exchanges_outside_window(
            db, conversation.id, covered=covered
        )
        if not pairs:
            return

        text = await summarizer.refresh(
            db, conversation, pairs, covers_through_id=pairs[-1][1].id
        )
        if text is not None:
            await db.commit()
            logger.info("Fact sheet refreshed for conversation %s", conversation.id)
    except Exception as error:
        logger.warning("Fact sheet refresh skipped: %s", error)
        await db.rollback()
