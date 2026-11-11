"""Tests for strip_code_fence (phase A9).

This function exists because of a measured cost, not tidiness: the planner
wrapped its JSON in a ```json fence on attempt 1 of every question in the A8
run, json.loads failed, and the retry spent a second planner call. Against a
20-requests-per-day quota that was the difference between ~20 and ~10
questions a day.

So the two properties that matter are: it strips a real fence, and it never
mangles a reply that was already fine.
"""

import pytest

from app.agent.text_utils import strip_code_fence


# ---------------------------------------------------------------------------
# It strips what it should
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"status": "ready"}\n```',
        '```JSON\n{"status": "ready"}\n```',
        '```\n{"status": "ready"}\n```',
        '```json\r\n{"status": "ready"}\r\n```',
        '  ```json\n{"status": "ready"}\n```  ',
        '```json   \n{"status": "ready"}\n   ```',
    ],
)
def test_a_wrapping_fence_is_removed(raw):
    assert strip_code_fence(raw) == '{"status": "ready"}'


def test_a_multiline_body_survives():
    raw = '```json\n{\n  "status": "ready",\n  "analysis_plan": []\n}\n```'

    result = strip_code_fence(raw)

    assert result.startswith("{")
    assert result.endswith("}")
    assert '"analysis_plan"' in result


def test_backticks_inside_the_body_are_kept():
    """A fence is only the outermost wrapper; the body is not sanitised."""
    raw = '```json\n{"note": "use `pandas` here"}\n```'

    assert strip_code_fence(raw) == '{"note": "use `pandas` here"}'


def test_an_unterminated_fence_is_salvaged():
    """What a reply truncated at max_output_tokens looks like.

    The body is often still complete enough to parse, so it is worth
    recovering rather than failing the whole turn.
    """
    assert strip_code_fence('```json\n{"status": "ready"}') == '{"status": "ready"}'


def test_a_truncated_closing_marker_is_removed():
    assert strip_code_fence('```json\n{"a": 1}\n`') == '{"a": 1}'


# ---------------------------------------------------------------------------
# It leaves alone what it should
# ---------------------------------------------------------------------------


def test_plain_json_is_unchanged():
    assert strip_code_fence('{"status": "ready"}') == '{"status": "ready"}'


def test_prose_is_unchanged():
    text = "The product with the highest total quantity sold is the Mouse."

    assert strip_code_fence(text) == text


def test_a_fence_in_the_middle_of_prose_is_left_alone():
    """Deliberately conservative.

    Guessing which part of a mixed reply was "the answer" is how a parser
    starts silently picking the wrong one. If the model returns prose around a
    fenced block, that is a planner failure and should be reported as one, not
    papered over here.
    """
    raw = 'Here is the plan:\n```json\n{"a": 1}\n```\nHope that helps.'

    assert strip_code_fence(raw) == raw


def test_an_empty_string_stays_empty():
    assert strip_code_fence("") == ""


def test_whitespace_only_becomes_empty():
    assert strip_code_fence("   \n  ") == ""


@pytest.mark.parametrize("value", [None, 42, [], {"a": 1}])
def test_non_strings_pass_straight_through(value):
    """Safe to apply blindly to whatever a provider hands back."""
    assert strip_code_fence(value) is value


def test_it_is_idempotent():
    once = strip_code_fence('```json\n{"a": 1}\n```')

    assert strip_code_fence(once) == once


# ---------------------------------------------------------------------------
# The thing this is actually for
# ---------------------------------------------------------------------------


def test_the_real_a8_planner_output_now_parses_first_time():
    """Verbatim from the A8 verification run, which needed a second call."""
    import json

    raw = (
        '```json\n'
        '{\n  "status": "ready",\n  "message": null,\n'
        '  "analysis_plan": [\n'
        '    { "tool": "aggregate_data", "column": "Quantity",'
        ' "operation": "sum", "group_by": "Product" }\n  ],\n'
        '  "chart_plan": { "should_plot": false, "chart_type": null,'
        ' "x": null, "y": null }\n}\n'
        '```'
    )

    parsed = json.loads(strip_code_fence(raw))

    assert parsed["status"] == "ready"
    assert parsed["analysis_plan"][0]["group_by"] == "Product"


def test_the_stripped_output_satisfies_the_real_validator():
    """End to end through the actual validator, with no retry involved."""
    from app.agent.validators import validate_agent_output

    schema = {"Product": "str", "Quantity": "int64"}
    raw = (
        '```json\n{"status": "ready", "message": null, "analysis_plan": '
        '[{"tool": "aggregate_data", "column": "Quantity", "operation": "sum",'
        ' "group_by": "Product"}], "chart_plan": {"should_plot": true,'
        ' "chart_type": "bar", "x": "Product", "y": "Quantity"}}\n```'
    )

    is_valid, output, error = validate_agent_output(strip_code_fence(raw), schema)

    assert is_valid is True, error
    assert output["status"] == "ready"


def test_the_fenced_output_fails_the_validator_without_stripping():
    """Proves the cost being avoided: this is the call that used to be wasted."""
    from app.agent.validators import validate_agent_output

    raw = '```json\n{"status": "ready", "analysis_plan": []}\n```'

    is_valid, output, error = validate_agent_output(raw, {"Product": "str"})

    assert is_valid is False
    assert "invalid JSON" in error
