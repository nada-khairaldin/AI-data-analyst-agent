"""Tests for tools.py — the five whitelisted pandas operations and execute_plan.

This module is the project's core safety boundary: it is the ONLY place where
an LLM-authored plan turns into real computation, and it executes nothing but
these five functions. A test that passes here is a guarantee that no
AI-generated Python ran.
"""

import pandas as pd
import pytest

from tools import (
    TOOL_REGISTRY,
    aggregate_data,
    execute_plan,
    filter_data,
    limit_results,
    select_columns,
    sort_data,
)


# ---------------------------------------------------------------------------
# The registry is the whitelist
# ---------------------------------------------------------------------------


def test_registry_contains_exactly_the_five_approved_tools():
    """Adding a tool here widens what the LLM is allowed to cause.

    This test exists so that widening the whitelist is a deliberate, reviewed
    act rather than a side effect.
    """
    assert set(TOOL_REGISTRY) == {
        "filter_data",
        "aggregate_data",
        "sort_data",
        "select_columns",
        "limit_results",
    }


# ---------------------------------------------------------------------------
# filter_data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "operator,value,expected_quantities",
    [
        ("equals", 10, [10]),
        ("not_equals", 10, [5, 15, 7, 3]),
        ("greater_than", 7, [10, 15]),
        ("less_than", 7, [5, 3]),
        ("greater_than_or_equal", 7, [10, 15, 7]),
        ("less_than_or_equal", 7, [5, 7, 3]),
    ],
)
def test_every_filter_operator(orders_df, operator, value, expected_quantities):
    result = filter_data(orders_df, "Quantity", operator, value)

    assert list(result["Quantity"]) == expected_quantities


def test_unsupported_filter_operator_raises(orders_df):
    """The error must be raised, not silently ignored.

    A silently-dropped filter would return MORE rows than asked for and the
    explainer would describe them as filtered — a wrong answer presented
    confidently.
    """
    with pytest.raises(ValueError, match="Unsupported operator: contains"):
        filter_data(orders_df, "Product", "contains", "Lap")


def test_filter_on_a_string_column(orders_df):
    result = filter_data(orders_df, "Country", "equals", "FR")

    assert len(result) == 2
    assert set(result["Product"]) == {"Mouse"}


def test_filter_does_not_mutate_the_input(orders_df):
    before = len(orders_df)

    filter_data(orders_df, "Quantity", "greater_than", 7)

    assert len(orders_df) == before


# ---------------------------------------------------------------------------
# aggregate_data
# ---------------------------------------------------------------------------


def test_aggregate_without_group_by_returns_a_scalar(orders_df):
    """This is the shape the frontend has no renderer for (Suggested change S4).

    10 + 5 + 15 + 7 + 3 = 40. The return value is a numpy scalar, NOT a
    DataFrame, which is why result_kind exists in the message schema.
    """
    result = aggregate_data(orders_df, "Quantity", "sum")

    assert not isinstance(result, pd.DataFrame)
    assert result == 40


def test_aggregate_with_group_by_returns_a_two_column_frame(orders_df):
    result = aggregate_data(orders_df, "Quantity", "sum", group_by="Product")

    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ["Product", "Quantity"]

    totals = dict(zip(result["Product"], result["Quantity"]))
    assert totals == {"Laptop": 25, "Mouse": 8, "Keyboard": 7}


@pytest.mark.parametrize(
    "operation,expected",
    [("sum", 40), ("count", 5), ("min", 3), ("max", 15), ("mean", 8.0)],
)
def test_every_aggregation_operation(orders_df, operation, expected):
    result = aggregate_data(orders_df, "Quantity", operation)

    assert result == pytest.approx(expected)


def test_unsupported_aggregation_raises(orders_df):
    with pytest.raises(ValueError, match="Unsupported aggregation operation"):
        aggregate_data(orders_df, "Quantity", "median")


def test_unsupported_aggregation_raises_with_group_by_too(orders_df):
    """Covers the grouped branch, which falls through to the same raise.

    Easy to miss: the grouped path has its own if-chain, so a bad operation
    there reaches the final raise only because no branch returned first.
    """
    with pytest.raises(ValueError, match="Unsupported aggregation operation"):
        aggregate_data(orders_df, "Quantity", "median", group_by="Product")


# ---------------------------------------------------------------------------
# sort_data, limit_results, select_columns
# ---------------------------------------------------------------------------


def test_sort_descending(orders_df):
    result = sort_data(orders_df, "Quantity", ascending=False)

    assert list(result["Quantity"]) == [15, 10, 7, 5, 3]


def test_sort_ascending(orders_df):
    result = sort_data(orders_df, "Quantity", ascending=True)

    assert list(result["Quantity"]) == [3, 5, 7, 10, 15]


def test_limit_results(orders_df):
    result = limit_results(orders_df, 2)

    assert len(result) == 2


def test_limit_larger_than_the_frame_is_not_an_error(orders_df):
    result = limit_results(orders_df, 500)

    assert len(result) == 5


def test_select_columns(orders_df):
    result = select_columns(orders_df, ["Product", "Quantity"])

    assert list(result.columns) == ["Product", "Quantity"]


def test_select_columns_preserves_the_requested_order(orders_df):
    result = select_columns(orders_df, ["Quantity", "Product"])

    assert list(result.columns) == ["Quantity", "Product"]


# ---------------------------------------------------------------------------
# execute_plan
# ---------------------------------------------------------------------------


def test_execute_plan_runs_a_single_step(orders_df):
    plan = [{"tool": "aggregate_data", "column": "Quantity", "operation": "sum"}]

    assert execute_plan(orders_df, plan) == 40


def test_execute_plan_runs_the_canonical_four_step_analysis(orders_df):
    """The exact plan behind the mock answer in the UI.

    "Which product has the highest total quantity sold?" -> Laptop, 25.
    """
    plan = [
        {
            "tool": "filter_data",
            "column": "Quantity",
            "operator": "greater_than",
            "value": 0,
        },
        {
            "tool": "aggregate_data",
            "column": "Quantity",
            "operation": "sum",
            "group_by": "Product",
        },
        {"tool": "sort_data", "column": "Quantity", "ascending": False},
        {"tool": "limit_results", "limit": 1},
    ]

    result = execute_plan(orders_df, plan)

    assert len(result) == 1
    assert result.iloc[0]["Product"] == "Laptop"
    assert result.iloc[0]["Quantity"] == 25


def test_execute_plan_strips_the_tool_key_before_calling(orders_df):
    """Every key except "tool" is forwarded as a keyword argument.

    So an unexpected extra key in a step becomes a TypeError, not a silently
    ignored field — which is the safe direction, and is why validators.py
    checks the parameter names before this ever runs.
    """
    plan = [{"tool": "limit_results", "limit": 1, "unexpected": True}]

    with pytest.raises(TypeError):
        execute_plan(orders_df, plan)


def test_execute_plan_on_an_empty_plan_returns_the_frame_unchanged(orders_df):
    result = execute_plan(orders_df, [])

    assert len(result) == len(orders_df)


def test_execute_plan_does_not_mutate_the_input(orders_df):
    """execute_plan copies first — the user's working frame is shared state.

    Without the copy, one question's filter would narrow the dataset for every
    later question in the conversation.
    """
    plan = [
        {
            "tool": "filter_data",
            "column": "Quantity",
            "operator": "greater_than",
            "value": 7,
        }
    ]

    execute_plan(orders_df, plan)

    assert len(orders_df) == 5


def test_execute_plan_raises_on_an_unknown_tool(orders_df):
    """Defence in depth: validators.py should have caught this already."""
    with pytest.raises(KeyError):
        execute_plan(orders_df, [{"tool": "drop_table"}])
