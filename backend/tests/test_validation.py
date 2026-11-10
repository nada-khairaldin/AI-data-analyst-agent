"""Tests for validation.py — CSV loading, quality thresholds, type normalisation.

The thresholds under test are the ones the product promises in the UI
(docs/API_CONTRACT.md endpoint 5), so a change here is a change to what the
user is told about their data.
"""

import pandas as pd
import pytest

from validation import (
    DUPLICATE_REJECT_THRESHOLD,
    DUPLICATE_WARNING_THRESHOLD,
    MISSING_COLUMN_THRESHOLD,
    MISSING_DATASET_THRESHOLD,
    TYPE_CONVERSION_THRESHOLD,
    check_missing_values,
    load_csv,
    normalize_dataframe,
    prepare_dataframe,
    validate_dataframe,
    validate_question,
)


# ---------------------------------------------------------------------------
# Thresholds — pinned, because the UI quotes these numbers to the user
# ---------------------------------------------------------------------------


def test_thresholds_match_the_documented_values():
    """DatasetRejected.jsx renders "Maximum allowed 40%" as a literal.

    If these constants drift, the UI silently starts lying. This test is the
    link between the two.
    """
    assert MISSING_DATASET_THRESHOLD == 0.40
    assert MISSING_COLUMN_THRESHOLD == 0.70
    assert DUPLICATE_WARNING_THRESHOLD == 0.10
    assert DUPLICATE_REJECT_THRESHOLD == 0.50
    assert TYPE_CONVERSION_THRESHOLD == 0.95


# ---------------------------------------------------------------------------
# load_csv
# ---------------------------------------------------------------------------


def test_load_csv_reads_a_valid_file(valid_csv):
    df, error = load_csv(valid_csv)

    assert error is None
    assert list(df.columns) == ["Product", "Quantity"]
    assert len(df) == 2


def test_load_csv_rejects_duplicate_column_names(duplicate_header_csv):
    df, error = load_csv(duplicate_header_csv)

    assert df is None
    assert "Duplicate column names found" in error
    assert "Product" in error


def test_load_csv_on_completely_empty_input_returns_the_generic_message(make_csv):
    """Documents a real quirk rather than asserting the nicer message.

    load_csv reads the header row with csv.reader before handing the buffer to
    pandas. On empty input, next(reader) raises StopIteration, which the broad
    `except Exception` catches first — so the specific EmptyDataError branch
    ("contains no readable data") is unreachable for this input.
    """
    df, error = load_csv(make_csv(""))

    assert df is None
    assert error == "The file could not be read."


def test_load_csv_accepts_a_header_only_file(make_csv):
    """Header-only is NOT a load error; it becomes an empty frame.

    The "no data rows" rejection happens later, in validate_dataframe. Both
    layers are needed: this is why upload cannot rely on load_csv alone.
    """
    df, error = load_csv(make_csv("Product,Quantity\n"))

    assert error is None
    assert df.empty
    assert list(df.columns) == ["Product", "Quantity"]


# ---------------------------------------------------------------------------
# check_missing_values
# ---------------------------------------------------------------------------


def test_column_above_the_column_threshold_becomes_unavailable():
    # 4 of 5 missing = 80% > 70%. The other columns are full, so the
    # dataset-level average stays low and only the column rule fires.
    df = pd.DataFrame(
        {
            "Phone": [None, None, None, None, "x"],
            "Product": ["a", "b", "c", "d", "e"],
            "Quantity": [1, 2, 3, 4, 5],
        }
    )

    report = check_missing_values(df)

    assert "Phone" in report["unavailable_columns"]
    assert "80.0%" in report["unavailable_columns"]["Phone"]
    assert report["errors"] == []


def test_dataset_above_the_dataset_threshold_is_an_error():
    # Every column is 50% missing, so the mean of the column means is 0.50,
    # above the 0.40 dataset limit. No single column passes 70%, which keeps
    # this test about the dataset rule alone.
    df = pd.DataFrame(
        {
            "A": [1, None, 3, None],
            "B": [1, None, 3, None],
            "C": [1, None, 3, None],
        }
    )

    report = check_missing_values(df)

    assert len(report["errors"]) == 1
    assert "50.0%" in report["errors"][0]
    assert report["unavailable_columns"] == {}


def test_overall_missing_ratio_is_the_mean_of_column_means():
    """Pins the actual formula, which is not the fraction of missing cells.

    df.isna().mean().mean() averages the per-column ratios, so a wide column
    and a narrow one count equally. The two differ whenever column missingness
    is uneven; this test records which one the code uses, because it is the
    number shown to the user as a rejection reason.
    """
    df = pd.DataFrame({"A": [1, None], "B": [1, 2], "C": [1, 2]})

    report = check_missing_values(df)

    # Column ratios are 0.5, 0.0, 0.0 -> mean 0.1666...
    # The true missing-cell fraction would be 1/6 as well here; the shapes
    # diverge only with differing column lengths, which a DataFrame forbids.
    assert report["overall_missing_ratio"] == pytest.approx(1 / 6)
    assert report["column_missing_ratios"]["A"] == pytest.approx(0.5)


def test_missing_value_warnings_do_not_name_the_column():
    """Documents a known defect (docs/PLAN.md §1).

    The warning text omits the column name, so the list reads "80.0% of values
    are missing" with no subject. unavailable_columns does carry the name,
    which is why the report in endpoint 5 must be built from that dict rather
    than from warnings.
    """
    df = pd.DataFrame({"Phone": [None, None, None, None, "x"], "Q": [1, 2, 3, 4, 5]})

    report = check_missing_values(df)

    assert len(report["warnings"]) == 1
    assert "Phone" not in report["warnings"][0]


# ---------------------------------------------------------------------------
# validate_dataframe
# ---------------------------------------------------------------------------


def test_empty_dataframe_is_rejected():
    result = validate_dataframe(pd.DataFrame())

    assert result["errors"] == ["The dataset contains no data rows."]


def test_duplicate_rows_above_the_reject_threshold_are_an_error():
    # 3 of 4 rows are duplicates of the first = 75% > 50%.
    df = pd.DataFrame({"A": [1, 1, 1, 1], "B": [2, 2, 2, 2]})

    result = validate_dataframe(df)

    assert any("duplicates" in e for e in result["errors"])


def test_duplicate_rows_between_the_thresholds_are_only_a_warning():
    # 1 of 5 rows is a duplicate = 20%: above the 10% warning line, below the
    # 50% rejection line.
    df = pd.DataFrame({"A": [1, 2, 3, 4, 1], "B": [1, 2, 3, 4, 1]})

    result = validate_dataframe(df)

    assert result["errors"] == []
    assert any("duplicates" in w for w in result["warnings"])
    assert result["duplicate_ratio"] == pytest.approx(0.2)


def test_clean_dataframe_passes_with_no_errors_or_warnings(orders_df):
    result = validate_dataframe(orders_df)

    assert result["errors"] == []
    assert result["warnings"] == []
    assert result["unavailable_columns"] == {}


# ---------------------------------------------------------------------------
# normalize_dataframe
# ---------------------------------------------------------------------------


def test_numeric_strings_are_converted_to_numbers():
    df = pd.DataFrame({"Quantity": ["1", "2", "3", "4"]})

    working, conversions = normalize_dataframe(df)

    assert pd.api.types.is_numeric_dtype(working["Quantity"])
    assert conversions["Quantity"]["converted_to"] == "numeric"
    assert conversions["Quantity"]["success_rate"] == pytest.approx(1.0)


def test_mostly_numeric_column_below_the_threshold_is_left_alone():
    # 2 of 4 parse as numbers = 50%, well below the 95% requirement.
    df = pd.DataFrame({"Mixed": ["1", "2", "abc", "def"]})

    working, conversions = normalize_dataframe(df)

    # Asserted as "not numeric" rather than "== object": under pandas 3.x a
    # text column is StringDtype, not object. See
    # test_pandas_3_reports_text_columns_as_str_not_object below.
    assert not pd.api.types.is_numeric_dtype(working["Mixed"])
    assert conversions == {}


def test_datetime_conversion_requires_a_date_like_column_name():
    """A date-shaped column that is not NAMED like a date is not converted.

    normalize_dataframe only attempts datetime parsing when the column name
    contains date/time/created/updated/timestamp. This is intentional (it
    avoids mangling numeric ids), and it means "order_date" converts while an
    identically-valued "shipped" column does not.
    """
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    df = pd.DataFrame({"order_date": dates, "shipped": dates})

    working, conversions = normalize_dataframe(df)

    assert pd.api.types.is_datetime64_any_dtype(working["order_date"])
    assert conversions["order_date"]["converted_to"] == "datetime"

    assert not pd.api.types.is_datetime64_any_dtype(working["shipped"])
    assert "shipped" not in conversions


def test_already_typed_columns_are_skipped(orders_df):
    working, conversions = normalize_dataframe(orders_df)

    # Quantity is already int64 and Price already float64, so neither is
    # touched; the object columns are not numeric or date-like.
    assert conversions == {}
    assert working["Quantity"].dtype == orders_df["Quantity"].dtype


def test_normalize_does_not_mutate_the_input():
    df = pd.DataFrame({"Quantity": ["1", "2"]})

    normalize_dataframe(df)

    # The original dataset must survive untouched — a promise the
    # Preprocessing Report makes to the user in so many words.
    assert not pd.api.types.is_numeric_dtype(df["Quantity"])


# ---------------------------------------------------------------------------
# prepare_dataframe
# ---------------------------------------------------------------------------


def test_prepare_dataframe_happy_path_returns_a_working_copy():
    df = pd.DataFrame(
        {"Product": ["a", "b", "c"], "Quantity": ["1", "2", "3"]}
    )

    result = prepare_dataframe(df)

    assert result["errors"] == []
    assert pd.api.types.is_numeric_dtype(result["working_df"]["Quantity"])
    assert "Quantity" in result["conversions"]


def test_prepare_dataframe_short_circuits_on_a_fatal_error():
    """A dataset that fails validation never reaches normalisation."""
    df = pd.DataFrame({"A": [1, None], "B": [1, None], "C": [1, None]})

    result = prepare_dataframe(df)

    assert result["working_df"] is None
    assert result["errors"]
    assert result["conversions"] == {}


def test_prepare_dataframe_keeps_duplicate_warnings_after_normalisation():
    # 20% duplicates: the warning must survive the re-check, which only looks
    # at missing values.
    df = pd.DataFrame({"A": [1, 2, 3, 4, 1], "B": ["1", "2", "3", "4", "1"]})

    result = prepare_dataframe(df)

    assert any("duplicates" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# validate_question
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("question", ["", "   ", "\n", "\t "])
def test_blank_questions_are_rejected(question):
    is_valid, error = validate_question(question)

    assert is_valid is False
    assert error == "Please enter a question."


def test_a_real_question_is_accepted():
    is_valid, error = validate_question("Which product sold the most?")

    assert is_valid is True
    assert error is None


# ---------------------------------------------------------------------------
# pandas 3.x dtype behaviour — affects what the LLM is told about the data
# ---------------------------------------------------------------------------


def test_pandas_3_reports_text_columns_as_str_not_object():
    """Pinned because it changes the schema the planner prompt receives.

    This project is on pandas 3.0.6, where a text column is StringDtype and
    str(dtype) is "str" — not "object" as it was under pandas 1.x/2.x.

    get_schema() stringifies dtypes straight into the agent prompt and into the
    "Columns & Types" tab, so every schema the model sees now says "str". That
    is fine (arguably clearer), but it means:
      - any prompt example or doc that says "object" is now stale;
      - any code branching on == "object" is silently dead.
    Asserting it here means a pandas downgrade shows up as a failing test
    rather than as a quietly different prompt.
    """
    df = pd.DataFrame({"Product": ["Laptop", "Mouse"], "Quantity": [1, 2]})

    assert str(df["Product"].dtype) == "str"
    assert str(df["Quantity"].dtype) == "int64"


def test_get_schema_stringifies_every_column():
    from data_utils import get_schema

    df = pd.DataFrame(
        {
            "Product": ["Laptop"],
            "Quantity": [1],
            "Price": [9.5],
            "order_date": pd.to_datetime(["2024-01-01"]),
        }
    )

    schema = get_schema(df)

    assert schema["Quantity"] == "int64"
    assert schema["Price"] == "float64"
    assert schema["order_date"].startswith("datetime64")
    # Every value must be a string: the prompt builder json.dumps() this dict,
    # and a raw numpy dtype object is not JSON-serialisable.
    assert all(isinstance(v, str) for v in schema.values())
