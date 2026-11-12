"""Tests for the condenser (phase C1).

The condenser is a pure string -> dict function, which is the main reason this
design was chosen over feeding history to the planner: a failure here is one
diffable line rather than an end-to-end mystery.

The failure mode that matters most is a *confidently wrong* answer — a
mis-condensed question plans the wrong thing perfectly. So most of these tests
are about the guard: anything the model returns that is not unambiguously
usable must become a pass-through.
"""

import pytest

from app.services import condenser


# ---------------------------------------------------------------------------
# The happy shapes
# ---------------------------------------------------------------------------


def test_a_question_is_returned():
    result = condenser.parse(
        '{"kind": "question", "question": "Show total quantity per month"}', "raw"
    )

    assert result == {
        "kind": "question",
        "question": "Show total quantity per month",
        "fell_back": False,
    }


def test_an_instruction_returns_an_acknowledgement():
    """1 LLM call instead of 3: no planner, no explainer."""
    result = condenser.parse(
        '{"kind": "instruction", "acknowledgement": "Got it - 2024 only."}', "raw"
    )

    assert result["kind"] == "instruction"
    assert result["acknowledgement"] == "Got it - 2024 only."
    assert "question" not in result


def test_a_clarification_answer_keeps_its_kind():
    """The UI shows it as a question, but the kind records that the user was
    answering rather than asking."""
    result = condenser.parse(
        '{"kind": "clarification_answer", "question": "Which product by quantity?"}',
        "raw",
    )

    assert result["kind"] == "clarification_answer"
    assert result["question"] == "Which product by quantity?"


def test_a_fenced_reply_is_parsed():
    """Gemini fences JSON; A9's strip_code_fence is reused rather than
    reimplemented."""
    result = condenser.parse(
        '```json\n{"kind": "question", "question": "Totals per month"}\n```', "raw"
    )

    assert result["question"] == "Totals per month"
    assert result["fell_back"] is False


def test_a_bare_line_is_accepted_as_a_question():
    """The pre-JSON design returned plain text, and a clean single line is
    still usable — discarding it would waste a call for nothing."""
    result = condenser.parse("Show total quantity per month", "raw")

    assert result["question"] == "Show total quantity per month"
    assert result["fell_back"] is False


def test_a_question_label_is_stripped():
    result = condenser.parse('{"kind":"question","question":"Question: totals?"}', "raw")

    assert result["question"] == "totals?"


# ---------------------------------------------------------------------------
# The guard — every doubt becomes a pass-through
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,why",
    [
        ("", "empty"),
        ("   \n  ", "whitespace only"),
        ("[1, 2, 3]", "JSON that is not an object"),
        ('{"kind": "chitchat", "question": "hi"}', "unknown kind"),
        ('{"question": "no kind at all"}', "missing kind"),
        ('{"kind": "instruction"}', "instruction with no acknowledgement"),
        ('{"kind": "instruction", "acknowledgement": "  "}', "blank acknowledgement"),
        ('{"kind": "question", "question": ""}', "empty question"),
        ('{"kind": "question", "question": "a\\nb"}', "multi-line question"),
        ('{"kind": "question", "question": "' + "x" * 400 + '"}', "over 300 chars"),
        ("Sure! Here is what I think:\nThe user wants monthly totals.", "prose"),
    ],
)
def test_anything_ambiguous_falls_back_to_the_raw_message(raw, why):
    result = condenser.parse(raw, "RAW USER MESSAGE")

    assert result["kind"] == "question", why
    assert result["question"] == "RAW USER MESSAGE", why
    assert result["fell_back"] is True, why


def test_truncated_json_is_not_mistaken_for_a_question():
    """Found while building this: the bare-line branch accepted
    '{"kind": "question", "question' as the question itself. Planning from a
    fragment of JSON is worse than falling back."""
    result = condenser.parse('{"kind": "question", "question"', "RAW")

    assert result["fell_back"] is True
    assert result["question"] == "RAW"


def test_a_model_failure_falls_back_rather_than_raising(monkeypatch):
    def boom(prompt, role=None):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(condenser, "complete", boom)

    result = condenser.condense(
        question="now per month",
        schema={"a": "int64"},
        excluded_columns={},
        fact_sheet="",
        window="",
    )

    assert result["fell_back"] is True
    assert result["question"] == "now per month"


def test_a_rate_limit_still_propagates(monkeypatch):
    """An infrastructure failure the user must be told about, unlike a model
    that simply answered badly."""
    from app.agent.llm import LLMRateLimited

    def rate_limited(prompt, role=None):
        raise LLMRateLimited("out of quota")

    monkeypatch.setattr(condenser, "complete", rate_limited)

    with pytest.raises(LLMRateLimited):
        condenser.condense(
            question="now per month",
            schema={},
            excluded_columns={},
            fact_sheet="",
            window="",
        )


def test_the_kill_switch_skips_the_call(monkeypatch):
    """CONDENSER_ENABLED=false degrades to "no follow-up understanding"
    instead of failing — the right behaviour at a quota wall."""
    calls = []
    monkeypatch.setattr(condenser.settings, "condenser_enabled", False, raising=False)
    monkeypatch.setattr(condenser, "complete", lambda *a, **k: calls.append(1))

    result = condenser.condense(
        question="now per month",
        schema={},
        excluded_columns={},
        fact_sheet="",
        window="",
    )

    assert calls == []
    assert result["question"] == "now per month"
    assert result["fell_back"] is True


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------


def test_the_prompt_carries_schema_excluded_facts_and_window():
    prompt = condenser.build_prompt(
        question="now per month",
        schema={"Product": "str", "quantity": "float64"},
        excluded_columns={"customer_phone": "73.9% missing"},
        fact_sheet="Active filters/assumptions:\n- 2024 only",
        window="user: which product?\n  agent: Mouse",
    )

    assert "Product: str" in prompt
    assert "customer_phone: 73.9% missing" in prompt
    assert "2024 only" in prompt
    assert "which product?" in prompt
    assert "now per month" in prompt


def test_the_prompt_says_none_rather_than_leaving_a_blank():
    """An empty section invites the model to fill it in."""
    prompt = condenser.build_prompt(
        question="q", schema={}, excluded_columns={}, fact_sheet=None, window=None
    )

    assert prompt.count("none") >= 3


def test_the_prompt_has_no_unfilled_placeholders():
    prompt = condenser.build_prompt(
        question="q",
        schema={"a": "int64"},
        excluded_columns={},
        fact_sheet="",
        window="",
    )

    # The JSON examples use {{ }} so they survive substitution; anything else
    # left in braces would be a placeholder nobody filled.
    assert "{schema}" not in prompt
    assert "{question}" not in prompt
    assert "{fact_sheet}" not in prompt
    assert "{window}" not in prompt
    assert "{excluded_columns}" not in prompt


def test_the_prompt_forbids_answering():
    """The one instruction that stops the condenser becoming a second agent."""
    prompt = condenser.build_prompt(
        question="q", schema={}, excluded_columns={}, fact_sheet="", window=""
    )

    assert "Never answer the question" in prompt


def test_the_json_examples_in_the_prompt_are_real_json():
    """Found a bug here: the template used {{ }} as if it were a format
    string, but substitution is .replace(), so the model was shown literal
    double braces and asked to return them.
    """
    import json

    prompt = condenser.build_prompt(
        question="q", schema={}, excluded_columns={}, fact_sheet="", window=""
    )

    examples = [
        line.strip()
        for line in prompt.splitlines()
        if line.strip().startswith('{"kind"')
    ]
    assert len(examples) == 3, "all three kinds must be shown"

    for example in examples:
        placeholder_free = (
            example.replace("<one standalone question>", "x")
            .replace("<the question the user meant>", "x")
            .replace("<one short sentence confirming it>", "x")
        )
        parsed = json.loads(placeholder_free)
        assert parsed["kind"] in condenser.KINDS


def test_no_doubled_braces_survive_into_the_prompt():
    prompt = condenser.build_prompt(
        question="q", schema={}, excluded_columns={}, fact_sheet="", window=""
    )

    assert "{{" not in prompt
    assert "}}" not in prompt
