"""Unit tests for the pure helpers in analysis_service (phase B2).

No database and no app: these are the functions that decide what the client
sees, so they are worth testing without the cost of a Neon round trip. The
turn itself is covered in tests/api/test_chat_api.py.
"""

import numpy as np
import pandas as pd
import pytest

from app.services import analysis_service as svc


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_a_frame_is_a_table():
    assert svc.result_kind(pd.DataFrame({"a": [1]})) == "table"


def test_a_scalar_is_a_scalar():
    """An aggregation with no group_by returns a scalar, not rows. Without
    this the UI has to guess from the JSON type (Suggested change S4)."""
    assert svc.result_kind(np.float64(3.5)) == "scalar"


def test_frame_rows_serialise_to_records():
    frame = pd.DataFrame({"Product": ["Mouse"], "quantity": [45.0]})

    assert svc.serialise_result(frame) == [{"Product": "Mouse", "quantity": 45.0}]


def test_missing_values_serialise_as_null():
    frame = pd.DataFrame({"a": [1.0, None]})

    assert svc.serialise_result(frame) == [{"a": 1.0}, {"a": None}]


def test_numpy_scalars_become_plain_python():
    """json.dumps cannot serialise a numpy scalar."""
    result = svc.serialise_result(np.float64(396.57))

    assert isinstance(result, float)
    assert result == pytest.approx(396.57)


# ---------------------------------------------------------------------------
# Chart validation — drop the chart, keep the answer
# ---------------------------------------------------------------------------


@pytest.fixture
def grouped():
    return pd.DataFrame({"Product": ["Mouse", "Laptop"], "quantity": [45.0, 9.0]})


def test_a_valid_chart_survives(grouped):
    chart = {"should_plot": True, "chart_type": "bar", "x": "Product", "y": "quantity"}

    assert svc._validated_chart(grouped, chart) == chart


def test_a_chart_naming_a_missing_column_is_dropped(grouped):
    """validators.py checked the plan's predicted columns; this checks the
    data that actually came out."""
    chart = {"should_plot": True, "chart_type": "bar", "x": "Nope", "y": "quantity"}

    assert svc._validated_chart(grouped, chart)["should_plot"] is False


def test_a_chart_with_a_non_numeric_axis_is_dropped(grouped):
    chart = {"should_plot": True, "chart_type": "bar", "x": "quantity", "y": "Product"}

    assert svc._validated_chart(grouped, chart)["should_plot"] is False


def test_a_chart_on_a_scalar_is_dropped():
    chart = {"should_plot": True, "chart_type": "bar", "x": "a", "y": "b"}

    assert svc._validated_chart(np.float64(1.0), chart)["should_plot"] is False


def test_a_chart_on_an_empty_frame_is_dropped():
    chart = {"should_plot": True, "chart_type": "bar", "x": "Product", "y": "quantity"}
    empty = pd.DataFrame({"Product": [], "quantity": []})

    assert svc._validated_chart(empty, chart)["should_plot"] is False


def test_no_chart_requested_is_normalised(grouped):
    """Always the same shape, so the serializer never sees a partial dict."""
    assert svc._validated_chart(grouped, None) == {
        "should_plot": False,
        "chart_type": None,
        "x": None,
        "y": None,
    }


# ---------------------------------------------------------------------------
# The explainer fallback
# ---------------------------------------------------------------------------


def test_a_single_row_result_is_described():
    """The old code raised when the explainer produced nothing, losing a turn
    whose analysis had already succeeded and already been paid for."""
    frame = pd.DataFrame({"Product": ["Mouse"], "quantity": [45.0]})

    answer = svc._fallback_answer(frame, [])

    assert "Mouse" in answer
    assert "45" in answer


def test_a_multi_row_result_is_counted():
    frame = pd.DataFrame({"a": [1, 2, 3]})

    assert "3 rows" in svc._fallback_answer(frame, [])


def test_an_empty_result_says_so():
    assert "no rows" in svc._fallback_answer(pd.DataFrame({"a": []}), [])


def test_a_scalar_result_is_stated():
    assert "396" in svc._fallback_answer(np.float64(396.57), [])


# ---------------------------------------------------------------------------
# Token chunking
# ---------------------------------------------------------------------------


def test_text_is_chunked_into_several_pieces():
    text = "The product with the highest total quantity sold is the Mouse, 45 units."

    chunks = list(svc._as_chunks(text))

    assert len(chunks) > 1
    assert "".join(chunks).split() == text.split()


def test_empty_text_yields_nothing():
    assert list(svc._as_chunks("")) == []
    assert list(svc._as_chunks(None)) == []


def test_short_text_still_yields_once():
    assert "".join(svc._as_chunks("OK")).strip() == "OK"


# ---------------------------------------------------------------------------
# Stage labels
# ---------------------------------------------------------------------------


def test_the_five_contract_stages_all_have_labels():
    """`label` is the display string so wording changes need no frontend
    deploy; a missing one would be a KeyError mid-turn."""
    assert set(svc.STAGE_LABELS) == {
        "condensing",
        "planning",
        "validating",
        "executing",
        "explaining",
    }
    assert all(svc.STAGE_LABELS.values())


def test_a_status_event_carries_stage_and_label():
    item = svc._status("planning")

    assert item["event"] == "status"
    assert item["data"]["stage"] == "planning"
    assert item["data"]["label"]


# ---------------------------------------------------------------------------
# Derived calendar columns (phase D0)
# ---------------------------------------------------------------------------


def test_a_datetime_column_gains_year_and_month():
    """"Per month" needs something to group by: tools.py has no date
    truncation, so without these the planner can only group by the raw date
    and answer per DAY."""
    from app.services.dataset_service import add_calendar_columns

    frame = pd.DataFrame({"OrderDate": pd.to_datetime(["2023-01-05", "2024-12-31"])})

    result = add_calendar_columns(frame)

    assert list(result["OrderDate_year"]) == [2023, 2024]
    assert list(result["OrderDate_month"]) == ["2023-01", "2024-12"]


def test_the_year_column_is_numeric_so_it_can_be_filtered():
    from app.agent.validators import dtype_kind
    from app.services.dataset_service import add_calendar_columns

    frame = add_calendar_columns(
        pd.DataFrame({"d": pd.to_datetime(["2024-01-01"])})
    )

    assert dtype_kind(str(frame["d_year"].dtype)) == "numeric"
    # The month is text, so it can be grouped by but never summed.
    assert dtype_kind(str(frame["d_month"].dtype)) == "other"


def test_non_datetime_columns_are_left_alone():
    from app.services.dataset_service import add_calendar_columns

    frame = add_calendar_columns(pd.DataFrame({"a": [1], "b": ["x"]}))

    assert list(frame.columns) == ["a", "b"]


def test_missing_dates_do_not_break_the_derived_columns():
    """NaT would force .dt.year to float without the nullable Int64 cast."""
    from app.services.dataset_service import add_calendar_columns

    frame = add_calendar_columns(
        pd.DataFrame({"d": pd.to_datetime(["2024-01-01", None])})
    )

    assert frame["d_year"].isna().sum() == 1
    assert str(frame["d_year"].dtype) == "Int64"


def test_it_is_idempotent():
    """Re-uploading the same frame must not add _year_year."""
    from app.services.dataset_service import add_calendar_columns

    frame = add_calendar_columns(
        add_calendar_columns(pd.DataFrame({"d": pd.to_datetime(["2024-01-01"])}))
    )

    assert sorted(frame.columns) == ["d", "d_month", "d_year"]
