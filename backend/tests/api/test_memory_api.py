"""API tests for memory and streaming (phase C).

Every LLM is mocked at its use site. What is real: the window built from the
messages table, the fact-sheet trigger, the event sequence, persistence, and
the SSE framing.
"""

import json
import uuid

import pytest

from app.agent.schemas import STATUSES

READY_PLAN = {
    "status": STATUSES["READY"],
    "analysis_plan": [
        {
            "tool": "aggregate_data",
            "column": "quantity",
            "operation": "sum",
            "group_by": "Product",
        }
    ],
    "chart_plan": None,
    "message": None,
}


@pytest.fixture
def mocks(monkeypatch):
    """Script the three LLM calls and record what each one was asked.

    Returns a dict the test can inspect and steer:
      condenser_replies  queue of raw replies (str) the condenser returns
      condenser_prompts  every prompt it received
      summarizer_reply   what the summariser returns (or an Exception to raise)
      summarizer_prompts every prompt it received
    """
    from app.agent import explainer as explainer_module
    from app.services import analysis_service, condenser, summarizer

    state = {
        "condenser_replies": [],
        "condenser_prompts": [],
        "summarizer_reply": (
            "Goal: sales\nDefinitions & agreements:\n- none\n"
            "Active filters/assumptions:\n- 2024 only\nKey findings:\n- none"
        ),
        "summarizer_prompts": [],
        "plan": dict(READY_PLAN),
        "answer": "Mouse sold the most.",
    }

    def fake_condenser_complete(prompt, role=None):
        state["condenser_prompts"].append(prompt)
        if state["condenser_replies"]:
            return state["condenser_replies"].pop(0)
        # Default: echo the new message back as a standalone question.
        question = prompt.rsplit("New user message:", 1)[-1].split("Decide what")[0]
        return json.dumps({"kind": "question", "question": question.strip()})

    def fake_summarizer_complete(prompt, role=None):
        state["summarizer_prompts"].append(prompt)
        reply = state["summarizer_reply"]
        if isinstance(reply, Exception):
            raise reply
        return reply

    def fake_run_agent(agent_state):
        agent_state.update(state["plan"])
        return agent_state

    async def fake_astream(question, plan, result):
        for word in state["answer"].split(" "):
            yield word + " "

    monkeypatch.setattr(condenser, "complete", fake_condenser_complete)
    monkeypatch.setattr(summarizer, "complete", fake_summarizer_complete)
    monkeypatch.setattr(analysis_service, "run_agent", fake_run_agent)
    monkeypatch.setattr(analysis_service, "astream_explanation", fake_astream)
    monkeypatch.setattr(explainer_module, "astream_explanation", fake_astream)
    return state


@pytest.fixture
async def conversation(client, upload, headers):
    dataset_id = (await upload()).json()["id"]
    created = (
        await client.post(
            f"/api/datasets/{dataset_id}/conversations", json={}, headers=headers
        )
    ).json()
    return dataset_id, created["id"]


async def ask(client, headers, conversation_id, text):
    return await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": text},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Condensation
# ---------------------------------------------------------------------------


async def test_the_first_message_skips_condensation(client, conversation, headers, mocks):
    """A first question is standalone by definition; on a free tier a
    guaranteed-identity call is pure waste."""
    _, conversation_id = conversation

    await ask(client, headers, conversation_id, "Which product sold most?")

    assert mocks["condenser_prompts"] == []


async def test_a_follow_up_is_condensed_and_stored(client, conversation, headers, mocks):
    _, conversation_id = conversation
    await ask(client, headers, conversation_id, "Which product sold most?")

    mocks["condenser_replies"] = [
        json.dumps(
            {
                "kind": "question",
                "question": "Show total quantity per month for every product",
            }
        )
    ]
    response = await ask(client, headers, conversation_id, "Now show it per month")
    message = response.json()["message"]

    assert len(mocks["condenser_prompts"]) == 1
    assert message["condensedQuestion"] == (
        "Show total quantity per month for every product"
    )


async def test_the_condensed_question_survives_a_reload(
    client, conversation, headers, mocks
):
    """It must come back from the messages endpoint, not only the stream, or
    the "Understood as:" line vanishes on refresh."""
    _, conversation_id = conversation
    await ask(client, headers, conversation_id, "Which product sold most?")
    mocks["condenser_replies"] = [
        json.dumps({"kind": "question", "question": "Totals per month"})
    ]
    await ask(client, headers, conversation_id, "per month?")

    history = (
        await client.get(
            f"/api/conversations/{conversation_id}/messages", headers=headers
        )
    ).json()

    assert history["messages"][-1]["condensedQuestion"] == "Totals per month"


async def test_a_condenser_parse_failure_plans_the_raw_question(
    client, conversation, headers, mocks
):
    """The pass-through: a broken reply must not break the chat."""
    _, conversation_id = conversation
    await ask(client, headers, conversation_id, "Which product sold most?")

    mocks["condenser_replies"] = ["this is not JSON and not one clean line\nat all"]
    response = await ask(client, headers, conversation_id, "and per month?")
    message = response.json()["message"]

    assert response.status_code == 201
    assert message["status"] == "ready"
    # Nothing is shown as "understood as" when it fell back, because nothing
    # was actually resolved.
    assert message["condensedQuestion"] is None


async def test_the_window_carries_the_plan_and_a_digest_not_the_rows(
    client, conversation, headers, mocks
):
    """One 500-row answer re-sent every turn would grow the cost of every
    future question forever."""
    _, conversation_id = conversation
    await ask(client, headers, conversation_id, "Which product sold most?")
    await ask(client, headers, conversation_id, "and per month?")

    prompt = mocks["condenser_prompts"][0]

    assert "understood as:" in prompt or "user: Which product sold most?" in prompt
    assert "plan:" in prompt
    assert "result:" in prompt
    assert "rows)" in prompt


# ---------------------------------------------------------------------------
# The acknowledgement path
# ---------------------------------------------------------------------------


async def test_an_instruction_costs_one_call_and_runs_no_planner(
    client, conversation, headers, mocks, monkeypatch
):
    from app.services import analysis_service

    planner_calls = []

    def counting_agent(state):
        planner_calls.append(1)
        state.update(READY_PLAN)
        return state

    monkeypatch.setattr(analysis_service, "run_agent", counting_agent)

    _, conversation_id = conversation
    await ask(client, headers, conversation_id, "Which product sold most?")
    before = len(planner_calls)

    mocks["condenser_replies"] = [
        json.dumps(
            {
                "kind": "instruction",
                "acknowledgement": "Got it - I'll keep everything to 2024.",
            }
        )
    ]
    response = await ask(client, headers, conversation_id, "only 2024 from now on")
    message = response.json()["message"]

    assert message["status"] == "ready"
    assert message["content"] == "Got it - I'll keep everything to 2024."
    assert message["resultData"] is None
    assert message["plan"] is None
    assert len(planner_calls) == before, "an instruction must not reach the planner"


async def test_an_acknowledgement_is_a_normal_message_in_the_history(
    client, conversation, headers, mocks
):
    """It has to be a real agent message so the next window and the fact sheet
    both carry the agreement forward."""
    _, conversation_id = conversation
    await ask(client, headers, conversation_id, "Which product sold most?")
    mocks["condenser_replies"] = [
        json.dumps({"kind": "instruction", "acknowledgement": "2024 only from now on."})
    ]
    await ask(client, headers, conversation_id, "only 2024")

    history = (
        await client.get(
            f"/api/conversations/{conversation_id}/messages", headers=headers
        )
    ).json()

    assert [m["role"] for m in history["messages"]][-2:] == ["user", "agent"]
    assert history["messages"][-1]["content"] == "2024 only from now on."


# ---------------------------------------------------------------------------
# The rolling summary
# ---------------------------------------------------------------------------


async def test_no_summary_before_two_exchanges_have_left_the_window(
    client, conversation, headers, mocks
):
    _, conversation_id = conversation
    for index in range(4):
        await ask(client, headers, conversation_id, f"question {index}")

    assert mocks["summarizer_prompts"] == []


async def test_the_summary_is_written_once_two_exchanges_have_left(
    client, conversation, headers, mocks
):
    _, conversation_id = conversation
    for index in range(5):
        await ask(client, headers, conversation_id, f"question {index}")

    assert len(mocks["summarizer_prompts"]) >= 1


async def test_a_summariser_failure_never_blocks_the_chat(
    client, conversation, headers, mocks
):
    """It runs after `done`, so a failure must leave an answered turn alone."""
    _, conversation_id = conversation
    mocks["summarizer_reply"] = RuntimeError("summariser exploded")

    for index in range(5):
        response = await ask(client, headers, conversation_id, f"question {index}")
        assert response.status_code == 201, response.text

    history = (
        await client.get(
            f"/api/conversations/{conversation_id}/messages", headers=headers
        )
    ).json()

    assert len(history["messages"]) == 10
    assert all(m.get("status") != "failed" for m in history["messages"] if m["role"] == "agent")


async def test_a_summary_without_headings_is_not_stored(
    client, conversation, headers, mocks
):
    """Keeping the previous sheet beats storing prose that later turns will
    misread."""
    _, conversation_id = conversation
    mocks["summarizer_reply"] = "The user asked about products and then months."

    for index in range(5):
        assert (await ask(client, headers, conversation_id, f"q{index}")).status_code == 201

    # The next turn's condenser prompt must not contain the rejected text.
    await ask(client, headers, conversation_id, "one more")
    assert "then months" not in mocks["condenser_prompts"][-1]


async def test_an_agreement_still_applies_after_it_has_left_the_window(
    client, conversation, headers, mocks
):
    """The whole point of the fact sheet.

    "only 2024" is agreed on turn 1, then pushed out of the 3-exchange window
    by four more turns. On the turn after that, the condenser must still be
    told about it — and the only remaining carrier is the fact sheet.
    """
    _, conversation_id = conversation

    await ask(client, headers, conversation_id, "Which product sold most?")

    mocks["condenser_replies"] = [
        json.dumps(
            {"kind": "instruction", "acknowledgement": "Got it - 2024 only from now on."}
        )
    ]
    await ask(client, headers, conversation_id, "only 2024 from now on")

    # Four more exchanges, which pushes the agreement out of the window.
    for index in range(4):
        await ask(client, headers, conversation_id, f"later question {index}")

    prompt = mocks["condenser_prompts"][-1]

    # Slice BETWEEN the markers. The prompt's own rules mention
    # "only 2024 from now on" as an example of an instruction, and that text
    # sits after the window — reading to the end of the prompt picks it up and
    # the assertion passes for the wrong reason.
    window = prompt.split("Recent exchanges (oldest first):", 1)[-1].split(
        "New user message:", 1
    )[0]
    facts = prompt.split("Known from earlier in this conversation:", 1)[-1].split(
        "Recent exchanges (oldest first):", 1
    )[0]

    assert "2024" not in window, "the agreement should have left the window by now"
    assert "2024" in facts, "the fact sheet must still carry the agreement"


# ---------------------------------------------------------------------------
# The SSE endpoint
# ---------------------------------------------------------------------------


def parse_sse(text):
    """[(event, data), ...] from a raw SSE body."""
    events = []
    for block in text.split("\n\n"):
        name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if name:
            events.append((name, data))
    return events


async def test_the_stream_emits_the_contract_sequence(
    client, conversation, headers, mocks
):
    _, conversation_id = conversation

    async with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "Which product sold most?"},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        body = "".join([chunk async for chunk in response.aiter_text()])

    events = parse_sse(body)
    names = [name for name, _ in events]

    assert names[0] == "status"
    assert names[-1] == "done"
    assert names.count("done") == 1
    assert "error" not in names
    assert names.index("result") < names.index("token")
    assert len([n for n in names if n == "status"]) == 5


async def test_the_stream_and_the_json_endpoint_agree(
    client, conversation, headers, mocks
):
    """Both drain the same generator, so done.message must match endpoint 11."""
    _, conversation_id = conversation

    async with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "Which product sold most?"},
        headers=headers,
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    done = dict(parse_sse(body))["done"]
    tokens = "".join(
        data["text"] for name, data in parse_sse(body) if name == "token"
    )

    assert set(done) == {"conversation", "message"}
    assert done["message"]["status"] == "ready"
    # The contract tells clients to replace their accumulation with this.
    assert done["message"]["content"].strip() == tokens.strip()


async def test_the_stream_persists_the_messages(client, conversation, headers, mocks):
    _, conversation_id = conversation

    async with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "Which product sold most?"},
        headers=headers,
    ) as response:
        [chunk async for chunk in response.aiter_text()]

    history = (
        await client.get(
            f"/api/conversations/{conversation_id}/messages", headers=headers
        )
    ).json()

    assert [m["role"] for m in history["messages"]] == ["user", "agent"]


async def test_an_empty_question_is_a_400_before_the_stream_starts(
    client, conversation, headers, mocks
):
    """After the status line, an error can only be an event — far less useful
    to a client than a real status code."""
    _, conversation_id = conversation

    response = await client.post(
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "  "},
        headers=headers,
    )

    assert response.status_code == 400


async def test_another_session_cannot_stream_the_conversation(
    client, conversation, headers, mocks
):
    _, conversation_id = conversation

    response = await client.post(
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "Which product sold most?"},
        headers={"X-Session-Id": str(uuid.uuid4())},
    )

    assert response.status_code == 404


async def test_a_disconnect_still_persists_the_reply(
    client, conversation, headers, mocks, db_factory
):
    """The §6B invariant under the condition it was designed for: the calls
    are already paid for, so the turn finishes even though nobody is reading.
    """
    import asyncio

    _, conversation_id = conversation

    async with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "Which product sold most?"},
        headers=headers,
    ) as response:
        # Read one chunk, then walk away without draining.
        async for _ in response.aiter_text():
            break

    # Give the detached task a moment to finish and commit.
    from app.db.models import Message
    from sqlalchemy import select

    for _ in range(40):
        await asyncio.sleep(0.25)
        async with db_factory() as db:
            rows = list(
                (
                    await db.execute(
                        select(Message).where(
                            Message.conversation_id == uuid.UUID(conversation_id)
                        )
                    )
                ).scalars()
            )
        roles = [r.role for r in rows]
        if roles.count("agent") >= 1:
            break

    assert "user" in roles
    assert "agent" in roles, "the reply must be persisted even after a disconnect"
