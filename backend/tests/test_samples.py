"""Tests for the sample fixtures (phase A9).

These assert the *properties* the samples are supposed to have, not their
contents. A sample that quietly stopped being dirty would still upload fine
and every other test would still pass, while the preprocessing report, the
excluded-column path and the type-conversion notice silently stopped being
exercised by anything.

Each number here is load-bearing against a threshold in validation.py, and
two of them were wrong on the first attempt — see the comments.
"""

import pathlib

import pandas as pd
import pytest

from app.data.validation import prepare_dataframe, validate_dataframe

SAMPLES = pathlib.Path(__file__).resolve().parent.parent.parent / "samples"


def load(name):
    return pd.read_csv(SAMPLES / name)


@pytest.fixture
def orders():
    return load("orders.csv")


# ---------------------------------------------------------------------------
# They exist and are reproducible
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["orders.csv", "customers.csv", "bad.csv"])
def test_the_sample_exists(name):
    assert (SAMPLES / name).is_file()


def test_there_is_a_generator_with_a_fixed_seed():
    """The expected answers in the verification runs are specific numbers, so
    a sample that drifted would break a check with no code change to blame."""
    source = (SAMPLES / "generate.py").read_text(encoding="utf-8")

    assert "SEED = " in source


def test_regenerating_produces_identical_files(tmp_path):
    import hashlib
    import subprocess
    import sys

    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(SAMPLES.glob("*.csv"))
    }

    result = subprocess.run(
        [sys.executable, str(SAMPLES / "generate.py")],
        capture_output=True,
        cwd=str(SAMPLES.parent),
    )
    assert result.returncode == 0, result.stderr.decode()

    after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(SAMPLES.glob("*.csv"))
    }

    assert before == after, "the generator is not deterministic"


# ---------------------------------------------------------------------------
# orders.csv is dirty, and accepted anyway
# ---------------------------------------------------------------------------


def test_orders_is_accepted_despite_being_dirty(orders):
    """It has to stay usable: the verification questions run against it."""
    result = prepare_dataframe(orders)

    assert result["errors"] == []
    assert result["working_df"] is not None


def test_orders_has_a_column_above_the_exclusion_threshold(orders):
    """customer_phone at ~74% is above the 70% column limit, so it is excluded
    WITH A REASON — which is what lets the agent say why a column is unusable
    instead of silently losing it."""
    result = prepare_dataframe(orders)

    assert "customer_phone" in result["unavailable_columns"]
    assert "%" in result["unavailable_columns"]["customer_phone"]


def test_orders_stays_well_under_the_dataset_rejection_limit(orders):
    """One column at 75% out of nine keeps the dataset mean near 9%, far
    below the 40% that would reject the file outright."""
    report = validate_dataframe(orders)

    assert report["overall_missing_ratio"] < 0.40
    assert report["overall_missing_ratio"] == pytest.approx(0.087, abs=0.01)


def test_orders_has_exact_duplicate_rows(orders):
    """The bug this guards against produced a fixture that tested nothing.

    The first generator duplicated the base rows and *then* filled in a random
    phone per row, so each "duplicate" got a different phone and
    df.duplicated() found none. The warning never fired and the fixture looked
    correct. Duplicating complete rows is what makes them exact.
    """
    assert orders.duplicated().sum() == 195


def test_orders_duplicate_ratio_warns_without_rejecting(orders):
    """13% is above the 10% warning line and nowhere near the 50% that
    rejects."""
    report = validate_dataframe(orders)

    assert 0.10 < report["duplicate_ratio"] < 0.50
    assert any("duplicates" in w for w in report["warnings"])


def test_orders_quantity_arrives_as_text(orders):
    """Whitespace-padded values and one word force the column to read as
    text, which is what exercises normalize_dataframe at all."""
    assert not pd.api.types.is_numeric_dtype(orders["quantity"])


def test_orders_quantity_is_converted_but_only_just(orders):
    """The sharp edge: the bad share is tuned to stay inside the limit.

    ~97% of values parse, clearing the 95% conversion threshold, so the column
    IS converted and the bad rows become NaN. Push the bad share past 5% and
    the column stays text, at which point summing it CONCATENATES and
    "highest total quantity" is silently wrong rather than merely short a few
    rows. That is the failure this fixture exists to keep reachable.
    """
    result = prepare_dataframe(orders)
    conversion = result["conversions"]["quantity"]

    assert conversion["converted_to"] == "numeric"
    assert float(conversion["success_rate"]) == pytest.approx(0.9725, abs=0.01)
    assert float(conversion["success_rate"]) > 0.95, "must clear the threshold"
    assert pd.api.types.is_numeric_dtype(result["working_df"]["quantity"])


def test_orders_has_some_unparseable_quantities_but_not_too_many(orders):
    """Both bounds matter: zero would stop exercising the conversion path at
    all, and too many would flip the column to text."""
    numeric = pd.to_numeric(orders["quantity"], errors="coerce")
    bad = numeric.isna().sum()

    assert bad > 0
    assert bad / len(orders) < 0.05


def test_orders_still_supports_the_verification_questions(orders):
    """The columns the A8/A9 questions depend on must survive preprocessing."""
    working = prepare_dataframe(orders)["working_df"]

    for column in ("Product", "quantity", "Price"):
        assert column in working.columns


# ---------------------------------------------------------------------------
# customers.csv is the clean control
# ---------------------------------------------------------------------------


def test_customers_is_completely_clean():
    """With orders.csv now dirty, something has to still exercise the "no
    warnings at all" path, or a regression that made every upload warn would
    look entirely normal."""
    result = prepare_dataframe(load("customers.csv"))

    assert result["errors"] == []
    assert result["warnings"] == []
    assert result["unavailable_columns"] == {}


# ---------------------------------------------------------------------------
# bad.csv must be rejected
# ---------------------------------------------------------------------------


def test_bad_is_rejected():
    result = prepare_dataframe(load("bad.csv"))

    assert result["errors"], "bad.csv must be rejected"
    assert result["working_df"] is None


def test_bad_is_rejected_for_missingness_specifically():
    result = prepare_dataframe(load("bad.csv"))

    assert any("missing" in e for e in result["errors"])


def test_bad_clears_the_threshold_with_margin_not_by_a_hair():
    """The arithmetic error this guards against.

    A first version blanked exactly half of each data column, giving
    (0 + 4 x 0.50) / 5 = 0.40 exactly — and the check is `>`, not `>=`, so the
    file was ACCEPTED and the fixture did the opposite of its job. 55% per
    column gives 0.44 and clears it properly.
    """
    report = validate_dataframe(load("bad.csv"))

    assert report["overall_missing_ratio"] > 0.40
    assert report["overall_missing_ratio"] == pytest.approx(0.44, abs=0.01)


def test_bad_has_no_column_over_the_exclusion_threshold():
    """If one column carried all the missingness it would simply be excluded
    and the file accepted — a different code path, and not this fixture's."""
    report = validate_dataframe(load("bad.csv"))

    assert report["unavailable_columns"] == {}


def test_bad_has_no_duplicate_rows():
    """RecordID stays populated so the mostly-empty rows are not duplicates of
    each other, which would trip a second rule and muddle the fixture."""
    assert load("bad.csv").duplicated().sum() == 0


def test_orders_covers_every_month_of_two_years(orders):
    """Phase C asks "per month" and "only 2024" questions, so both years and
    all 24 months have to be present - an empty month makes a grouping
    question degenerate while every other test still passes.
    """
    dates = pd.to_datetime(orders["OrderDate"])
    months = dates.dt.to_period("M").unique()
    years = sorted(dates.dt.year.unique())

    assert len(months) == 24, f"only {len(months)} month(s) in orders.csv"
    assert years == [2023, 2024]


def test_orders_has_enough_products_and_countries(orders):
    """Grouping questions need real cardinality to be meaningful."""
    assert orders["Product"].nunique() >= 5
    assert orders["Country"].nunique() >= 4


def test_orders_has_a_revenue_column(orders):
    """tools.py has no multiplication, so without a precomputed Revenue
    column "total revenue per country" could only ever be cannot_answer."""
    assert "Revenue" in orders.columns
    assert pd.api.types.is_numeric_dtype(orders["Revenue"])


def test_orders_is_large_enough_to_be_realistic(orders):
    assert len(orders) >= 1000
