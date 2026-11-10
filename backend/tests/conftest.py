"""Shared fixtures for the pure-module test suite.

These tests cover validation.py, tools.py and agent/validators.py exactly as
they behave today, BEFORE the restructure into app/ (docs/PLAN.md step A3).
They are the safety net for that move: they must pass before it and still pass
after it, with nothing changed but the import paths.

No LLM calls, no database, no network, no filesystem. Everything is a small
in-memory DataFrame or an in-memory byte buffer.
"""

import io

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------


@pytest.fixture
def orders_df():
    """A small, clean orders frame — the shape the whole project assumes.

    Deliberately includes two products with several rows each so that a
    group-by produces a predictable, hand-checkable result.
    """
    return pd.DataFrame(
        {
            "Product": ["Laptop", "Mouse", "Laptop", "Keyboard", "Mouse"],
            "Quantity": [10, 5, 15, 7, 3],
            "Price": [1000.0, 25.0, 1100.0, 50.0, 30.0],
            "Country": ["DE", "FR", "DE", "ES", "FR"],
        }
    )


@pytest.fixture
def schema():
    """The schema dict for ``orders_df``, as data_utils.get_schema would build it.

    Text columns are "str", not "object": this project runs pandas 3.x, where a
    text column is StringDtype. See
    test_validation.test_pandas_3_reports_text_columns_as_str_not_object.

    The validators only use this dict as a set of legal column names, so the
    dtype strings do not affect their behaviour — but they are kept accurate so
    the fixture is not quietly misleading.
    """
    return {
        "Product": "str",
        "Quantity": "int64",
        "Price": "float64",
        "Country": "str",
    }


# ---------------------------------------------------------------------------
# CSV buffers
# ---------------------------------------------------------------------------


def csv_bytes(text):
    """Wrap CSV text the way validation.load_csv expects it.

    load_csv calls .seek() and .getvalue(), so it needs BytesIO specifically —
    a plain bytes object or an open file would not satisfy both.
    """
    return io.BytesIO(text.encode("utf-8"))


@pytest.fixture
def make_csv():
    """Build a CSV buffer inside a test, for one-off content."""
    return csv_bytes


@pytest.fixture
def valid_csv():
    return csv_bytes("Product,Quantity\nLaptop,10\nMouse,5\n")


@pytest.fixture
def duplicate_header_csv():
    return csv_bytes("Product,Quantity,Product\nLaptop,10,Laptop\n")
