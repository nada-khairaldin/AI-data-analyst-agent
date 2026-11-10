"""Tests for agent/validators.py — the gate between the LLM and real execution.

Nothing the model produces reaches tools.py without passing through here, so
these tests are the project's security tests as much as its correctness tests.
Every case below is a plan the model could plausibly emit.
"""

import json

import pytest

from agent.schemas import STATUSES
from agent.validators import (
    get_final_result_columns,
    validate_agent_output,
    validate_analysis_plan,
    validate_chart_plan,
    validate_explainer_output,
    validate_plan_types,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def group_step():
    """A valid grouped aggregation — the most common real plan step."""
    return {
        "tool": "aggregate_data",
        "column": "Quantity",
        "operation": "sum",
        "group_by": "Product",
    }


def valid_chart():
    return {
        "should_plot": True,
        "chart_type": "bar",
        "x": "Product",
        "y": "Quantity",
    }


# ---------------------------------------------------------------------------
# validate_analysis_plan — structure
# ---------------------------------------------------------------------------


def test_empty_plan_is_rejected(schema):
    is_valid, error = validate_analysis_plan([], schema)

    assert is_valid is False
    assert error == "Analysis plan cannot be empty."


def test_a_step_that_is_not_an_object_is_rejected(schema):
    is_valid, error = validate_analysis_plan(["aggregate_data"], schema)

    assert is_valid is False
    assert "must be a dictionary" in error


def test_unknown_tool_is_rejected(schema):
    """The whitelist check. This is the single most important assertion here."""
    is_valid, error = validate_analysis_plan(
        [{"tool": "exec_python", "code": "import os"}], schema
    )

    assert is_valid is False
    assert error == "Unsupported tool: exec_python"


def test_group_data_is_not_a_tool(schema):
    """The planner prompt explicitly forbids "group_data"; this enforces it.

    Worth its own test because the prompt naming it makes the model MORE
    likely to emit it, not less.
    """
    is_valid, error = validate_analysis_plan(
        [{"tool": "group_data", "column": "Product"}], schema
    )

    assert is_valid is False
    assert "Unsupported tool" in error


def test_missing_required_parameter_is_rejected(schema):
    is_valid, error = validate_analysis_plan(
        [{"tool": "filter_data", "column": "Quantity"}], schema
    )

    assert is_valid is False
    assert "filter_data requires 'operator'" in error


def test_valid_grouped_plan_passes(schema):
    is_valid, error = validate_analysis_plan([group_step()], schema)

    assert is_valid is True
    assert error is None


# ---------------------------------------------------------------------------
# validate_analysis_plan — values and types
# ---------------------------------------------------------------------------


def test_invalid_filter_operator_is_rejected(schema):
    is_valid, error = validate_analysis_plan(
        [
            {
                "tool": "filter_data",
                "column": "Product",
                "operator": "contains",
                "value": "Lap",
            }
        ],
        schema,
    )

    assert is_valid is False
    assert "Invalid value for 'operator'" in error


def test_invalid_aggregation_operation_is_rejected(schema):
    is_valid, error = validate_analysis_plan(
        [{"tool": "aggregate_data", "column": "Quantity", "operation": "median"}],
        schema,
    )

    assert is_valid is False
    assert "Invalid value for 'operation'" in error


def test_limit_must_be_an_integer(schema):
    is_valid, error = validate_analysis_plan(
        [{"tool": "limit_results", "limit": "5"}], schema
    )

    assert is_valid is False
    assert "limit must be an integer" in error


def test_limit_rejects_a_boolean(schema):
    """bool is a subclass of int in Python, so this needs an explicit check.

    True would otherwise pass as limit=1 and silently truncate the answer to a
    single row.
    """
    is_valid, error = validate_analysis_plan(
        [{"tool": "limit_results", "limit": True}], schema
    )

    assert is_valid is False
    assert "limit must be an integer" in error


def test_limit_must_be_positive(schema):
    is_valid, error = validate_analysis_plan(
        [{"tool": "limit_results", "limit": 0}], schema
    )

    assert is_valid is False
    assert "limit must be greater than zero" in error


def test_ascending_must_be_a_boolean(schema):
    is_valid, error = validate_analysis_plan(
        [{"tool": "sort_data", "column": "Quantity", "ascending": "yes"}], schema
    )

    assert is_valid is False
    assert "ascending must be of type bool" in error


def test_select_columns_must_be_a_non_empty_list(schema):
    is_valid, error = validate_analysis_plan(
        [{"tool": "select_columns", "columns": []}], schema
    )

    assert is_valid is False
    assert "columns cannot be empty" in error


# ---------------------------------------------------------------------------
# validate_analysis_plan — columns must exist
# ---------------------------------------------------------------------------


def test_hallucinated_column_is_rejected(schema):
    """The model inventing a plausible column is the most common failure."""
    is_valid, error = validate_analysis_plan(
        [{"tool": "aggregate_data", "column": "Revenue", "operation": "sum"}],
        schema,
    )

    assert is_valid is False
    assert error == "Unknown column: Revenue"


def test_hallucinated_group_by_column_is_rejected(schema):
    is_valid, error = validate_analysis_plan(
        [
            {
                "tool": "aggregate_data",
                "column": "Quantity",
                "operation": "sum",
                "group_by": "Region",
            }
        ],
        schema,
    )

    assert is_valid is False
    assert error == "Unknown column: Region"


def test_every_column_in_a_list_is_checked(schema):
    is_valid, error = validate_analysis_plan(
        [{"tool": "select_columns", "columns": ["Product", "Margin"]}], schema
    )

    assert is_valid is False
    assert error == "Unknown column: Margin"


# ---------------------------------------------------------------------------
# validate_plan_types — the dataframe/scalar flow
# ---------------------------------------------------------------------------


def test_a_step_after_a_scalar_is_rejected():
    """aggregate without group_by yields a scalar; nothing can follow it.

    This is correct but strict: it is the reason some genuinely answerable
    questions come back as cannot_answer (docs/PLAN.md risk 25).
    """
    plan = [
        {"tool": "aggregate_data", "column": "Quantity", "operation": "sum"},
        {"tool": "sort_data", "column": "Quantity", "ascending": False},
    ]

    is_valid, error = validate_plan_types(plan)

    assert is_valid is False
    assert "expects input type 'dataframe'" in error
    assert "received 'scalar'" in error


def test_a_grouped_aggregation_can_be_followed_by_more_steps():
    plan = [
        group_step(),
        {"tool": "sort_data", "column": "Quantity", "ascending": False},
        {"tool": "limit_results", "limit": 5},
    ]

    is_valid, error = validate_plan_types(plan)

    assert is_valid is True
    assert error is None


# ---------------------------------------------------------------------------
# get_final_result_columns
# ---------------------------------------------------------------------------


def test_final_columns_after_a_grouped_aggregation(schema):
    assert get_final_result_columns([group_step()], schema) == {
        "Product",
        "Quantity",
    }


def test_final_columns_is_none_for_a_scalar_result(schema):
    """None is the signal "there is no table", which the chart check relies on."""
    plan = [{"tool": "aggregate_data", "column": "Quantity", "operation": "sum"}]

    assert get_final_result_columns(plan, schema) is None


def test_select_columns_replaces_the_column_set(schema):
    plan = [{"tool": "select_columns", "columns": ["Product"]}]

    assert get_final_result_columns(plan, schema) == {"Product"}


# ---------------------------------------------------------------------------
# validate_chart_plan
# ---------------------------------------------------------------------------


def test_chart_plan_must_be_an_object(schema):
    is_valid, error = validate_chart_plan(None, [group_step()], schema)

    assert is_valid is False
    assert "must be an object" in error


def test_should_plot_must_be_a_boolean(schema):
    is_valid, error = validate_chart_plan(
        {"should_plot": "yes"}, [group_step()], schema
    )

    assert is_valid is False
    assert "'should_plot' must be a boolean" in error


def test_no_chart_requires_all_chart_fields_to_be_null(schema):
    is_valid, error = validate_chart_plan(
        {"should_plot": False, "chart_type": "bar", "x": None, "y": None},
        [group_step()],
        schema,
    )

    assert is_valid is False
    assert "must be null when should_plot is false" in error


def test_no_chart_with_clean_nulls_passes(schema):
    is_valid, error = validate_chart_plan(
        {"should_plot": False, "chart_type": None, "x": None, "y": None},
        [group_step()],
        schema,
    )

    assert is_valid is True
    assert error is None


def test_unsupported_chart_type_is_rejected(schema):
    chart = valid_chart() | {"chart_type": "radar"}

    is_valid, error = validate_chart_plan(chart, [group_step()], schema)

    assert is_valid is False
    assert "Unsupported chart type: radar" in error


def test_a_chart_cannot_be_drawn_from_a_scalar(schema):
    plan = [{"tool": "aggregate_data", "column": "Quantity", "operation": "sum"}]

    is_valid, error = validate_chart_plan(valid_chart(), plan, schema)

    assert is_valid is False
    assert "cannot be created from a scalar result" in error


def test_chart_axis_must_exist_in_the_predicted_result(schema):
    """The column exists in the dataset but NOT in the aggregated output.

    This is the check that makes chart_plan trustworthy: "Country" is a real
    column, but a group-by on Product has already discarded it.
    """
    chart = valid_chart() | {"x": "Country"}

    is_valid, error = validate_chart_plan(chart, [group_step()], schema)

    assert is_valid is False
    assert "Chart x column 'Country'" in error


def test_valid_chart_passes(schema):
    is_valid, error = validate_chart_plan(valid_chart(), [group_step()], schema)

    assert is_valid is True
    assert error is None


# ---------------------------------------------------------------------------
# validate_agent_output — the full envelope
# ---------------------------------------------------------------------------


def test_non_json_output_is_rejected(schema):
    is_valid, output, error = validate_agent_output("Sure! Here is the plan:", schema)

    assert is_valid is False
    assert output is None
    assert error == "The model returned invalid JSON."


def test_json_that_is_not_an_object_is_rejected(schema):
    is_valid, output, error = validate_agent_output("[1, 2, 3]", schema)

    assert is_valid is False
    assert "must be a dictionary" in error


def test_unknown_status_is_rejected(schema):
    raw = json.dumps({"status": "success", "analysis_plan": []})

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert "Invalid status: success" in error


def test_completed_status_is_not_acceptable_from_the_model(schema):
    """STATUSES has six values but the model may only return three.

    pending/completed/failed are internal states; the model claiming one would
    bypass the plan checks entirely.
    """
    raw = json.dumps({"status": STATUSES["COMPLETED"], "analysis_plan": []})

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert "Invalid status" in error


def test_analysis_plan_is_required(schema):
    raw = json.dumps({"status": "ready"})

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert error == "analysis_plan is required."


def test_analysis_plan_must_be_a_list(schema):
    raw = json.dumps({"status": "ready", "analysis_plan": {"tool": "limit_results"}})

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert "must be a list" in error


def test_a_complete_ready_output_passes(schema):
    raw = json.dumps(
        {
            "status": "ready",
            "message": None,
            "analysis_plan": [group_step()],
            "chart_plan": valid_chart(),
        }
    )

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is True
    assert error is None
    assert output["status"] == "ready"


def test_ready_output_with_a_bad_plan_is_rejected(schema):
    raw = json.dumps(
        {
            "status": "ready",
            "analysis_plan": [
                {"tool": "aggregate_data", "column": "Revenue", "operation": "sum"}
            ],
            "chart_plan": {
                "should_plot": False,
                "chart_type": None,
                "x": None,
                "y": None,
            },
        }
    )

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert error == "Unknown column: Revenue"


def test_clarification_requires_a_message(schema):
    raw = json.dumps(
        {"status": "needs_clarification", "message": "", "analysis_plan": []}
    )

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert "requires a message" in error


def test_clarification_must_have_an_empty_plan(schema):
    raw = json.dumps(
        {
            "status": "needs_clarification",
            "message": "By quantity or revenue?",
            "analysis_plan": [group_step()],
        }
    )

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert "must have an empty analysis_plan" in error


def test_clarification_must_have_a_null_chart_plan(schema):
    raw = json.dumps(
        {
            "status": "needs_clarification",
            "message": "By quantity or revenue?",
            "analysis_plan": [],
            "chart_plan": valid_chart(),
        }
    )

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is False
    assert "chart_plan set to null" in error


def test_a_well_formed_clarification_passes(schema):
    raw = json.dumps(
        {
            "status": "needs_clarification",
            "message": "Do you mean total quantity or total revenue?",
            "analysis_plan": [],
            "chart_plan": None,
        }
    )

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is True
    assert output["message"].startswith("Do you mean")


def test_a_well_formed_cannot_answer_passes(schema):
    raw = json.dumps(
        {
            "status": "cannot_answer",
            "message": "Forecasting is not supported.",
            "analysis_plan": [],
            "chart_plan": None,
        }
    )

    is_valid, output, error = validate_agent_output(raw, schema)

    assert is_valid is True
    assert output["status"] == "cannot_answer"


# ---------------------------------------------------------------------------
# validate_explainer_output
#
# Note: this function becomes dead code when the explainer switches to plain
# text for streaming (docs/PLAN.md §6B, risk 13). It is tested here because
# A2 is a snapshot of today's behaviour, and because the empty-summary rule it
# enforces has to be reimplemented in the stream generator.
# ---------------------------------------------------------------------------


def test_explainer_output_must_be_json():
    is_valid, summary, error = validate_explainer_output("Laptop sold the most.")

    assert is_valid is False
    assert "invalid JSON" in error


def test_explainer_summary_must_not_be_empty():
    is_valid, summary, error = validate_explainer_output(json.dumps({"summary": "  "}))

    assert is_valid is False
    assert "non-empty summary" in error


def test_valid_explainer_output_returns_the_summary():
    raw = json.dumps({"summary": "Laptop has the highest total quantity, 25 units."})

    is_valid, summary, error = validate_explainer_output(raw)

    assert is_valid is True
    assert summary.startswith("Laptop")
    assert error is None
