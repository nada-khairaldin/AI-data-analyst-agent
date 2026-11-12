"""API tests for conversations and the chat turn (phase B1/B2).

The LLM is never called. ``run_agent`` and ``explain_result`` are replaced at
their use sites in analysis_service, which is where the names are bound — the
rest of the pipeline (execute_plan, chart validation, persistence, the event
sequence) is the real code.
"""

import uuid

import pytest

from app.agent.schemas import STATUSES


@pytest.fixture
def fake_agent(monkeypatch):
    """Install a planner result. Returns a setter so each test picks one."""
    from app.services import analysis_service

    state = {}

    def set_plan(**overrides):
        state.clear()
        state.update(overrides)

    def fake_run_agent(agent_state):
        agent_state.update(state)
        return agent_state

    monkeypatch.setattr(analysis_service, "run_agent", fake_run_agent)
    monkeypatch.setattr(
        analysis_service,
        "explain_result",
        lambda question, plan, result: "Mouse sold the most, at 2709 units.",
    )
    return set_plan


READY_PLAN = {
    "status": STATUSES["READY"],
    "analysis_plan": [
        {
            "tool": "aggregate_data",
            "column": "quantity",
            "operation": "sum",
            "group_by": "Product",
        },
        {"tool": "sort_data", "column": "quantity", "ascending": False},
        {"tool": "limit_results", "limit": 1},
    ],
    "chart_plan": {
        "should_plot": True,
        "chart_type": "bar",
        "x": "Product",
        "y": "quantity",
    },
    "message": None,
}


@pytest.fixture
async def conversation(client, upload, headers):
    dataset_id = (await upload()).json()["id"]
    created = (
        await client.post(
            f"/api/datasets/{dataset_id}/conversations", json={}, headers=headers
        )
    ).json()
    return dataset_id, created["id"]


# ---------------------------------------------------------------------------
# Conversations — endpoints 8, 9, 12
# ---------------------------------------------------------------------------


async def test_create_conversation_returns_the_mock_shape(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    response = await client.post(
        f"/api/datasets/{dataset_id}/conversations", json={}, headers=headers
    )
    body = response.json()

    assert response.status_code == 201
    assert body["title"] == "New Conversation"
    assert body["date"] == "Just now"
    assert body["messageCount"] == 0
    assert body["messages"] == []


async def test_create_conversation_accepts_a_title(client, upload, headers):
    dataset_id = (await upload()).json()["id"]

    body = (await client.post(
        f"/api/datasets/{dataset_id}/conversations",
        json={"title": "Q4 review"},
        headers=headers,
    )).json()

    assert body["title"] == "Q4 review"


async def test_conversations_appear_on_the_dataset(client, conversation, headers):
    dataset_id, conversation_id = conversation

    listed = (await client.get(
        f"/api/datasets/{dataset_id}/conversations", headers=headers
    )).json()
    nested = (await client.get(f"/api/datasets/{dataset_id}", headers=headers)).json()

    assert [c["id"] for c in listed["conversations"]] == [conversation_id]
    assert [c["id"] for c in nested["conversations"]] == [conversation_id]


async def test_a_conversation_needs_an_owned_dataset(client, headers):
    response = await client.post(
        f"/api/datasets/{uuid.uuid4()}/conversations", json={}, headers=headers
    )

    assert response.status_code == 404


async def test_rename_a_conversation(client, conversation, headers):
    _, conversation_id = conversation

    response = await client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "Renamed"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"


# ---------------------------------------------------------------------------
# A ready turn — endpoint 11
# ---------------------------------------------------------------------------


async def test_a_ready_turn_returns_the_contract_shape(
    client, conversation, headers, fake_agent
):
    _, conversation_id = conversation
    fake_agent(**READY_PLAN)

    response = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "Which product has the highest total quantity sold?"},
        headers=headers,
    )
    body = response.json()

    assert response.status_code == 201
    assert set(body) == {"conversation", "message"}
    message = body["message"]
    assert message["role"] == "agent"
    assert message["status"] == "ready"
    assert message["content"]
    # The duplicates are NOT removed, which is the point: the dataset warns
    # about them and the analysis counts them.
    assert message["resultData"] == [{"Product": "Mouse", "quantity": 2709.0}]
    assert message["resultKind"] == "table"
    assert message["showChart"] is True
    assert message["chartTitle"]
    assert message["plan"]["steps"]
    assert message["plan"]["columnsUsed"] == ["quantity", "Product"]
    assert message["plan"]["filters"] == "None"


async def test_the_analysis_uses_the_stored_parquet(client, conversation, headers, fake_agent):
    """The exact total proves the real stored frame was loaded, the real
    execute_plan ran, and the text quantity column was converted to numbers —
    a string column would have concatenated instead of summing."""
    _, conversation_id = conversation
    fake_agent(**READY_PLAN)

    body = (await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )).json()

    assert body["message"]["resultData"][0]["quantity"] == 2709.0


async def test_both_messages_are_persisted(client, conversation, headers, fake_agent):
    _, conversation_id = conversation
    fake_agent(**READY_PLAN)

    await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )
    history = (await client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    )).json()

    assert [m["role"] for m in history["messages"]] == ["user", "agent"]
    assert history["messages"][0]["content"] == "top product?"


async def test_the_conversation_is_autotitled_from_the_first_question(
    client, conversation, headers, fake_agent
):
    _, conversation_id = conversation
    fake_agent(**READY_PLAN)

    body = (await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "Which product has the highest total quantity sold?"},
        headers=headers,
    )).json()

    # The mock's substring(0, 25) + '...'
    assert body["conversation"]["title"] == "Which product has the hig..."


async def test_counters_move_with_the_messages(client, conversation, headers, fake_agent):
    _, conversation_id = conversation
    fake_agent(**READY_PLAN)

    body = (await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )).json()

    assert body["conversation"]["messageCount"] == 2


async def test_an_empty_question_is_rejected(client, conversation, headers):
    _, conversation_id = conversation

    response = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "   "},
        headers=headers,
    )

    assert response.status_code == 400


async def test_another_session_cannot_post_to_the_conversation(
    client, conversation, fake_agent
):
    _, conversation_id = conversation
    fake_agent(**READY_PLAN)

    response = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers={"X-Session-Id": str(uuid.uuid4())},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Clarification and cannot_answer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected",
    [
        (STATUSES["NEEDS_CLARIFICATION"], "needs_clarification"),
        (STATUSES["CANNOT_ANSWER"], "cannot_answer"),
    ],
)
async def test_a_non_answer_turn_carries_no_result_or_plan(
    client, conversation, headers, fake_agent, status, expected
):
    _, conversation_id = conversation
    fake_agent(
        status=status,
        analysis_plan=[],
        chart_plan=None,
        message="Please say which metric you mean.",
    )

    body = (await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "Show me the best"},
        headers=headers,
    )).json()
    message = body["message"]

    assert message["status"] == expected
    assert message["content"] == "Please say which metric you mean."
    assert message["resultData"] is None
    assert message["plan"] is None
    assert message["showChart"] is False


async def test_a_clarification_makes_no_explainer_call(
    client, conversation, headers, monkeypatch
):
    """There is nothing to explain, and on a 20-calls-a-day quota a wasted
    call matters."""
    from app.services import analysis_service

    calls = []

    def fake_run_agent(state):
        state.update(
            status=STATUSES["NEEDS_CLARIFICATION"],
            analysis_plan=[],
            chart_plan=None,
            message="Which metric?",
        )
        return state

    monkeypatch.setattr(analysis_service, "run_agent", fake_run_agent)
    monkeypatch.setattr(
        analysis_service,
        "explain_result",
        lambda *a, **k: calls.append(1) or "should not be called",
    )

    _, conversation_id = conversation
    await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "Show me the best"},
        headers=headers,
    )

    assert calls == []


# ---------------------------------------------------------------------------
# The invariant: never a user message without a reply
# ---------------------------------------------------------------------------


async def test_a_planner_failure_still_writes_an_agent_message(
    client, conversation, headers, monkeypatch
):
    from app.services import analysis_service

    def failing(state):
        state.update(status=STATUSES["FAILED"], error="planner exploded")
        return state

    monkeypatch.setattr(analysis_service, "run_agent", failing)

    _, conversation_id = conversation
    response = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )
    history = (await client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    )).json()

    assert response.status_code == 502
    assert [m["role"] for m in history["messages"]] == ["user", "agent"]
    assert history["messages"][1]["status"] == "failed"


async def test_an_execution_failure_still_writes_an_agent_message(
    client, conversation, headers, fake_agent
):
    _, conversation_id = conversation
    # limit_results with a bad keyword reaches execute_plan and raises.
    fake_agent(
        status=STATUSES["READY"],
        analysis_plan=[{"tool": "limit_results", "limit": 1, "bogus": True}],
        chart_plan=None,
        message=None,
    )

    response = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )
    history = (await client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    )).json()

    assert response.status_code == 502
    assert history["messages"][-1]["status"] == "failed"


async def test_an_llm_error_becomes_a_429_not_a_500(
    client, conversation, headers, monkeypatch
):
    from app.agent.llm import LLMRateLimited
    from app.services import analysis_service

    def rate_limited(state):
        raise LLMRateLimited("Out of quota for now.")

    monkeypatch.setattr(analysis_service, "run_agent", rate_limited)

    _, conversation_id = conversation
    response = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )
    history = (await client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    )).json()

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "LLM_RATE_LIMITED"
    assert history["messages"][-1]["status"] == "failed"


# ---------------------------------------------------------------------------
# Real unavailable_columns, and the chart check
# ---------------------------------------------------------------------------


async def test_the_planner_is_told_why_a_column_is_unavailable(
    client, conversation, headers, monkeypatch
):
    """The bug this fixes: the old endpoint dropped excluded columns and
    passed unavailable_columns={}, so the agent could only say "unknown
    column" and never "excluded for quality reasons"."""
    from app.services import analysis_service

    seen = {}

    def capture(state):
        seen.update(state)
        state.update(
            status=STATUSES["NEEDS_CLARIFICATION"],
            analysis_plan=[],
            chart_plan=None,
            message="n/a",
        )
        return state

    monkeypatch.setattr(analysis_service, "run_agent", capture)

    _, conversation_id = conversation
    await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "phone numbers?"},
        headers=headers,
    )

    assert "customer_phone" in seen["unavailable_columns"]
    assert "missing" in seen["unavailable_columns"]["customer_phone"]
    # And it must NOT be offered as usable.
    assert "customer_phone" not in seen["schema"]


async def test_an_unusable_chart_is_dropped_without_failing_the_turn(
    client, conversation, headers, fake_agent
):
    """A bad chart is cosmetic; failing the turn would throw away a correct
    analysis the user already paid for."""
    _, conversation_id = conversation
    plan = dict(READY_PLAN)
    plan["chart_plan"] = {
        "should_plot": True,
        "chart_type": "bar",
        "x": "NotAColumn",
        "y": "quantity",
    }
    fake_agent(**plan)

    body = (await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )).json()

    assert body["message"]["status"] == "ready"
    assert body["message"]["showChart"] is False
    assert body["message"]["resultData"]


async def test_a_scalar_result_is_marked_as_such(client, conversation, headers, fake_agent):
    _, conversation_id = conversation
    fake_agent(
        status=STATUSES["READY"],
        analysis_plan=[
            {"tool": "aggregate_data", "column": "Price", "operation": "mean"}
        ],
        chart_plan=None,
        message=None,
    )

    body = (await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "average price?"},
        headers=headers,
    )).json()

    assert body["message"]["resultKind"] == "scalar"
    assert isinstance(body["message"]["resultData"], (int, float))
    assert body["message"]["showChart"] is False


async def test_the_explainer_falling_silent_does_not_lose_the_turn(
    client, conversation, headers, monkeypatch
):
    """Better than the old behaviour, which raised and lost a turn whose
    analysis had already succeeded."""
    from app.services import analysis_service

    monkeypatch.setattr(
        analysis_service, "run_agent", lambda s: (s.update(READY_PLAN), s)[1]
    )
    monkeypatch.setattr(analysis_service, "explain_result", lambda *a, **k: "   ")

    _, conversation_id = conversation
    body = (await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "top product?"},
        headers=headers,
    )).json()

    assert body["message"]["status"] == "ready"
    assert body["message"]["content"].strip()


async def test_the_earliest_order_date_runs_end_to_end(
    client, conversation, headers, fake_agent
):
    """min on a date column, which the validator now allows.

    Two things only this path proves: the plan survives validation, and the
    Timestamp it produces comes back as an ISO string. A raw Timestamp is
    neither JSON-serialisable nor a valid jsonb value, so without the
    conversion this turn would 500 on persistence.
    """
    _, conversation_id = conversation
    fake_agent(
        status=STATUSES["READY"],
        analysis_plan=[
            {"tool": "aggregate_data", "column": "OrderDate", "operation": "min"}
        ],
        chart_plan=None,
        message=None,
    )

    response = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "What is the earliest order date?"},
        headers=headers,
    )
    message = response.json()["message"]

    assert response.status_code == 201
    assert message["status"] == "ready"
    assert message["resultKind"] == "scalar"
    # The first OrderDate in samples/orders.csv, which now starts in 2023.
    assert message["resultData"] == "2023-01-01T00:00:00"
    assert message["plan"]["steps"] == ["Calculate MINIMUM of OrderDate"]
    assert message["showChart"] is False


async def test_the_stored_message_round_trips_the_date(
    client, conversation, headers, fake_agent
):
    """Reading it back proves it was storable as jsonb, not just returnable."""
    _, conversation_id = conversation
    fake_agent(
        status=STATUSES["READY"],
        analysis_plan=[
            {"tool": "aggregate_data", "column": "OrderDate", "operation": "max"}
        ],
        chart_plan=None,
        message=None,
    )

    await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "What is the latest order date?"},
        headers=headers,
    )
    history = (
        await client.get(
            f"/api/conversations/{conversation_id}/messages", headers=headers
        )
    ).json()

    assert history["messages"][-1]["resultData"] == "2024-12-31T00:00:00"


# ---------------------------------------------------------------------------
# Event sequence from the generator itself
# ---------------------------------------------------------------------------


async def test_the_event_sequence_matches_the_contract(
    client, conversation, headers, fake_agent, db_factory
):
    """Endpoint 11 hides the events, so they are asserted on the generator.

    result must precede the first token, and exactly one of done/error ends
    the stream.
    """
    from app.services import analysis_service, conversation_service, dataset_service

    dataset_id, conversation_id = conversation
    fake_agent(**READY_PLAN)

    names = []
    async with db_factory() as db:
        owner = uuid.UUID(headers["X-Session-Id"])
        conv = await conversation_service.get_conversation(
            db, owner, uuid.UUID(conversation_id)
        )
        dataset = await dataset_service.get_dataset(db, owner, uuid.UUID(dataset_id))
        columns = await dataset_service.get_columns(db, owner, dataset.id)
        frame = await dataset_service.load_frame(db, owner, dataset.id)
        async for item in analysis_service.run_turn(
            db, conv, dataset, frame, columns, "top product?", history=[]
        ):
            names.append(item["event"])

    assert names[0] == "status"
    assert names[-1] == "done"
    assert names.count("done") == 1
    assert "error" not in names
    assert names.index("result") < names.index("token")
    assert len([n for n in names if n == "status"]) == 5


# ---------------------------------------------------------------------------
# Search — endpoint 14
# ---------------------------------------------------------------------------


async def test_search_finds_a_conversation_by_title(client, conversation, headers):
    _, conversation_id = conversation
    await client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "Revenue analysis"},
        headers=headers,
    )

    body = (await client.get("/api/conversations?q=revenue", headers=headers)).json()

    assert [c["id"] for c in body["conversations"]] == [conversation_id]
    assert body["conversations"][0]["datasetName"] == "orders.csv"


async def test_search_finds_a_conversation_by_message_content(
    client, conversation, headers, fake_agent
):
    _, conversation_id = conversation
    fake_agent(**READY_PLAN)
    await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "a very distinctive phrase"},
        headers=headers,
    )

    body = (await client.get("/api/conversations?q=distinctive", headers=headers)).json()

    assert [c["id"] for c in body["conversations"]] == [conversation_id]


async def test_search_is_scoped_to_the_session(client, conversation, headers):
    body = (await client.get(
        "/api/conversations?q=", headers={"X-Session-Id": str(uuid.uuid4())}
    )).json()

    assert body["conversations"] == []
